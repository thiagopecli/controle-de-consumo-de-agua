import os
from datetime import date
from pathlib import Path
from urllib.parse import quote

from django.conf import settings


def calcular_data_coleta(data_referencia):
    """
    Retorna a data de coleta de referência (dia 15).

    - Se a data de referência for dia >= 15, usa dia 15 do mesmo mês.
    - Se for dia < 15, usa dia 15 do mês anterior.
    """
    if data_referencia.day >= 15:
        return data_referencia.replace(day=15)

    ano = data_referencia.year
    mes = data_referencia.month - 1
    if mes == 0:
        mes = 12
        ano -= 1

    return date(ano, mes, 15)


def intervalo_anual_da_coleta(data_coleta):
    return date(data_coleta.year, 1, 1), data_coleta


def nome_arquivo_relatorio_lote(lote_numero, data_inicio, data_fim):
    return (
        f"relatorio_lote_{lote_numero}_"
        f"{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.pdf"
    )


def pasta_relatorios_coleta(data_coleta):
    return Path(settings.MEDIA_ROOT) / "relatorios_mensais" / data_coleta.strftime("%Y-%m-%d")


def caminho_pdf_lote(pasta_base, lote_numero, data_inicio, data_fim):
    return Path(pasta_base) / nome_arquivo_relatorio_lote(lote_numero, data_inicio, data_fim)


def montar_url_publica_arquivo_media(caminho_arquivo):
    base_url = getattr(settings, "APP_BASE_URL", None)
    if not base_url:
        base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
    base_url = base_url.rstrip("/")

    media_root = Path(settings.MEDIA_ROOT).resolve()
    caminho_abs = Path(caminho_arquivo).resolve()
    rel_media = caminho_abs.relative_to(media_root).as_posix()
    rel_media = quote(rel_media, safe="/")

    media_url = settings.MEDIA_URL.strip("/")
    return f"{base_url}/{media_url}/{rel_media}"
