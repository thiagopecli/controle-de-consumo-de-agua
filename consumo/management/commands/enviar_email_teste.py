from django.core.management.base import BaseCommand, CommandError

from consumo.services.email import (
    ConfiguracaoEmailInvalida,
    enviar_relatorio_pdf_email,
    enviar_resumo_consumo_email,
)


class Command(BaseCommand):
    help = "Envia mensagem de teste por e-mail"

    def add_arguments(self, parser):
        parser.add_argument("--lote", default="A-101", help="Identificação do lote")
        parser.add_argument("--inicio", default="16/01/2026", help="Data inicial do período")
        parser.add_argument("--fim", default="15/02/2026", help="Data final do período")
        parser.add_argument("--consumo", default="12450", help="Consumo em litros")
        parser.add_argument(
            "--url",
            default="http://127.0.0.1:8000/",
            help="Link do relatório",
        )
        parser.add_argument(
            "--to",
            dest="to_email",
            default=None,
            help="E-mail de destino (obrigatorio)",
        )
        parser.add_argument(
            "--enviar-pdf",
            action="store_true",
            help="Testa envio de PDF por e-mail",
        )
        parser.add_argument(
            "--pdf-url",
            default="http://127.0.0.1:8000/lotes/1/graficos/exportar/pdf/?periodo=personalizado&data_inicio=2026-01-16&data_fim=2026-02-15",
            help="URL pública do PDF para envio por e-mail",
        )

    def handle(self, *args, **options):
        if not options["to_email"]:
            raise CommandError("Informe --to com um e-mail de destino.")

        self.stdout.write("Enviando mensagem de teste por e-mail...")

        try:
            if options["enviar_pdf"]:
                resultado = enviar_relatorio_pdf_email(
                    lote=options["lote"],
                    data_inicio=options["inicio"],
                    data_fim=options["fim"],
                    consumo_litros=options["consumo"],
                    url_relatorio=options["url"],
                    url_pdf=options["pdf_url"],
                    to_email=options["to_email"],
                )
            else:
                resultado = enviar_resumo_consumo_email(
                    lote=options["lote"],
                    data_inicio=options["inicio"],
                    data_fim=options["fim"],
                    consumo_litros=options["consumo"],
                    url_relatorio=options["url"],
                    to_email=options["to_email"],
                )
        except ConfiguracaoEmailInvalida as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Erro no envio: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Mensagem enviada com sucesso."))
        self.stdout.write(f"Tipo: {resultado.get('tipo', 'texto')}")
        self.stdout.write(f"SID: {resultado['sid']}")
        self.stdout.write(f"Status inicial: {resultado['status']}")
        self.stdout.write(f"De: {resultado['from']}")
        self.stdout.write(f"Para: {resultado['to']}")
        if resultado.get("erro_pdf"):
            self.stdout.write(f"Aviso fallback PDF: {resultado['erro_pdf']}")
