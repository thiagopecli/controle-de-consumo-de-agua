from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from consumo.models import Leitura, Lote
from consumo.services.relatorios_cache import (
    calcular_data_coleta,
    caminho_pdf_lote,
    intervalo_anual_da_coleta,
    montar_url_publica_arquivo_media,
    pasta_relatorios_coleta,
)
from consumo.services.whatsapp import (
    ConfiguracaoWhatsAppInvalida,
    enviar_relatorio_pdf_whatsapp,
    enviar_resumo_consumo_whatsapp,
    normalizar_numero_whatsapp,
)


class Command(BaseCommand):
    help = "Envia resumo por WhatsApp para lotes residenciais ativos (com cache de PDFs pregerados)."

    def add_arguments(self, parser):
        parser.add_argument("--data-referencia", default=None, help="Data no formato YYYY-MM-DD (padrao: hoje)")
        parser.add_argument("--to", dest="to_whatsapp", default=None, help="Numero de destino no formato +55... ou 55...")
        parser.add_argument("--dry-run", action="store_true", help="Apenas simula o envio")
        parser.add_argument("--enviar-pdf", action="store_true", help="Envia o PDF via Z-API")
        parser.add_argument("--sem-fallback-texto", action="store_true", help="Sem fallback para texto em falha do PDF")
        parser.add_argument("--pasta-relatorios", default=None, help="Pasta com PDFs pregerados")
        parser.add_argument("--nao-usar-relatorios-pregerados", action="store_true", help="Desativa uso de cache")
        parser.add_argument("--obrigar-relatorios-pregerados", action="store_true", help="Falha se nao houver cache")

    def handle(self, *args, **options):
        data_referencia = self._resolver_data_referencia(options.get("data_referencia"))
        usar_relatorios_pregerados = not options["nao_usar_relatorios_pregerados"]
        data_coleta = calcular_data_coleta(data_referencia)
        cache_remoto_habilitado = self._cache_remoto_habilitado()

        if usar_relatorios_pregerados and not options["enviar_pdf"]:
            self.stdout.write(self.style.WARNING("[AVISO] Cache detectado: habilitando envio em PDF automaticamente."))
            options["enviar_pdf"] = True

        pasta_cache = None
        cache_obrigatorio = options["obrigar_relatorios_pregerados"] or data_referencia.day >= 20
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
            data_inicio, data_fim = intervalo_anual_da_coleta(data_coleta)
        else:
            data_inicio = data_referencia.replace(day=1)
            data_fim = data_referencia

        lotes = Lote.objects.filter(ativo=True, tipo="residencial").order_by("numero")
        if not lotes.exists():
            raise CommandError("Nenhum lote residencial ativo encontrado.")

        enviados = 0
        falhas = 0
        ignorados_sem_whatsapp = 0
        ignorados_sem_pdf_cache = 0

        origem_pdf_msg = f"cache em {pasta_cache}" if usar_relatorios_pregerados else "URL dinamica"
        self.stdout.write(
            f"Processando {lotes.count()} lotes: periodo {data_inicio.strftime('%d/%m/%Y')} ate {data_fim.strftime('%d/%m/%Y')} | Origem PDF: {origem_pdf_msg}"
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

            destinos_lote = self._resolver_destinos_lote(lote, options["to_whatsapp"])
            if not destinos_lote:
                ignorados_sem_whatsapp += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[AVISO] Lote {lote.numero} sem WhatsApp cadastrado. Cadastre telefone_whatsapp e/ou telefone_whatsapp_2"
                    )
                )
                continue

            if options["dry_run"]:
                for destino_lote in destinos_lote:
                    self.stdout.write(
                        f"[DRY-RUN] Lote {lote.numero} | WhatsApp: {destino_lote} | Consumo: {consumo_litros}L | PDF: {url_pdf}"
                    )
                enviados += 1
                continue

            envio_ok_lote = False
            for destino_lote in destinos_lote:
                try:
                    if options["enviar_pdf"]:
                        resultado = enviar_relatorio_pdf_whatsapp(
                            lote=lote.numero,
                            data_inicio=data_inicio.strftime("%d/%m/%Y"),
                            data_fim=data_fim.strftime("%d/%m/%Y"),
                            consumo_litros=consumo_litros,
                            url_relatorio=url_relatorio,
                            url_pdf=url_pdf,
                            to_whatsapp=destino_lote,
                            fallback_texto=not options["sem_fallback_texto"],
                        )
                    else:
                        resultado = enviar_resumo_consumo_whatsapp(
                            lote=lote.numero,
                            data_inicio=data_inicio.strftime("%d/%m/%Y"),
                            data_fim=data_fim.strftime("%d/%m/%Y"),
                            consumo_litros=consumo_litros,
                            url_relatorio=url_relatorio,
                            to_whatsapp=destino_lote,
                        )
                    envio_ok_lote = True
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[OK] Lote {lote.numero} enviado para {destino_lote} | Tipo: {resultado.get('tipo', 'texto')} | SID: {resultado.get('sid')}"
                        )
                    )
                except ConfiguracaoWhatsAppInvalida as exc:
                    raise CommandError(str(exc)) from exc
                except Exception as exc:
                    falhas += 1
                    self.stdout.write(self.style.ERROR(f"[ERRO] Lote {lote.numero} para {destino_lote} falhou: {exc}"))

            if envio_ok_lote:
                enviados += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Finalizado. "
                f"Enviados: {enviados} | Ignorados sem WhatsApp: {ignorados_sem_whatsapp} "
                f"| Ignorados sem PDF cache: {ignorados_sem_pdf_cache} | Falhas: {falhas}"
            )
        )

        if falhas > 0:
            raise CommandError("Execucao finalizada com falhas. Verifique os erros acima.")

    def _resolver_destinos_lote(self, lote, destino_forcado=None):
        if destino_forcado:
            return [normalizar_numero_whatsapp(destino_forcado)]

        candidatos = [
            (lote.telefone_whatsapp or "").strip(),
            (getattr(lote, "telefone_whatsapp_2", "") or "").strip(),
        ]
        candidatos = [item for item in candidatos if item]

        destinos = []
        for candidato in candidatos:
            try:
                destinos.append(normalizar_numero_whatsapp(candidato))
            except Exception:
                continue

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
            leituras = Leitura.objects.filter(
                hidrometro=hidrometro,
                data_leitura__date__gte=data_inicio,
                data_leitura__date__lte=data_fim,
            ).order_by("data_leitura")
            if leituras.count() < 2:
                continue
            primeira = leituras.first()
            ultima = leituras.last()
            if not primeira or not ultima:
                continue
            delta = ultima.leitura - primeira.leitura
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
