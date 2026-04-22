import csv
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from consumo.models import Lote
from consumo.services.relatorios_cache import calcular_data_coleta, pasta_relatorios_coleta
from consumo.services.email import normalizar_email


class Command(BaseCommand):
    help = (
        "Audita lotes residenciais ativos quanto a pendencias de e-mail e "
        "gera CSV para saneamento antes do envio mensal."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-referencia",
            default=None,
            help="Data no formato YYYY-MM-DD (padrao: hoje)",
        )
        parser.add_argument(
            "--nao-salvar-csv",
            action="store_true",
            help="Somente imprime o resumo no log, sem gerar arquivo CSV.",
        )
        parser.add_argument(
            "--incluir-esperados",
            action="store_true",
            help="Inclui no CSV os casos esperados (lote sem morador e sem contato).",
        )

    def handle(self, *args, **options):
        data_referencia = self._resolver_data_referencia(options.get("data_referencia"))
        salvar_csv = not bool(options.get("nao_salvar_csv"))
        incluir_esperados = bool(options.get("incluir_esperados"))

        data_coleta = calcular_data_coleta(data_referencia)
        lotes = list(Lote.objects.filter(ativo=True, tipo="residencial").order_by("numero"))
        if not lotes:
            raise CommandError("Nenhum lote residencial ativo encontrado para auditoria.")

        pendencias = []
        total_com_contato_valido = 0
        total_sem_contato = 0
        total_sem_contato_esperado = 0
        total_sem_contato_inesperado = 0
        total_contato_invalido = 0

        for lote in lotes:
            email1 = (getattr(lote, "email_responsavel", "") or "").strip()
            email2 = (getattr(lote, "email_responsavel_2", "") or "").strip()
            morador = (lote.proprietario_nome or "").strip()
            tem_morador = bool(morador)

            has_any = bool(email1 or email2)
            validos = []

            if email1:
                n1 = normalizar_email(email1)
                if n1:
                    validos.append(n1)
            if email2:
                n2 = normalizar_email(email2)
                if n2:
                    validos.append(n2)

            if validos:
                total_com_contato_valido += 1
                continue

            if not has_any:
                total_sem_contato += 1
                tipo_pendencia = "SEM_CONTATO_INESPERADO" if tem_morador else "SEM_CONTATO_ESPERADO"
                if tem_morador:
                    total_sem_contato_inesperado += 1
                else:
                    total_sem_contato_esperado += 1
                pendencias.append(
                    {
                        "lote": lote.numero,
                        "pendencia": tipo_pendencia,
                        "email_responsavel": email1,
                        "email_responsavel_2": email2,
                        "telefone_whatsapp": (lote.telefone_whatsapp or "").strip(),
                        "telefone_whatsapp_2": (getattr(lote, "telefone_whatsapp_2", "") or "").strip(),
                        "proprietario_nome": morador,
                        "observacao": (
                            "Lote sem morador informado; contato ausente esperado"
                            if not tem_morador
                            else "Lote com morador e sem e-mail cadastrado"
                        ),
                    }
                )
            else:
                total_contato_invalido += 1
                pendencias.append(
                    {
                        "lote": lote.numero,
                        "pendencia": "FORMATO_INVALIDO",
                        "email_responsavel": email1,
                        "email_responsavel_2": email2,
                        "telefone_whatsapp": (lote.telefone_whatsapp or "").strip(),
                        "telefone_whatsapp_2": (getattr(lote, "telefone_whatsapp_2", "") or "").strip(),
                        "proprietario_nome": morador,
                        "observacao": "E-mail cadastrado em formato invalido",
                    }
                )

        total_lotes = len(lotes)
        percentual_ok = (total_com_contato_valido / total_lotes * 100.0) if total_lotes else 0.0

        self.stdout.write(
            "Auditoria e-mail | "
            f"data_referencia={data_referencia} | coleta={data_coleta} | "
            f"lotes_residenciais={total_lotes}"
        )
        self.stdout.write(
            "Resumo | "
            f"com_contato_valido={total_com_contato_valido} ({percentual_ok:.1f}%) | "
            f"sem_contato={total_sem_contato} (esperado={total_sem_contato_esperado}, inesperado={total_sem_contato_inesperado}) | "
            f"contato_invalido={total_contato_invalido}"
        )

        pendencias_csv = [
            item for item in pendencias
            if incluir_esperados or item["pendencia"] != "SEM_CONTATO_ESPERADO"
        ]

        if pendencias_csv:
            exemplos = ", ".join(item["lote"] for item in pendencias_csv[:10])
            self.stdout.write(
                self.style.WARNING(
                    f"[AVISO] Total de pendencias para acao: {len(pendencias_csv)} | Exemplos de lotes: {exemplos}"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("[OK] Nenhuma pendencia de e-mail para acao encontrada."))

        if not salvar_csv:
            return

        pasta_destino = pasta_relatorios_coleta(data_coleta)
        pasta_destino.mkdir(parents=True, exist_ok=True)

        arquivo = pasta_destino / (
            "auditoria_email_"
            f"{timezone.localtime().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        with arquivo.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=[
                    "lote",
                    "pendencia",
                    "proprietario_nome",
                    "email_responsavel",
                    "email_responsavel_2",
                    "telefone_whatsapp",
                    "telefone_whatsapp_2",
                    "observacao",
                ],
            )
            writer.writeheader()
            writer.writerows(pendencias_csv)

        self.stdout.write(self.style.SUCCESS(f"CSV de pendencias salvo em: {arquivo}"))

    def _resolver_data_referencia(self, valor):
        if not valor:
            return timezone.localdate()
        try:
            return datetime.strptime(valor, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError("--data-referencia deve estar no formato YYYY-MM-DD") from exc
