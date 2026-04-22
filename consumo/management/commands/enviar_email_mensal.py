from datetime import datetime
from decimal import Decimal
from pathlib import Path
import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from consumo.models import Leitura, Lote
from consumo.services.env_guard import ensure_required_env, env_status_line
from consumo.services.relatorios_cache import (
    calcular_data_coleta,
    caminho_pdf_lote,
    intervalo_mensal_da_coleta,
    montar_url_publica_arquivo_media,
    pasta_relatorios_coleta,
)
from consumo.services.email import (
    ConfiguracaoEmailInvalida,
    enviar_relatorio_pdf_email,
    enviar_resumo_consumo_email,
    normalizar_email,
)


class Command(BaseCommand):
    help = "Envia resumo por e-mail para lotes residenciais ativos (com cache de PDFs pregerados)."

    def add_arguments(self, parser):
        parser.add_argument("--data-referencia", default=None, help="Data no formato YYYY-MM-DD (padrao: hoje)")
        parser.add_argument("--to", dest="to_email", default=None, help="E-mail de destino (opcional para forcar envio)")
        parser.add_argument("--dry-run", action="store_true", help="Apenas simula o envio")
        parser.add_argument("--enviar-pdf", action="store_true", help="Envia o PDF por e-mail")
        parser.add_argument("--sem-fallback-texto", action="store_true", help="Sem fallback para texto em falha do PDF")
        parser.add_argument("--pasta-relatorios", default=None, help="Pasta com PDFs pregerados")
        parser.add_argument("--nao-usar-relatorios-pregerados", action="store_true", help="Desativa uso de cache")
        parser.add_argument("--obrigar-relatorios-pregerados", action="store_true", help="Falha se nao houver cache")
        parser.add_argument(
            "--intervalo-segundos",
            type=float,
            default=5.0,
            help="Intervalo entre envios de mensagens (padrao: 5s)",
        )

    def handle(self, *args, **options):
        required_env = ["APP_BASE_URL"]
        if not options.get("dry_run"):
            required_env.extend(["DEFAULT_FROM_EMAIL"])

        try:
            ensure_required_env(required_env, context="enviar_email_mensal")
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Env check | {env_status_line(required_env)}")

        data_referencia = self._resolver_data_referencia(options.get("data_referencia"))
        usar_relatorios_pregerados = not options["nao_usar_relatorios_pregerados"]
        intervalo_segundos = max(0.0, float(options.get("intervalo_segundos") or 0.0))
        data_coleta = calcular_data_coleta(data_referencia)
        cache_remoto_habilitado = self._cache_remoto_habilitado()

        if usar_relatorios_pregerados and not options["enviar_pdf"]:
            self.stdout.write(self.style.WARNING("[AVISO] Cache detectado: habilitando envio em PDF automaticamente."))
            options["enviar_pdf"] = True

        pasta_cache = None
        cache_obrigatorio = options["obrigar_relatorios_pregerados"]
        if usar_relatorios_pregerados:
            if options["pasta_relatorios"]:
                pasta_cache = Path(options["pasta_relatorios"]).expanduser().resolve()
            else:
                pasta_cache = pasta_relatorios_coleta(data_coleta)

            if not pasta_cache.exists():
                if cache_obrigatorio and not cache_remoto_habilitado:
                    raise CommandError(
                        "Pasta de relatorios pregerados nao encontrada: "
                        f"{pasta_cache}. Execute antes a pregeracao do dia 15."
                    )

                if cache_remoto_habilitado:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[AVISO] Pasta local nao encontrada ({pasta_cache}). Usando cache remoto por URL."
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[AVISO] Pasta local nao encontrada ({pasta_cache}). Usando URL dinamica."
                        )
                    )
                    usar_relatorios_pregerados = False

        if usar_relatorios_pregerados:
            data_inicio, data_fim = intervalo_mensal_da_coleta(data_coleta)
        else:
            data_inicio, data_fim = intervalo_mensal_da_coleta(data_coleta)

        lotes = Lote.objects.filter(ativo=True, tipo="residencial").order_by("numero")
        if not lotes.exists():
            raise CommandError("Nenhum lote residencial ativo encontrado.")

        enviados = 0
        falhas = 0
        ignorados_sem_email = 0
        ignorados_sem_pdf_cache = 0
        fallbacks_pdf_para_texto = 0
        mensagens_tentadas = 0
        mensagens_enviadas = 0
        inicio_execucao = time.monotonic()

        origem_pdf_msg = f"cache em {pasta_cache}" if usar_relatorios_pregerados else "URL dinamica"
        self.stdout.write(
            f"Processando {lotes.count()} lotes: periodo {data_inicio.strftime('%d/%m/%Y')} ate {data_fim.strftime('%d/%m/%Y')} | Origem PDF: {origem_pdf_msg} | Intervalo entre envios: {intervalo_segundos:.1f}s"
        )

        for lote in lotes:
            consumo_litros = self._calcular_consumo_lote_litros(lote, data_inicio, data_fim)
            url_relatorio = self._montar_url_relatorio(lote.pk)
            url_pdf = self._montar_url_relatorio_pdf(lote.pk, data_inicio, data_fim)

            if usar_relatorios_pregerados:
                caminho_pdf = caminho_pdf_lote(pasta_cache, lote.numero, data_inicio, data_fim)
                if not caminho_pdf.exists():
                    if cache_remoto_habilitado:
                        url_pdf = montar_url_publica_arquivo_media(caminho_pdf)
                    elif cache_obrigatorio:
                        ignorados_sem_pdf_cache += 1
                        self.stdout.write(self.style.WARNING(f"[AVISO] Lote {lote.numero} sem PDF no cache ({caminho_pdf})."))
                        continue
                    else:
                        self.stdout.write(self.style.WARNING(f"[AVISO] Lote {lote.numero} sem PDF no cache. Usando URL dinamica."))
                else:
                    url_pdf = montar_url_publica_arquivo_media(caminho_pdf)

            destinos_lote = self._resolver_destinos_lote(lote, options["to_email"])
            if not destinos_lote:
                ignorados_sem_email += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[AVISO] Lote {lote.numero} sem e-mail cadastrado. Cadastre email_responsavel e/ou email_responsavel_2"
                    )
                )
                continue

            if options["dry_run"]:
                for destino_lote in destinos_lote:
                    self.stdout.write(
                        f"[DRY-RUN] Lote {lote.numero} | E-mail: {destino_lote} | Consumo: {consumo_litros}L | PDF: {url_pdf}"
                    )
                enviados += 1
                continue

            envio_ok_lote = False
            for indice_destino, destino_lote in enumerate(destinos_lote):
                mensagens_tentadas += 1
                try:
                    if options["enviar_pdf"]:
                        resultado = enviar_relatorio_pdf_email(
                            lote=lote.numero,
                            data_inicio=data_inicio.strftime("%d/%m/%Y"),
                            data_fim=data_fim.strftime("%d/%m/%Y"),
                            consumo_litros=consumo_litros,
                            url_relatorio=url_relatorio,
                            url_pdf=url_pdf,
                            to_email=destino_lote,
                            fallback_texto=not options["sem_fallback_texto"],
                        )
                    else:
                        resultado = enviar_resumo_consumo_email(
                            lote=lote.numero,
                            data_inicio=data_inicio.strftime("%d/%m/%Y"),
                            data_fim=data_fim.strftime("%d/%m/%Y"),
                            consumo_litros=consumo_litros,
                            url_relatorio=url_relatorio,
                            to_email=destino_lote,
                        )
                    envio_ok_lote = True
                    mensagens_enviadas += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[OK] Lote {lote.numero} enviado para {destino_lote} | Tipo: {resultado.get('tipo', 'texto')} | SID: {resultado.get('sid')}"
                        )
                    )
                    if resultado.get("tipo") == "texto_fallback":
                        fallbacks_pdf_para_texto += 1
                        erro_pdf = resultado.get("erro_pdf") or "motivo nao informado"
                        self.stdout.write(
                            self.style.WARNING(
                                f"[AVISO] Lote {lote.numero} para {destino_lote}: PDF nao enviado, fallback para texto. Motivo: {erro_pdf}"
                            )
                        )
                except ConfiguracaoEmailInvalida as exc:
                    raise CommandError(str(exc)) from exc
                except Exception as exc:
                    falhas += 1
                    self.stdout.write(self.style.ERROR(f"[ERRO] Lote {lote.numero} para {destino_lote} falhou: {exc}"))

                if intervalo_segundos > 0 and indice_destino < (len(destinos_lote) - 1):
                    time.sleep(intervalo_segundos)

            if intervalo_segundos > 0 and destinos_lote:
                time.sleep(intervalo_segundos)

            if envio_ok_lote:
                enviados += 1

        duracao_total_segundos = max(0.0, time.monotonic() - inicio_execucao)
        horas = int(duracao_total_segundos // 3600)
        minutos = int((duracao_total_segundos % 3600) // 60)
        segundos = duracao_total_segundos % 60
        media_por_mensagem = (duracao_total_segundos / mensagens_tentadas) if mensagens_tentadas > 0 else 0.0

        self.stdout.write(
            self.style.SUCCESS(
                "Finalizado. "
                f"Enviados: {enviados} | Ignorados sem e-mail: {ignorados_sem_email} "
                f"| Ignorados sem PDF cache: {ignorados_sem_pdf_cache} | Falhas: {falhas} "
                f"| Fallbacks PDF->texto: {fallbacks_pdf_para_texto} "
                f"| Mensagens enviadas: {mensagens_enviadas}/{mensagens_tentadas} "
                f"| Tempo total: {horas:02d}:{minutos:02d}:{segundos:05.2f} "
                f"| Media por mensagem: {media_por_mensagem:.2f}s"
            )
        )

        if falhas > 0:
            raise CommandError("Execucao finalizada com falhas. Verifique os erros acima.")

    def _resolver_destinos_lote(self, lote, destino_forcado=None):
        if destino_forcado:
            email_forcado = normalizar_email(destino_forcado)
            return [email_forcado] if email_forcado else []

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
            leitura_anterior_periodo = Leitura.objects.filter(
                hidrometro=hidrometro,
                data_leitura__date__lt=data_inicio,
            ).order_by("-data_leitura").first()

            leituras_periodo = list(Leitura.objects.filter(
                hidrometro=hidrometro,
                data_leitura__date__gte=data_inicio,
                data_leitura__date__lte=data_fim,
            ).order_by("data_leitura"))

            if leitura_anterior_periodo:
                leituras_para_calculo = [leitura_anterior_periodo] + leituras_periodo
            else:
                leituras_para_calculo = leituras_periodo

            for i in range(1, len(leituras_para_calculo)):
                leitura_atual = leituras_para_calculo[i]
                leitura_anterior = leituras_para_calculo[i - 1]

                if leitura_atual.data_leitura.date() < data_inicio:
                    continue

                delta = leitura_atual.leitura - leitura_anterior.leitura
                if delta > 0:
                    consumo_total_m3 += delta
        return int(consumo_total_m3 * Decimal("1000"))

    def _montar_url_relatorio(self, lote_id):
        from django.conf import settings
        import os

        base_url = getattr(settings, "APP_BASE_URL", None) or os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
        base_url = base_url.rstrip("/")
        return f"{base_url}/lotes/{lote_id}/graficos/"

    def _montar_url_relatorio_pdf(self, lote_id, data_inicio, data_fim):
        from django.conf import settings
        import os

        base_url = getattr(settings, "APP_BASE_URL", None) or os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
        base_url = base_url.rstrip("/")
        return (
            f"{base_url}/lotes/{lote_id}/graficos/exportar/pdf/"
            f"?periodo=personalizado&data_inicio={data_inicio.strftime('%Y-%m-%d')}"
            f"&data_fim={data_fim.strftime('%Y-%m-%d')}"
        )

    def _cache_remoto_habilitado(self):
        from django.conf import settings
        import os

        base_url = getattr(settings, "APP_BASE_URL", None) or os.getenv("APP_BASE_URL", "")
        base_url = (base_url or "").strip().lower()
        if not base_url:
            return False
        return not ("127.0.0.1" in base_url or "localhost" in base_url)
