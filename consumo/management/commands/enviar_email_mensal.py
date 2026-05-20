from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import EmailValidator
from django.utils import timezone

from consumo.models import Leitura, Lote
from consumo.services.relatorios_cache import (
    calcular_data_coleta,
    caminho_pdf_lote,
    intervalo_mensal_da_coleta,
    pasta_relatorios_coleta,
)


class Command(BaseCommand):
    help = 'Envia os relatorios mensais em PDF por email para os lotes residenciais ativos.'

    def add_arguments(self, parser):
        parser.add_argument('--data-referencia', default=None, help='Data no formato YYYY-MM-DD (padrao: hoje)')
        parser.add_argument('--dry-run', action='store_true', help='Apenas simula o envio')

    def handle(self, *args, **options):
        if settings.EMAIL_BACKEND.endswith('smtp.EmailBackend'):
            required_env = ['EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'DEFAULT_FROM_EMAIL']
            faltantes = [key for key in required_env if not str(getattr(settings, key, '')).strip()]
            if faltantes:
                raise CommandError('Variaveis de email ausentes: ' + ', '.join(faltantes))

        data_referencia = self._resolver_data_referencia(options.get('data_referencia'))
        data_coleta = calcular_data_coleta(data_referencia)
        data_inicio, data_fim = intervalo_mensal_da_coleta(data_coleta)
        pasta_cache = pasta_relatorios_coleta(data_coleta)

        if not pasta_cache.exists():
            raise CommandError(f'Pasta de relatorios nao encontrada: {pasta_cache}')

        lotes = Lote.objects.filter(ativo=True, tipo='residencial').order_by('numero')
        if not lotes.exists():
            raise CommandError('Nenhum lote residencial ativo encontrado.')

        enviados = 0
        pulados_sem_email = 0
        pulados_sem_pdf = 0
        erros = 0

        self.stdout.write(
            'Enviando relatorios por email | '
            f'periodo={data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")} | '
            f'pasta={pasta_cache}'
        )

        for lote in lotes:
            destinatarios = self._destinos_lote(lote)
            if not destinatarios:
                pulados_sem_email += 1
                self.stdout.write(self.style.WARNING(f'Lote {lote.numero}: sem email cadastrado.'))
                continue

            caminho_pdf = caminho_pdf_lote(pasta_cache, lote.numero, data_inicio, data_fim)
            if not caminho_pdf.exists():
                pulados_sem_pdf += 1
                self.stdout.write(self.style.WARNING(f'Lote {lote.numero}: PDF nao encontrado em {caminho_pdf}.'))
                continue

            if options['dry_run']:
                self.stdout.write(
                    f'[DRY-RUN] Lote {lote.numero} -> {", ".join(destinatarios)} | PDF: {caminho_pdf.name}'
                )
                enviados += 1
                continue

            try:
                with open(caminho_pdf, 'rb') as arquivo_pdf:
                    conteudo_pdf = arquivo_pdf.read()

                consumo_litros = self._calcular_consumo_lote_litros(lote, data_inicio, data_fim)

                mensagem = EmailMessage(
                    subject=self._assunto_email(lote.numero),
                    body=self._corpo_email(lote, data_inicio, data_fim, consumo_litros),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=destinatarios,
                )
                mensagem.attach(caminho_pdf.name, conteudo_pdf, 'application/pdf')
                resultado = mensagem.send(fail_silently=False)
                if resultado <= 0:
                    raise RuntimeError('EmailMessage.send retornou zero mensagens entregues.')

                enviados += 1
                self.stdout.write(self.style.SUCCESS(f'[OK] Lote {lote.numero} enviado para {", ".join(destinatarios)}'))
            except Exception as exc:  # noqa: BLE001
                erros += 1
                self.stdout.write(self.style.ERROR(f'[ERRO] Lote {lote.numero}: {exc}'))

        self.stdout.write(
            self.style.SUCCESS(
                'Finalizado. '
                f'Enviados: {enviados} | Sem email: {pulados_sem_email} | Sem PDF: {pulados_sem_pdf} | Erros: {erros}'
            )
        )

        if erros > 0:
            raise CommandError('Execucao finalizada com falhas. Verifique os erros acima.')

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

    def _assunto_email(self, lote_numero):
        return f'Resumo mensal de consumo de água do Lote {lote_numero}'

    def _corpo_email(self, lote, data_inicio, data_fim, consumo_litros):
        consumo_formatado = self._formatar_litros(consumo_litros)
        return (
            f'Olá! Segue o resumo mensal de consumo de água do Lote {lote.numero}.\n\n'
            f'📅 Período: {data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}\n'
            f'📊 Consumo no Período: {consumo_formatado} litros\n'
            '‼️Limite Mensal: 15.000 litros, valores excedentes sujeitos a cobrança.\n\n'
            '⚠️ Esta é uma mensagem automática. Em caso de dúvidas, por favor, entre em contato diretamente com a administração.\n\n'
            'Atenciosamente,\n'
            'Condomínio Residencial Pedra de Inoã'
        )

    def _formatar_litros(self, valor):
        try:
            inteiro = int(float(valor))
        except (TypeError, ValueError):
            inteiro = 0
        return f'{inteiro:,}'.replace(',', '.')

    def _data_leitura_local(self, leitura):
        return timezone.localtime(leitura.data_leitura)

    def _calcular_consumo_lote_litros(self, lote, data_inicio, data_fim):
        consumo_total_m3 = Decimal('0')
        for hidrometro in lote.hidrometros.filter(ativo=True).only('id'):
            leitura_anterior_periodo = Leitura.objects.filter(
                hidrometro=hidrometro,
                data_leitura__date__lt=data_inicio,
            ).order_by('-data_leitura').first()

            leituras_periodo = list(
                Leitura.objects.filter(
                    hidrometro=hidrometro,
                    data_leitura__date__gte=data_inicio,
                    data_leitura__date__lte=data_fim,
                ).order_by('data_leitura')
            )

            if leitura_anterior_periodo:
                leituras_para_calculo = [leitura_anterior_periodo] + leituras_periodo
            else:
                leituras_para_calculo = leituras_periodo

            for indice in range(1, len(leituras_para_calculo)):
                leitura_atual = leituras_para_calculo[indice]
                leitura_anterior = leituras_para_calculo[indice - 1]

                if self._data_leitura_local(leitura_atual).date() < data_inicio:
                    continue

                delta = leitura_atual.leitura - leitura_anterior.leitura
                if delta > 0:
                    consumo_total_m3 += delta

        return int(consumo_total_m3 * Decimal('1000'))