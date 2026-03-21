import json
import os
from datetime import datetime
from io import BytesIO

import requests
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from consumo.models import Lote
from consumo.services.relatorios_cache import (
    calcular_data_coleta,
    caminho_pdf_lote,
    intervalo_anual_da_coleta,
    pasta_relatorios_coleta,
)


class Command(BaseCommand):
    help = (
        "Pregera relatorios anuais em PDF dos lotes residenciais e salva em pasta "
        "datada (dia 15), para envio no dia 20 sem sobrecarga."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-coleta",
            default=None,
            help="Data de coleta no formato YYYY-MM-DD (padrao: dia 15 derivado de hoje)",
        )
        parser.add_argument(
            "--sobrescrever",
            action="store_true",
            help="Sobrescreve PDFs ja existentes na pasta de destino.",
        )

    def handle(self, *args, **options):
        data_coleta = self._resolver_data_coleta(options.get("data_coleta"))
        data_inicio, data_fim = intervalo_anual_da_coleta(data_coleta)
        pasta_saida = pasta_relatorios_coleta(data_coleta)
        pasta_saida.mkdir(parents=True, exist_ok=True)

        lotes = Lote.objects.filter(ativo=True, tipo="residencial").order_by("numero")
        if not lotes.exists():
            raise CommandError(
                "Nenhum lote residencial ativo encontrado para o periodo "
                f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}."
            )

        gerados = 0
        ignorados = 0
        fallback_sem_dados = 0
        erros = 0

        self.stdout.write(
            "Pregerando relatorios anuais "
            f"({data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}) "
            f"para {lotes.count()} lote(s) em {pasta_saida}"
        )

        for lote in lotes:
            caminho_pdf = caminho_pdf_lote(pasta_saida, lote.numero, data_inicio, data_fim)
            if caminho_pdf.exists() and not options["sobrescrever"]:
                ignorados += 1
                continue

            try:
                response_pdf = self._baixar_pdf_por_url(lote.id, data_inicio, data_fim)
                if response_pdf.status_code == 404:
                    self._gerar_pdf_fallback_sem_dados(
                        caminho_pdf,
                        lote_numero=lote.numero,
                        data_inicio=data_inicio.strftime("%d/%m/%Y"),
                        data_fim=data_fim.strftime("%d/%m/%Y"),
                    )
                    gerados += 1
                    fallback_sem_dados += 1
                    continue

                if response_pdf.status_code != 200:
                    erros += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Lote {lote.numero}: retorno {response_pdf.status_code}, nao foi gerado."
                        )
                    )
                    continue

                with open(caminho_pdf, "wb") as arquivo_pdf:
                    arquivo_pdf.write(response_pdf.content)
                gerados += 1
            except Exception as exc:  # noqa: BLE001
                erros += 1
                self.stdout.write(
                    self.style.WARNING(f"Lote {lote.numero}: erro ao gerar relatorio ({exc}).")
                )

        manifesto_path = pasta_saida / "manifesto.json"
        manifesto = {
            "gerado_em": timezone.localtime(timezone.now()).isoformat(),
            "data_coleta": data_coleta.isoformat(),
            "periodo_inicio": data_inicio.isoformat(),
            "periodo_fim": data_fim.isoformat(),
            "quantidade_lotes": lotes.count(),
            "pdfs_gerados": gerados,
            "pdfs_ignorados_existentes": ignorados,
            "pdfs_fallback_sem_dados": fallback_sem_dados,
            "pdfs_com_erro": erros,
        }
        with open(manifesto_path, "w", encoding="utf-8") as manifesto_file:
            json.dump(manifesto, manifesto_file, ensure_ascii=False, indent=2)

        self.stdout.write(
            self.style.SUCCESS(
                "Concluido. "
                f"Gerados: {gerados} | Fallback sem dados: {fallback_sem_dados} "
                f"| Ignorados: {ignorados} | Erros: {erros} | Pasta: {pasta_saida}"
            )
        )

        if erros > 0:
            raise CommandError("Pre-geracao finalizada com erros. Verifique os avisos acima.")

    def _baixar_pdf_por_url(self, lote_id, data_inicio, data_fim):
        base_url = getattr(settings, "APP_BASE_URL", None)
        if not base_url:
            base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
        base_url = base_url.rstrip("/")

        url = (
            f"{base_url}/lotes/{lote_id}/graficos/exportar/pdf/"
            f"?periodo=personalizado&data_inicio={data_inicio.strftime('%Y-%m-%d')}"
            f"&data_fim={data_fim.strftime('%Y-%m-%d')}"
        )

        return requests.get(url, timeout=120)

    def _gerar_pdf_fallback_sem_dados(self, caminho_pdf, lote_numero, data_inicio, data_fim):
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)

        c.setTitle(f"Relatorio do Lote {lote_numero}")
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 790, f"Relatorio de Consumo - Lote {lote_numero}")

        c.setFont("Helvetica", 11)
        c.drawString(72, 760, f"Periodo: {data_inicio} a {data_fim}")
        c.drawString(72, 735, "Status: sem dados suficientes para apuracao de consumo no periodo.")
        c.drawString(72, 710, "Motivo comum: lote sem hidrometro ativo ou sem leituras validas.")
        c.drawString(72, 680, "Em caso de divergencia, contate a administracao.")

        c.showPage()
        c.save()

        with open(caminho_pdf, "wb") as arquivo_pdf:
            arquivo_pdf.write(buffer.getvalue())
        buffer.close()

    def _resolver_data_coleta(self, valor):
        if valor:
            try:
                data = datetime.strptime(valor, "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError("--data-coleta deve estar no formato YYYY-MM-DD") from exc

            if data.day != 15:
                self.stdout.write(
                    self.style.WARNING(
                        "A data informada nao e dia 15. O sistema usara exatamente essa data como referencia."
                    )
                )
            return data

        return calcular_data_coleta(timezone.localdate())
