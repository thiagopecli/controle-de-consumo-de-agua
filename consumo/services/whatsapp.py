import json
import os
import re

import requests


class ConfiguracaoWhatsAppInvalida(Exception):
    pass


def normalizar_numero_whatsapp(valor):
    """
    Converte formatos comuns (+55..., whatsapp:+55..., 55...)
    para o formato esperado pela Z-API (somente dígitos).
    """
    if not valor:
        return None

    numero = str(valor).strip()
    if numero.lower().startswith("whatsapp:"):
        numero = numero.split(":", 1)[1]

    numero = re.sub(r"\D", "", numero)

    if not re.fullmatch(r"\d{10,15}", numero or ""):
        return None

    return numero


def _obter_configuracao_zapi():
    instance_id = os.getenv("ZAPI_INSTANCE_ID", "").strip()
    instance_token = os.getenv("ZAPI_INSTANCE_TOKEN", "").strip()
    client_token = os.getenv("ZAPI_CLIENT_TOKEN", "").strip()
    to_whatsapp_padrao_raw = os.getenv("ZAPI_WHATSAPP_TO", "").strip()

    campos_obrigatorios = {
        "ZAPI_INSTANCE_ID": instance_id,
        "ZAPI_INSTANCE_TOKEN": instance_token,
        "ZAPI_CLIENT_TOKEN": client_token,
    }

    ausentes = [nome for nome, valor in campos_obrigatorios.items() if not valor]
    if ausentes:
        raise ConfiguracaoWhatsAppInvalida(
            f"Variáveis não configuradas no .env: {', '.join(ausentes)}"
        )

    to_whatsapp_padrao = normalizar_numero_whatsapp(to_whatsapp_padrao_raw)
    if to_whatsapp_padrao_raw and not to_whatsapp_padrao:
        raise ConfiguracaoWhatsAppInvalida(
            "ZAPI_WHATSAPP_TO inválido. Use DDI+DDD+número, ex.: 5521999999999"
        )

    return {
        "instance_id": instance_id,
        "instance_token": instance_token,
        "client_token": client_token,
        "to_whatsapp_padrao": to_whatsapp_padrao,
    }


def enviar_resumo_consumo_whatsapp(
    lote,
    data_inicio,
    data_fim,
    consumo_litros,
    url_relatorio,
    to_whatsapp=None,
):
    config = _obter_configuracao_zapi()
    destino = normalizar_numero_whatsapp(to_whatsapp or config["to_whatsapp_padrao"])

    if not destino:
        raise ConfiguracaoWhatsAppInvalida(
            "Defina ZAPI_WHATSAPP_TO no .env ou informe o destino no envio."
        )

    mensagem = (
            f"Olá! 💧 Segue o resumo mensal de consumo de água do *Lote {lote}*.\n\n"
            f"📅 *Período:* {data_inicio} a {data_fim}\n"
            f"📊 *Consumo Total:* {consumo_litros} litros\n\n"
            f"📄 *Acesse seu relatório detalhado em PDF no link abaixo:*\n"
            f"{url_relatorio}\n\n"
            f"⚠️ _Esta é uma mensagem automática. Em caso de dúvidas, por favor, entre em contato diretamente com a administração._\n\n"
            f"Atenciosamente,\n"
            f"*Condomínio Residencial Pedra de Inoã*"
    )

    endpoint = (
        "https://api.z-api.io/instances/"
        f"{config['instance_id']}/token/{config['instance_token']}/send-text"
    )
    payload = {
        "phone": destino,
        "message": mensagem,
    }
    headers = {
        "Client-Token": config["client_token"],
        "Content-Type": "application/json",
    }

    response = requests.post(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        timeout=30,
    )

    if not response.ok:
        try:
            erro = response.json()
            mensagem_erro = erro.get("message") or erro.get("error") or response.text
        except Exception:
            mensagem_erro = response.text
        raise RuntimeError(
            f"Falha ao enviar mensagem para a Z-API (HTTP {response.status_code}): {mensagem_erro}"
        )

    try:
        data = response.json()
    except Exception:
        data = {}

    return {
        "sid": data.get("zaapId") or data.get("messageId") or data.get("id"),
        "status": data.get("status") or ("sent" if response.ok else "error"),
        "to": destino,
        "from": data.get("from") or "z-api",
    }


def enviar_relatorio_pdf_whatsapp(
    lote,
    data_inicio,
    data_fim,
    consumo_litros,
    url_relatorio,
    url_pdf,
    to_whatsapp=None,
    fallback_texto=True,
):
    """
    Envia um PDF por WhatsApp via Z-API.
    Se falhar e fallback_texto=True, envia resumo em texto com link.
    """
    config = _obter_configuracao_zapi()
    destino = normalizar_numero_whatsapp(to_whatsapp or config["to_whatsapp_padrao"])

    if not destino:
        raise ConfiguracaoWhatsAppInvalida(
            "Defina ZAPI_WHATSAPP_TO no .env ou informe o destino no envio."
        )

    endpoint = (
        "https://api.z-api.io/instances/"
        f"{config['instance_id']}/token/{config['instance_token']}/send-document"
    )
    nome_arquivo = (
        f"relatorio_lote_{lote}_{str(data_inicio).replace('/', '-')}_{str(data_fim).replace('/', '-')}.pdf"
    )
    payload = {
        "phone": destino,
        "document": url_pdf,
        "fileName": nome_arquivo,
        "caption": (
            f"Relatório PDF do lote {lote} ({data_inicio} até {data_fim}). "
            f"Consumo: {consumo_litros} litros."
        ),
    }
    headers = {
        "Client-Token": config["client_token"],
        "Content-Type": "application/json",
    }

    response = requests.post(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        timeout=30,
    )

    if response.ok:
        try:
            data = response.json()
        except Exception:
            data = {}
        return {
            "sid": data.get("zaapId") or data.get("messageId") or data.get("id"),
            "status": data.get("status") or "sent",
            "to": destino,
            "from": data.get("from") or "z-api",
            "tipo": "pdf",
        }

    try:
        erro = response.json()
        mensagem_erro = erro.get("message") or erro.get("error") or response.text
    except Exception:
        mensagem_erro = response.text

    if not fallback_texto:
        raise RuntimeError(
            f"Falha ao enviar PDF para a Z-API (HTTP {response.status_code}): {mensagem_erro}"
        )

    resultado_texto = enviar_resumo_consumo_whatsapp(
        lote=lote,
        data_inicio=data_inicio,
        data_fim=data_fim,
        consumo_litros=consumo_litros,
        url_relatorio=url_relatorio,
        to_whatsapp=destino,
    )
    resultado_texto["tipo"] = "texto_fallback"
    resultado_texto["erro_pdf"] = mensagem_erro
    return resultado_texto


# Alias para compatibilidade com imports legados.
ConfiguracaoTwilioInvalida = ConfiguracaoWhatsAppInvalida
