from datetime import datetime
import os

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from consumo.models import Lote
from consumo.services.env_guard import env_status_line, missing_required_env
from consumo.services.relatorios_cache import (
    calcular_data_coleta,
    caminho_pdf_lote,
    intervalo_mensal_da_coleta,
    pasta_relatorios_coleta,
)
from consumo.services.email import normalizar_email


class Command(BaseCommand):
    help = (
        "Precheck operacional para envio mensal por e-mail: valida variaveis, "
        "cache de PDFs (ciclo 16 a 15) e cobertura de contatos por lote."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-referencia",
            default=None,
            help="Data no formato YYYY-MM-DD (padrao: hoje)",
        )
        parser.add_argument(
            "--modo-estrito",
            action="store_true",
            help="Falha se houver qualquer pendencia critica para o envio do dia 20.",
        )
        parser.add_argument(
            "--limite-exemplos",
            type=int,
            default=10,
            help="Quantidade maxima de lotes de exemplo para cada pendencia.",
        )

    def handle(self, *args, **options):
        data_referencia = self._resolver_data_referencia(options.get("data_referencia"))
        modo_estrito = bool(options.get("modo_estrito"))
        limite_exemplos = max(1, int(options.get("limite_exemplos") or 10))

        data_coleta = calcular_data_coleta(data_referencia)
        data_inicio, data_fim = intervalo_mensal_da_coleta(data_coleta)
        pasta_cache = pasta_relatorios_coleta(data_coleta)
        cache_remoto_habilitado = self._cache_remoto_habilitado()

        self.stdout.write(
            "Precheck envio e-mail mensal | "
            f"data_referencia={data_referencia} | coleta={data_coleta} | "
            f"periodo={data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
        )

        required_env = [
            "APP_BASE_URL",
            "DEFAULT_FROM_EMAIL",
        ]
        self.stdout.write(f"Env check | {env_status_line(required_env)}")

        faltantes_env = missing_required_env(required_env)
        if faltantes_env:
            self.stdout.write(
                self.style.ERROR(
                    "[CRITICO] Variaveis obrigatorias ausentes: "
                    + ", ".join(faltantes_env)
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("[OK] Variaveis criticas presentes."))

        lotes = list(Lote.objects.filter(ativo=True, tipo="residencial").order_by("numero"))
        if not lotes:
            raise CommandError("Nenhum lote residencial ativo encontrado para precheck.")

        lotes_sem_email = []
        lotes_com_email = []
        lotes_com_email_sem_pdf = []
        lotes_com_pdf = 0

        cache_existe = pasta_cache.exists()
        if cache_existe:
            self.stdout.write(self.style.SUCCESS(f"[OK] Pasta de cache encontrada: {pasta_cache}"))
        else:
            if cache_remoto_habilitado:
                self.stdout.write(
                    self.style.WARNING(
                        f"[AVISO] Pasta de cache local nao encontrada: {pasta_cache}. "
                        "Ambiente remoto detectado via APP_BASE_URL; sem bloqueio critico por cache local."
                    )
                )
            else:
                self.stdout.write(self.style.WARNING(f"[AVISO] Pasta de cache nao encontrada: {pasta_cache}"))

        for lote in lotes:
            destinos = self._destinos_lote(lote)
            if not destinos:
                lotes_sem_email.append(lote.numero)
                continue

            lotes_com_email.append(lote.numero)
            if cache_existe:
                caminho_pdf = caminho_pdf_lote(pasta_cache, lote.numero, data_inicio, data_fim)
                if caminho_pdf.exists():
                    lotes_com_pdf += 1
                else:
                    lotes_com_email_sem_pdf.append(lote.numero)

        total_lotes = len(lotes)
        total_com_email = len(lotes_com_email)
        total_sem_email = len(lotes_sem_email)
        total_sem_pdf_cache = len(lotes_com_email_sem_pdf)

        cobertura_email = (total_com_email / total_lotes * 100.0) if total_lotes else 0.0
        cobertura_pdf_cache = (lotes_com_pdf / total_com_email * 100.0) if total_com_email else 0.0

        self.stdout.write(
            "Resumo | "
            f"lotes_residenciais={total_lotes} | com_email={total_com_email} "
            f"({cobertura_email:.1f}%) | sem_email={total_sem_email}"
        )

        if lotes_sem_email:
            exemplos = ", ".join(lotes_sem_email[:limite_exemplos])
            self.stdout.write(
                self.style.WARNING(
                    f"[AVISO] Lotes sem e-mail ({total_sem_email}). Exemplos: {exemplos}"
                )
            )

        if cache_existe:
            self.stdout.write(
                "Cache PDF | "
                f"com_email_com_pdf={lotes_com_pdf}/{total_com_email} "
                f"({cobertura_pdf_cache:.1f}%) | sem_pdf_cache={total_sem_pdf_cache}"
            )
            if lotes_com_email_sem_pdf:
                exemplos = ", ".join(lotes_com_email_sem_pdf[:limite_exemplos])
                self.stdout.write(
                    self.style.WARNING(
                        f"[AVISO] Lotes com e-mail sem PDF no cache ({total_sem_pdf_cache}). Exemplos: {exemplos}"
                    )
                )

        pendencias_criticas = []
        if faltantes_env:
            pendencias_criticas.append("variaveis_criticas_ausentes")
        if not cache_existe and not cache_remoto_habilitado:
            pendencias_criticas.append("pasta_cache_ausente")
        if total_com_email == 0:
            pendencias_criticas.append("nenhum_lote_com_email")
        if cache_existe and total_sem_pdf_cache > 0:
            pendencias_criticas.append("lotes_com_email_sem_pdf_no_cache")

        if pendencias_criticas:
            self.stdout.write(
                self.style.ERROR(
                    "Pendencias criticas detectadas: " + ", ".join(pendencias_criticas)
                )
            )
            if modo_estrito:
                raise CommandError(
                    "Precheck em modo estrito falhou. Corrija as pendencias antes do dia 20."
                )
            self.stdout.write(self.style.WARNING("Precheck concluido com pendencias (modo nao estrito)."))
            return

        self.stdout.write(self.style.SUCCESS("Precheck concluido com sucesso. Ambiente pronto para o envio do dia 20."))

    def _cache_remoto_habilitado(self):
        base_url = os.getenv("APP_BASE_URL", "").strip().lower()
        if not base_url:
            return False
        return not ("127.0.0.1" in base_url or "localhost" in base_url)

    def _resolver_data_referencia(self, valor):
        if not valor:
            return timezone.localdate()
        try:
            return datetime.strptime(valor, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError("--data-referencia deve estar no formato YYYY-MM-DD") from exc

    def _destinos_lote(self, lote):
        candidatos = [
            (getattr(lote, "email_responsavel", "") or "").strip(),
            (getattr(lote, "email_responsavel_2", "") or "").strip(),
        ]
        candidatos = [item for item in candidatos if item]

        destinos = []
        for candidato in candidatos:
            email = normalizar_email(candidato)
            if email:
                destinos.append(email)

        return list(dict.fromkeys(destinos))
