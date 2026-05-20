import os
from datetime import datetime
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from consumo.models import Leitura
from consumo.services.relatorios_cache import calcular_data_coleta, intervalo_mensal_da_coleta


class Command(BaseCommand):
    help = (
        'Baixa fotos de leituras a partir da URL publica da aplicacao e as salva em MEDIA_ROOT '
        'no caminho esperado do ImageField.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-coleta',
            default=None,
            help='Data de coleta no formato YYYY-MM-DD (padrao: ciclo atual).',
        )
        parser.add_argument(
            '--base-url',
            default=None,
            help='URL base da aplicacao para baixar as fotos (ex: https://...onrender.com).',
        )
        parser.add_argument(
            '--sobrescrever',
            action='store_true',
            help='Rebaixa fotos mesmo quando o arquivo local ja existir.',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout em segundos para cada download.',
        )

    def handle(self, *args, **options):
        data_coleta = self._resolver_data_coleta(options.get('data_coleta'))
        data_inicio, data_fim = intervalo_mensal_da_coleta(data_coleta)
        base_url = self._obter_base_url(options.get('base_url'))
        sobrescrever = bool(options.get('sobrescrever', False))
        timeout = max(5, int(options.get('timeout') or 30))

        qs = Leitura.objects.filter(
            data_leitura__date__gte=data_inicio,
            data_leitura__date__lte=data_fim,
        ).exclude(foto='').exclude(foto__isnull=True).select_related('hidrometro__lote')

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('Nenhuma leitura com foto encontrada no periodo.'))
            return

        self.stdout.write(
            f'Sincronizando fotos de {total} leitura(s) para o periodo '
            f'{data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}...'
        )

        job_token = os.getenv('JOB_SECRET_TOKEN', '').strip()
        baixadas = 0
        ignoradas = 0
        erros = 0

        for leitura in qs.iterator():
            if not leitura.foto or not leitura.foto.name:
                ignoradas += 1
                continue

            destino = Path(settings.MEDIA_ROOT) / leitura.foto.name
            if destino.exists() and not sobrescrever:
                ignoradas += 1
                continue

            url_foto = self._montar_url_job(base_url, leitura.id)
            destino.parent.mkdir(parents=True, exist_ok=True)

            try:
                headers = {'X-Job-Token': job_token} if job_token else {}
                response = requests.get(url_foto, timeout=timeout, headers=headers)
                if response.status_code != 200 or not response.content:
                    url_fallback = self._montar_url_foto(base_url, leitura.foto.url)
                    response = requests.get(url_fallback, timeout=timeout)

                if response.status_code != 200 or not response.content:
                    erros += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Lote {leitura.hidrometro.lote.numero} leitura {leitura.id}: '
                            f'nao foi possivel baixar ({response.status_code}).'
                        )
                    )
                    continue

                destino.write_bytes(response.content)
                baixadas += 1
                self.stdout.write(
                    f'Lote {leitura.hidrometro.lote.numero} leitura {leitura.id}: foto salva em {destino}'
                )
            except Exception as exc:  # noqa: BLE001
                erros += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'Lote {leitura.hidrometro.lote.numero} leitura {leitura.id}: erro ao baixar ({exc}).'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Concluido. Baixadas: {baixadas} | Ignoradas: {ignoradas} | Erros: {erros}'
            )
        )

    def _resolver_data_coleta(self, data_coleta_str):
        if data_coleta_str:
            try:
                return datetime.strptime(data_coleta_str, '%Y-%m-%d').date()
            except ValueError as exc:
                raise CommandError('Data de coleta invalida. Use YYYY-MM-DD.') from exc

        hoje = timezone.localdate()
        return calcular_data_coleta(hoje)

    def _obter_base_url(self, base_url):
        valor = (base_url or os.getenv('APP_BASE_URL', '')).strip().rstrip('/')
        if not valor:
            raise CommandError('APP_BASE_URL nao configurada. Nao e possivel baixar as fotos.')
        return valor

    def _montar_url_foto(self, base_url, foto_url):
        foto_path = (foto_url or '').strip()
        if not foto_path:
            raise CommandError('URL da foto vazia.')
        return f"{base_url}/{foto_path.lstrip('/')}"

    def _montar_url_job(self, base_url, leitura_id):
        return f"{base_url}/jobs/leituras/{int(leitura_id)}/foto/"