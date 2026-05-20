from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import EmailValidator
from django.utils import timezone

from consumo.models import Lote
from consumo.services.env_guard import env_status_line, missing_required_env
from consumo.services.relatorios_cache import (
    calcular_data_coleta,
    caminho_pdf_lote,
    intervalo_mensal_da_coleta,
    pasta_relatorios_coleta,
)


class Command(BaseCommand):
    help = (
        'Precheck operacional para envio mensal por email: valida variaveis, '
        'cache de PDFs (ciclo 16 a 15) e cobertura de emails por lote.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-referencia',
            default=None,
            help='Data no formato YYYY-MM-DD (padrao: hoje)',
        )
        parser.add_argument(
            '--modo-estrito',
            action='store_true',
            help='Falha se houver qualquer pendencia critica para o envio do dia 20.',
        )
        parser.add_argument(
            '--limite-exemplos',
            type=int,
            default=10,
            help='Quantidade maxima de lotes de exemplo para cada pendencia.',
        )

    def handle(self, *args, **options):
        data_referencia = self._resolver_data_referencia(options.get('data_referencia'))
        modo_estrito = bool(options.get('modo_estrito'))
        limite_exemplos = max(1, int(options.get('limite_exemplos') or 10))

        data_coleta = calcular_data_coleta(data_referencia)
        data_inicio, data_fim = intervalo_mensal_da_coleta(data_coleta)
        pasta_cache = pasta_relatorios_coleta(data_coleta)

        self.stdout.write(
            'Precheck envio email mensal | '
            f'data_referencia={data_referencia} | coleta={data_coleta} | '
            f'periodo={data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")} '
        )

        required_env = []
        if settings.EMAIL_BACKEND.endswith('smtp.EmailBackend'):
            required_env.extend([
                'EMAIL_HOST',
                'EMAIL_PORT',
                'EMAIL_HOST_USER',
                'EMAIL_HOST_PASSWORD',
            ])
        required_env.append('DEFAULT_FROM_EMAIL')

        self.stdout.write(f'Env check | {env_status_line(required_env)}')

        faltantes_env = missing_required_env(required_env)
        if faltantes_env:
            self.stdout.write(
                self.style.ERROR(
                    '[CRITICO] Variaveis obrigatorias ausentes: ' + ', '.join(faltantes_env)
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('[OK] Variaveis criticas presentes.'))

        lotes = list(Lote.objects.filter(ativo=True, tipo='residencial').order_by('numero'))
        if not lotes:
            raise CommandError('Nenhum lote residencial ativo encontrado para precheck.')

        lotes_sem_emails = []
        lotes_com_emails = []
        lotes_com_emails_sem_pdf = []
        lotes_com_pdf = 0

        cache_existe = pasta_cache.exists()
        if cache_existe:
            self.stdout.write(self.style.SUCCESS(f'[OK] Pasta de cache encontrada: {pasta_cache}'))
        else:
            self.stdout.write(self.style.WARNING(f'[AVISO] Pasta de cache nao encontrada: {pasta_cache}'))

        for lote in lotes:
            destinos = self._destinos_lote(lote)
            if not destinos:
                lotes_sem_emails.append(lote.numero)
                continue

            lotes_com_emails.append(lote.numero)
            if cache_existe:
                caminho_pdf = caminho_pdf_lote(pasta_cache, lote.numero, data_inicio, data_fim)
                if caminho_pdf.exists():
                    lotes_com_pdf += 1
                else:
                    lotes_com_emails_sem_pdf.append(lote.numero)

        total_lotes = len(lotes)
        total_com_emails = len(lotes_com_emails)
        total_sem_emails = len(lotes_sem_emails)
        total_sem_pdf_cache = len(lotes_com_emails_sem_pdf)

        cobertura_emails = (total_com_emails / total_lotes * 100.0) if total_lotes else 0.0
        cobertura_pdf_cache = (lotes_com_pdf / total_com_emails * 100.0) if total_com_emails else 0.0

        self.stdout.write(
            'Resumo | '
            f'lotes_residenciais={total_lotes} | com_emails={total_com_emails} '
            f'({cobertura_emails:.1f}%) | sem_emails={total_sem_emails}'
        )

        if lotes_sem_emails:
            exemplos = ', '.join(lotes_sem_emails[:limite_exemplos])
            self.stdout.write(
                self.style.WARNING(
                    f'[AVISO] Lotes sem email ({total_sem_emails}) serao ignorados até o cadastro ser concluido. Exemplos: {exemplos}'
                )
            )

        if cache_existe:
            self.stdout.write(
                'Cache PDF | '
                f'com_emails_com_pdf={lotes_com_pdf}/{total_com_emails} '
                f'({cobertura_pdf_cache:.1f}%) | sem_pdf_cache={total_sem_pdf_cache}'
            )
            if lotes_com_emails_sem_pdf:
                exemplos = ', '.join(lotes_com_emails_sem_pdf[:limite_exemplos])
                self.stdout.write(
                    self.style.WARNING(
                        f'[AVISO] Lotes com emails sem PDF no cache ({total_sem_pdf_cache}). Exemplos: {exemplos}'
                    )
                )

        pendencias_criticas = []
        if faltantes_env:
            pendencias_criticas.append('variaveis_criticas_ausentes')
        if not cache_existe:
            pendencias_criticas.append('pasta_cache_ausente')
        if total_com_emails == 0:
            pendencias_criticas.append('nenhum_lote_com_email')
        if cache_existe and total_sem_pdf_cache > 0:
            pendencias_criticas.append('lotes_com_email_sem_pdf_no_cache')

        if pendencias_criticas:
            self.stdout.write(
                self.style.ERROR(
                    'Pendencias criticas detectadas: ' + ', '.join(pendencias_criticas)
                )
            )
            if modo_estrito:
                raise CommandError(
                    'Precheck em modo estrito falhou. Corrija as pendencias antes do dia 20.'
                )
            self.stdout.write(self.style.WARNING('Precheck concluido com pendencias (modo nao estrito).'))
            return

        self.stdout.write(self.style.SUCCESS('Precheck concluido com sucesso. Ambiente pronto para o envio do dia 20.'))

    def _resolver_data_referencia(self, valor):
        if not valor:
            return timezone.localdate()
        try:
            return datetime.strptime(valor, '%Y-%m-%d').date()
        except ValueError as exc:
            raise CommandError('--data-referencia deve estar no formato YYYY-MM-DD') from exc

    def _destinos_lote(self, lote):
        candidatos = [
            (lote.email_proprietario or '').strip().lower(),
            (getattr(lote, 'email_proprietario_2', '') or '').strip().lower(),
        ]
        destinos = []
        for candidato in candidatos:
            if not candidato:
                continue
            try:
                EmailValidator()(candidato)
            except ValidationError:
                continue
            destinos.append(candidato)

        return list(dict.fromkeys(destinos))