import json
import os

import requests


class ConfiguracaoTwilioInvalida(Exception):
    pass


def _obter_configuracao_twilio():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()
    to_whatsapp_padrao = os.getenv("TWILIO_WHATSAPP_TO", "").strip()
    content_sid = os.getenv("TWILIO_CONTENT_SID", "").strip()

    campos_obrigatorios = {
        "TWILIO_ACCOUNT_SID": account_sid,
        "TWILIO_AUTH_TOKEN": auth_token,
        "TWILIO_WHATSAPP_FROM": from_whatsapp,
        "TWILIO_CONTENT_SID": content_sid,
    }

    ausentes = [nome for nome, valor in campos_obrigatorios.items() if not valor]
    if ausentes:
        raise ConfiguracaoTwilioInvalida(
            f"Variáveis não configuradas no .env: {', '.join(ausentes)}"
        )

    return {
        "account_sid": account_sid,
        "auth_token": auth_token,
        "from_whatsapp": from_whatsapp,
        "to_whatsapp_padrao": to_whatsapp_padrao,
        "content_sid": content_sid,
    }


def enviar_resumo_consumo_whatsapp(
    lote,
    data_inicio,
    data_fim,
    consumo_litros,
    url_relatorio,
    to_whatsapp=None,
):
    config = _obter_configuracao_twilio()
    destino = (to_whatsapp or config["to_whatsapp_padrao"] or "").strip()

    if not destino:
        raise ConfiguracaoTwilioInvalida(
            "Defina TWILIO_WHATSAPP_TO no .env ou informe o destino no envio."
        )

    content_variables = json.dumps(
        {
            "1": str(lote),
            "2": str(data_inicio),
            "3": str(data_fim),
            "4": str(consumo_litros),
            "5": str(url_relatorio),
        },
        ensure_ascii=False,
    )

    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{config['account_sid']}/Messages.json"
    payload = {
        "From": config["from_whatsapp"],
        "To": destino,
        "ContentSid": config["content_sid"],
        "ContentVariables": content_variables,
    }

    response = requests.post(
        endpoint,
        data=payload,
        auth=(config["account_sid"], config["auth_token"]),
        timeout=30,
    )

    if not response.ok:
        try:
            erro = response.json()
            mensagem_erro = erro.get("message") or response.text
        except Exception:
            mensagem_erro = response.text
        raise RuntimeError(
            f"Falha ao enviar mensagem para o Twilio (HTTP {response.status_code}): {mensagem_erro}"
        )

    data = response.json()
    return {
        "sid": data.get("sid"),
        "status": data.get("status"),
        "to": data.get("to"),
        "from": data.get("from"),
    }
