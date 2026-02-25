from datetime import datetime
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test.client import RequestFactory

from consumo.models import Lote, Leitura
from consumo.views import exportar_graficos_lote_pdf


class Command(BaseCommand):
    help = 'Gera os relatórios PDF individuais dos lotes para um período e salva em pasta dedicada.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-inicio',
            required=True,
            help='Data inicial no formato YYYY-MM-DD (ex: 2026-01-01)'
        )
        parser.add_argument(
            '--data-fim',
            required=True,
            help='Data final no formato YYYY-MM-DD (ex: 2026-02-15)'
        )

    def handle(self, *args, **options):
        data_inicio_str = options['data_inicio']
        data_fim_str = options['data_fim']

        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        except ValueError as exc:
            raise CommandError('Datas inválidas. Use o formato YYYY-MM-DD.') from exc

        if data_inicio > data_fim:
            raise CommandError('data-inicio não pode ser maior que data-fim.')

        intervalo_token = f"{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}"
        pasta_saida = os.path.join(settings.BASE_DIR, f'relatorios_lotes_{intervalo_token}')
        os.makedirs(pasta_saida, exist_ok=True)

        lotes_ids = (
            Leitura.objects.filter(
                hidrometro__lote__tipo='residencial',
                hidrometro__lote__ativo=True,
                data_leitura__date__gte=data_inicio,
                data_leitura__date__lte=data_fim,
            )
            .values_list('hidrometro__lote_id', flat=True)
            .distinct()
        )

        lotes = Lote.objects.filter(id__in=lotes_ids, ativo=True, tipo='residencial').order_by('numero')

        if not lotes.exists():
            self.stdout.write(self.style.WARNING('Nenhum lote residencial com leituras no período informado.'))
            return

        request_factory = RequestFactory()
        total_gerados = 0
        total_erros = 0

        self.stdout.write(
            f'Gerando relatórios para {lotes.count()} lote(s) no período {data_inicio_str} a {data_fim_str}...'
        )

        for lote in lotes:
            request_lote = request_factory.get(
                '/',
                {
                    'periodo': 'personalizado',
                    'data_inicio': data_inicio_str,
                    'data_fim': data_fim_str,
                }
            )

            try:
                resposta_pdf = exportar_graficos_lote_pdf(request_lote, lote.id)
                if resposta_pdf.status_code != 200:
                    total_erros += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Lote {lote.numero}: retorno {resposta_pdf.status_code}, relatório não gerado.'
                        )
                    )
                    continue

                nome_arquivo = (
                    f'relatorio_lote_{lote.numero}_{data_inicio.strftime("%Y%m%d")}_{data_fim.strftime("%Y%m%d")}.pdf'
                )
                caminho_arquivo = os.path.join(pasta_saida, nome_arquivo)
                with open(caminho_arquivo, 'wb') as arquivo_pdf:
                    arquivo_pdf.write(resposta_pdf.content)

                total_gerados += 1
            except Exception as exc:  # noqa: BLE001
                total_erros += 1
                self.stdout.write(self.style.WARNING(f'Lote {lote.numero}: erro ao gerar relatório ({exc}).'))

        self.stdout.write(
            self.style.SUCCESS(
                f'Concluído. Gerados: {total_gerados} | Erros: {total_erros} | Pasta: {pasta_saida}'
            )
        )
