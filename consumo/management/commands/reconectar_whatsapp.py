from django.core.management.base import BaseCommand, CommandError

from consumo.services.whatsapp import (
    ConfiguracaoWhatsAppInvalida,
    garantir_conexao_whatsapp,
    obter_status_instancia_whatsapp,
)


class Command(BaseCommand):
    help = "Verifica status e tenta reestabelecer a conexao da instancia Z-API sem novo QRCode"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tentativas",
            type=int,
            default=None,
            help="Quantidade de tentativas de reconexao (padrao: ZAPI_RECONNECT_ATTEMPTS)",
        )
        parser.add_argument(
            "--espera",
            type=int,
            default=None,
            help="Segundos de espera entre etapas (padrao: ZAPI_RECONNECT_WAIT_SECONDS)",
        )

    def handle(self, *args, **options):
        try:
            status_inicial = obter_status_instancia_whatsapp()
        except ConfiguracaoWhatsAppInvalida as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Falha ao consultar status inicial: {exc}") from exc

        self.stdout.write(
            "Status inicial | "
            f"connected={status_inicial.get('connected')} | "
            f"smartphoneConnected={status_inicial.get('smartphoneConnected')} | "
            f"error={status_inicial.get('error') or '-'}"
        )

        try:
            resultado = garantir_conexao_whatsapp(
                tentativas=options.get("tentativas"),
                aguardar_segundos=options.get("espera"),
            )
        except ConfiguracaoWhatsAppInvalida as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Falha ao tentar reconectar: {exc}") from exc

        for passo in resultado.get("passos", []):
            etapa = passo.get("etapa")
            tentativa = passo.get("tentativa")
            if etapa.startswith("status"):
                self.stdout.write(
                    f"[tentativa {tentativa}] {etapa}: "
                    f"connected={passo.get('connected')} "
                    f"smartphoneConnected={passo.get('smartphoneConnected')} "
                    f"error={passo.get('error') or '-'}"
                )
            else:
                self.stdout.write(
                    f"[tentativa {tentativa}] {etapa}: ok={passo.get('ok')}"
                )

        if not resultado.get("ok"):
            raise CommandError("Nao foi possivel reestabelecer a conexao sem novo QRCode.")

        status_final = resultado.get("status", {})
        self.stdout.write(
            self.style.SUCCESS(
                "Conexao WhatsApp estavel | "
                f"acao={resultado.get('acao')} | "
                f"connected={status_final.get('connected')} | "
                f"smartphoneConnected={status_final.get('smartphoneConnected')}"
            )
        )
