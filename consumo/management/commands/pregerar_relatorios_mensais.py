import json
import os
import time
from datetime import datetime
from io import BytesIO

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Exists, OuterRef

import requests
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from consumo.models import Lote, Leitura
from consumo.services.relatorios_cache import (
    calcular_data_coleta,
    caminho_pdf_lote,
    intervalo_mensal_da_coleta,
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
        parser.add_argument(
            "--base-url",
            default=None,
            help="URL base da aplicacao para baixar os PDFs (ex: https://controle-de-consumo-de-agua.onrender.com)",
        )
        parser.add_argument(
            "--lote-numero",
            default=None,
            help="Gera apenas um lote especifico (numero do lote, ex: 287).",
        )
        parser.add_argument(
            "--permitir-base-local",
            action="store_true",
            help="Permite APP_BASE_URL local (localhost/127.0.0.1). Em producao, mantenha desativado.",
        )
        parser.add_argument(
            "--intervalo-segundos",
            type=float,
            default=2.0,
            help="Intervalo entre lotes para reduzir carga (padrao: 2s).",
        )
        parser.add_argument(
            "--tentativas",
            type=int,
            default=3,
            help="Quantidade de tentativas por lote em caso de falha temporaria (padrao: 3).",
        )

    def handle(self, *args, **options):
        data_coleta = self._resolver_data_coleta(options.get("data_coleta"))
        data_inicio, data_fim = intervalo_mensal_da_coleta(data_coleta)
        pasta_saida = pasta_relatorios_coleta(data_coleta)
        pasta_saida.mkdir(parents=True, exist_ok=True)

        lotes = Lote.objects.filter(ativo=True, tipo="residencial")
        if options.get("lote_numero"):
            lotes = lotes.filter(numero=str(options["lote_numero"]).strip())
        lotes = lotes.order_by("numero")
        if not lotes.exists():
            raise CommandError(
                "Nenhum lote residencial ativo encontrado para o periodo "
                f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}."
            )

        base_url = self._obter_base_url(
            options.get("base_url"),
            permitir_local=options.get("permitir_base_local", False),
        )
        intervalo_segundos = max(0.0, float(options.get("intervalo_segundos") or 0.0))
        tentativas = max(1, int(options.get("tentativas") or 1))
        gerados = 0
        ignorados = 0
        ignorados_sem_registro_sem_whatsapp = 0
        fallback_sem_dados = 0
        erros = 0

        self.stdout.write(
            "Pregerando relatorios anuais "
            f"({data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}) "
            f"para {lotes.count()} lote(s) em {pasta_saida}"
        )

        leituras_periodo_subquery = Leitura.objects.filter(
            hidrometro__lote_id=OuterRef('pk'),
            data_leitura__date__gte=data_inicio,
            data_leitura__date__lte=data_fim,
        )
        lotes = lotes.annotate(tem_leituras_periodo=Exists(leituras_periodo_subquery))

        total_lotes = lotes.count()
        for indice, lote in enumerate(lotes, start=1):
            self.stdout.write(f"[{indice}/{total_lotes}] Lote {lote.numero}: iniciando")

            tem_whatsapp = bool(
                (getattr(lote, 'telefone_whatsapp', '') or '').strip()
                or (getattr(lote, 'telefone_whatsapp_2', '') or '').strip()
            )

            if not lote.tem_leituras_periodo and not tem_whatsapp:
                ignorados_sem_registro_sem_whatsapp += 1
                continue

            caminho_pdf = caminho_pdf_lote(pasta_saida, lote.numero, data_inicio, data_fim)
            if caminho_pdf.exists() and not options["sobrescrever"]:
                ignorados += 1
                continue

            # Protege contra cenários em que a pasta não exista por limpeza externa.
            caminho_pdf.parent.mkdir(parents=True, exist_ok=True)

            try:
                url_pdf = (
                    f"{base_url}/lotes/{lote.id}/graficos/exportar/pdf/"
                    f"?periodo=personalizado&data_inicio={data_inicio.strftime('%Y-%m-%d')}"
                    f"&data_fim={data_fim.strftime('%Y-%m-%d')}"
                )

                response_pdf = self._baixar_pdf_com_retry(
                    url=url_pdf,
                    tentativas=tentativas,
                    timeout=180,
                )
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

            if indice < total_lotes and intervalo_segundos > 0:
                time.sleep(intervalo_segundos)

        manifesto_path = pasta_saida / "manifesto.json"
        manifesto_path.parent.mkdir(parents=True, exist_ok=True)
        manifesto = {
            "gerado_em": timezone.localtime(timezone.now()).isoformat(),
            "data_coleta": data_coleta.isoformat(),
            "periodo_inicio": data_inicio.isoformat(),
            "periodo_fim": data_fim.isoformat(),
            "quantidade_lotes": lotes.count(),
            "pdfs_gerados": gerados,
            "pdfs_ignorados_existentes": ignorados,
            "pdfs_ignorados_sem_registro_sem_whatsapp": ignorados_sem_registro_sem_whatsapp,
            "pdfs_fallback_sem_dados": fallback_sem_dados,
            "pdfs_com_erro": erros,
        }
        with open(manifesto_path, "w", encoding="utf-8") as manifesto_file:
            json.dump(manifesto, manifesto_file, ensure_ascii=False, indent=2)

        self.stdout.write(
            self.style.SUCCESS(
                "Concluido. "
                f"Gerados: {gerados} | Fallback sem dados: {fallback_sem_dados} "
                f"| Ignorados existentes: {ignorados} "
                f"| Ignorados sem registro e sem WhatsApp: {ignorados_sem_registro_sem_whatsapp} "
                f"| Erros: {erros} | Pasta: {pasta_saida}"
            )
        )

        if erros > 0:
            raise CommandError("Pre-geracao finalizada com erros. Verifique os avisos acima.")

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

    def _obter_base_url(self, base_url_override=None, permitir_local=False):
        base_url = (base_url_override or "").strip().rstrip("/")
        if not base_url:
            base_url = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
        if not base_url:
            raise CommandError(
                "APP_BASE_URL nao configurada. Defina a URL base da aplicacao para baixar PDFs."
            )

        base_url_lower = base_url.lower()
        if not permitir_local and ("localhost" in base_url_lower or "127.0.0.1" in base_url_lower):
            raise CommandError(
                "URL base local detectada. Use --base-url com dominio publico do Render "
                "ou --permitir-base-local explicitamente."
            )
        return base_url

    def _baixar_pdf_com_retry(self, url, tentativas, timeout):
        ultima_resposta = None
        ultimo_erro = None

        for tentativa in range(1, tentativas + 1):
            try:
                resposta = requests.get(url, timeout=timeout)
                ultima_resposta = resposta

                # 404 e 400 sao erros de negocio; nao adianta repetir.
                if resposta.status_code in {400, 404}:
                    return resposta

                # Sucesso.
                if resposta.status_code == 200:
                    return resposta

                # Erros temporarios (429/5xx): tenta novamente.
                if resposta.status_code in {429, 500, 502, 503, 504} and tentativa < tentativas:
                    time.sleep(min(8, 1.5 * tentativa))
                    continue

                return resposta
            except Exception as exc:  # noqa: BLE001
                ultimo_erro = exc
                if tentativa < tentativas:
                    time.sleep(min(8, 1.5 * tentativa))
                    continue

        if ultima_resposta is not None:
            return ultima_resposta

        raise RuntimeError(f"Falha de rede ao baixar PDF: {ultimo_erro}")
