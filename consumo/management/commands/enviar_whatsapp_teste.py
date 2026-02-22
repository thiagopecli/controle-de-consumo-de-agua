from django.core.management.base import BaseCommand, CommandError

from consumo.services.whatsapp import (
    ConfiguracaoTwilioInvalida,
    enviar_resumo_consumo_whatsapp,
)


class Command(BaseCommand):
    help = "Envia mensagem de teste do template WhatsApp (Twilio Content Template)"

    def add_arguments(self, parser):
        parser.add_argument("--lote", default="A-101", help="Valor para {{1}}")
        parser.add_argument("--inicio", default="01/02/2026", help="Valor para {{2}}")
        parser.add_argument("--fim", default="15/02/2026", help="Valor para {{3}}")
        parser.add_argument("--consumo", default="12450", help="Valor para {{4}} em litros")
        parser.add_argument(
            "--url",
            default="http://127.0.0.1:8000/",
            help="Valor para {{5}} (link do relatório)",
        )
        parser.add_argument(
            "--to",
            dest="to_whatsapp",
            default=None,
            help="Número de destino no formato whatsapp:+55... (opcional)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Enviando mensagem de teste via Twilio...")

        try:
            resultado = enviar_resumo_consumo_whatsapp(
                lote=options["lote"],
                data_inicio=options["inicio"],
                data_fim=options["fim"],
                consumo_litros=options["consumo"],
                url_relatorio=options["url"],
                to_whatsapp=options["to_whatsapp"],
            )
        except ConfiguracaoTwilioInvalida as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Erro no envio: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Mensagem enviada com sucesso."))
        self.stdout.write(f"SID: {resultado['sid']}")
        self.stdout.write(f"Status inicial: {resultado['status']}")
        self.stdout.write(f"De: {resultado['from']}")
        self.stdout.write(f"Para: {resultado['to']}")
