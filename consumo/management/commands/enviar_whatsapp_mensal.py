from datetime import datetime
from decimal import Decimal
import re

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from consumo.models import Leitura, Lote
from consumo.services.whatsapp import (
    ConfiguracaoTwilioInvalida,
    enviar_resumo_consumo_whatsapp,
)


class Command(BaseCommand):
    help = "Envia resumo mensal por WhatsApp para todos os lotes residenciais ativos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-referencia",
            default=None,
            help="Data no formato YYYY-MM-DD (padrão: hoje)",
        )
        parser.add_argument(
            "--to",
            dest="to_whatsapp",
            default=None,
            help="Número de destino no formato whatsapp:+55... (opcional)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas simula o envio sem chamar a API da Twilio",
        )

    def handle(self, *args, **options):
        data_referencia = self._resolver_data_referencia(options.get("data_referencia"))
        data_inicio = data_referencia.replace(day=1)
        data_fim = data_referencia

        lotes = Lote.objects.filter(ativo=True, tipo="residencial").order_by("numero")
        if not lotes.exists():
            raise CommandError("Nenhum lote residencial ativo encontrado.")

        enviados = 0
        falhas = 0

        self.stdout.write(
            f"Processando {lotes.count()} lotes: período {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}"
        )

        for lote in lotes:
            consumo_litros = self._calcular_consumo_lote_litros(lote, data_inicio, data_fim)
            url_relatorio = self._montar_url_relatorio(lote.id)
            destino_lote = self._resolver_destino_lote(lote, options["to_whatsapp"])

            if not destino_lote:
                falhas += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️ Lote {lote.numero} sem WhatsApp cadastrado. Cadastre em Lote.telefone_whatsapp"
                    )
                )
                continue

            if options["dry_run"]:
                self.stdout.write(
                    f"[DRY-RUN] Lote {lote.numero} | WhatsApp: {destino_lote} | Consumo: {consumo_litros}L | URL: {url_relatorio}"
                )
                enviados += 1
                continue

            try:
                resultado = enviar_resumo_consumo_whatsapp(
                    lote=lote.numero,
                    data_inicio=data_inicio.strftime("%d/%m/%Y"),
                    data_fim=data_fim.strftime("%d/%m/%Y"),
                    consumo_litros=consumo_litros,
                    url_relatorio=url_relatorio,
                    to_whatsapp=destino_lote,
                )
                enviados += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Lote {lote.numero} enviado | SID: {resultado['sid']} | status: {resultado['status']}"
                    )
                )
            except ConfiguracaoTwilioInvalida as exc:
                raise CommandError(str(exc)) from exc
            except Exception as exc:
                falhas += 1
                self.stdout.write(
                    self.style.ERROR(f"❌ Lote {lote.numero} falhou: {exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Finalizado. Enviados: {enviados} | Falhas: {falhas}"
            )
        )

        if falhas > 0:
            raise CommandError("Execução finalizada com falhas. Verifique os erros acima.")

    def _resolver_destino_lote(self, lote, destino_forcado=None):
        if destino_forcado:
            return destino_forcado

        telefone = (lote.telefone_whatsapp or "").strip()
        if not telefone:
            return None

        if telefone.startswith("whatsapp:+"):
            return telefone

        if telefone.startswith("+") and re.fullmatch(r"\+[0-9]{10,15}", telefone):
            return f"whatsapp:{telefone}"

        return None

    def _resolver_data_referencia(self, valor):
        if not valor:
            return timezone.localdate()

        try:
            return datetime.strptime(valor, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError("--data-referencia deve estar no formato YYYY-MM-DD") from exc

    def _calcular_consumo_lote_litros(self, lote, data_inicio, data_fim):
        consumo_total_m3 = Decimal("0")

        for hidrometro in lote.hidrometros.filter(ativo=True).only("id"):
            leituras = Leitura.objects.filter(
                hidrometro=hidrometro,
                data_leitura__date__gte=data_inicio,
                data_leitura__date__lte=data_fim,
            ).order_by("data_leitura")

            if leituras.count() < 2:
                continue

            primeira = leituras.first()
            ultima = leituras.last()
            delta = ultima.leitura - primeira.leitura
            if delta > 0:
                consumo_total_m3 += delta

        return int(consumo_total_m3 * Decimal("1000"))

    def _montar_url_relatorio(self, lote_id):
        from django.conf import settings

        base_url = getattr(settings, "APP_BASE_URL", None)
        if not base_url:
            import os

            base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")

        base_url = base_url.rstrip("/")
        return f"{base_url}/lotes/{lote_id}/graficos/"
