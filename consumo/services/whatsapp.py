import json
import logging
import os
import re
import time
from pathlib import Path

import requests


LOGGER = logging.getLogger(__name__)


class ConfiguracaoWhatsAppInvalida(Exception):
    pass


class FalhaConexaoWhatsApp(RuntimeError):
    pass


def _env_bool(nome, padrao=False):
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return str(valor).strip().lower() in {"1", "true", "yes", "sim", "on"}


def _env_int(nome, padrao):
    bruto = str(os.getenv(nome, str(padrao))).strip()
    try:
        valor = int(bruto)
    except (TypeError, ValueError):
        valor = padrao
    return max(0, valor)


def _formatar_litros(valor):
    try:
        inteiro = int(float(valor))
    except (TypeError, ValueError):
        inteiro = 0
    return f"{inteiro:,}".replace(",", ".")


def _montar_mensagem_resumo_consumo(lote, data_inicio, data_fim, consumo_litros, url_relatorio):
    consumo_formatado = _formatar_litros(consumo_litros)
    return (
        f"Olá! Segue o resumo mensal de consumo de água do Lote {lote}.\n\n"
        f"📅 Período: {data_inicio} a {data_fim}\n"
        f"📊 Consumo no Período: {consumo_formatado} litros\n"
        f"⚠️Limite de consumo: 15.000 litros/mês\n\n"
        "⚠️ Esta é uma mensagem automática. Em caso de dúvidas, por favor, entre em contato diretamente com a administração.\n\n"
        "Atenciosamente,\n"
        "Condomínio Residencial Pedra de Inoã"
    )


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
        "auto_recover_on_send": _env_bool("ZAPI_AUTO_RECOVER_ON_SEND", True),
        "reconnect_attempts": max(1, _env_int("ZAPI_RECONNECT_ATTEMPTS", 2)),
        "reconnect_wait_seconds": _env_int("ZAPI_RECONNECT_WAIT_SECONDS", 3),
    }


def _zapi_url(config, path):
    return (
        "https://api.z-api.io/instances/"
        f"{config['instance_id']}/token/{config['instance_token']}/{path.lstrip('/')}"
    )


def _zapi_request(config, method, path, payload=None, timeout=30):
    headers = {
        "Client-Token": config["client_token"],
        "Content-Type": "application/json",
    }

    request_kwargs = {
        "url": _zapi_url(config, path),
        "headers": headers,
        "timeout": timeout,
    }

    if payload is not None:
        request_kwargs["data"] = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    try:
        response = requests.request(method=method.upper(), **request_kwargs)
    except requests.RequestException as exc:
        raise RuntimeError(f"Falha de comunicação com Z-API: {exc}") from exc

    try:
        data = response.json()
    except Exception:
        data = {}

    return response, data


def _mensagem_erro_zapi(response, data):
    if isinstance(data, dict):
        msg = data.get("message") or data.get("error")
        if msg:
            return str(msg)
    return response.text or "erro nao detalhado"


def _erro_indica_desconexao(message):
    texto = (message or "").strip().lower()
    if not texto:
        return False

    termos = [
        "not connected",
        "restore the session",
        "disconnected",
        "device has been disconnected",
        "you need to restore the session",
        "nao conectado",
        "desconectado",
    ]
    return any(termo in texto for termo in termos)


def _obter_status_instancia_config(config):
    response, data = _zapi_request(config, "GET", "status", timeout=20)
    if not response.ok:
        mensagem = _mensagem_erro_zapi(response, data)
        raise RuntimeError(
            f"Falha ao consultar status da instancia Z-API (HTTP {response.status_code}): {mensagem}"
        )

    return {
        "connected": bool(data.get("connected")),
        "smartphoneConnected": bool(data.get("smartphoneConnected")),
        "error": str(data.get("error") or "").strip(),
        "raw": data,
    }


def obter_status_instancia_whatsapp():
    config = _obter_configuracao_zapi()
    return _obter_status_instancia_config(config)


def _restaurar_sessao_config(config):
    response, data = _zapi_request(config, "GET", "restore-session", timeout=30)
    return bool(response.ok and (data.get("value") is True or not data))


def _reiniciar_instancia_config(config):
    response, data = _zapi_request(config, "GET", "restart", timeout=30)
    return bool(response.ok and (data.get("value") is True or not data))


def garantir_conexao_whatsapp(tentativas=None, aguardar_segundos=None):
    """
    Tenta manter/reestabelecer a conexao sem exigir novo QRCode.
    Fluxo: status -> restore-session -> status -> restart -> status.
    """
    config = _obter_configuracao_zapi()
    total_tentativas = tentativas if tentativas is not None else config["reconnect_attempts"]
    total_tentativas = max(1, int(total_tentativas))
    espera = config["reconnect_wait_seconds"] if aguardar_segundos is None else max(0, int(aguardar_segundos))

    passos = []

    for tentativa in range(1, total_tentativas + 1):
        status_inicial = _obter_status_instancia_config(config)
        passos.append({
            "tentativa": tentativa,
            "etapa": "status_inicial",
            "connected": status_inicial["connected"],
            "smartphoneConnected": status_inicial["smartphoneConnected"],
            "error": status_inicial["error"],
        })

        if status_inicial["connected"]:
            return {
                "ok": True,
                "acao": "ja_conectado",
                "status": status_inicial,
                "passos": passos,
            }

        restaurado = _restaurar_sessao_config(config)
        passos.append({"tentativa": tentativa, "etapa": "restore_session", "ok": restaurado})
        if espera:
            time.sleep(espera)

        status_pos_restore = _obter_status_instancia_config(config)
        passos.append({
            "tentativa": tentativa,
            "etapa": "status_pos_restore",
            "connected": status_pos_restore["connected"],
            "smartphoneConnected": status_pos_restore["smartphoneConnected"],
            "error": status_pos_restore["error"],
        })

        if status_pos_restore["connected"]:
            return {
                "ok": True,
                "acao": "restaurado",
                "status": status_pos_restore,
                "passos": passos,
            }

        reiniciado = _reiniciar_instancia_config(config)
        passos.append({"tentativa": tentativa, "etapa": "restart", "ok": reiniciado})
        if espera:
            time.sleep(espera)

        status_pos_restart = _obter_status_instancia_config(config)
        passos.append({
            "tentativa": tentativa,
            "etapa": "status_pos_restart",
            "connected": status_pos_restart["connected"],
            "smartphoneConnected": status_pos_restart["smartphoneConnected"],
            "error": status_pos_restart["error"],
        })

        if status_pos_restart["connected"]:
            return {
                "ok": True,
                "acao": "reiniciado",
                "status": status_pos_restart,
                "passos": passos,
            }

    ultimo_status = passos[-1] if passos else {}
    return {
        "ok": False,
        "acao": "falha_reconexao",
        "status": ultimo_status,
        "passos": passos,
    }


def garantir_conexao_whatsapp_ou_erro():
    resultado = garantir_conexao_whatsapp()
    if not resultado.get("ok"):
        raise FalhaConexaoWhatsApp(
            "Nao foi possivel reestabelecer a conexao WhatsApp pela Z-API sem nova leitura de QRCode."
        )
    return resultado


def processar_webhook_desconexao_whatsapp(payload=None):
    """
    Entrada principal para webhook de desconexao da Z-API.
    """
    resultado = garantir_conexao_whatsapp()
    if resultado.get("ok"):
        LOGGER.warning("Reconexao automatica da Z-API concluida apos webhook de desconexao.")
    else:
        LOGGER.error("Falha na reconexao automatica da Z-API apos webhook de desconexao.")
    return {
        "ok": bool(resultado.get("ok")),
        "reconexao": resultado,
        "evento": payload or {},
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

    if config["auto_recover_on_send"]:
        garantir_conexao_whatsapp_ou_erro()

    destino = normalizar_numero_whatsapp(to_whatsapp or config["to_whatsapp_padrao"])

    if not destino:
        raise ConfiguracaoWhatsAppInvalida(
            "Defina ZAPI_WHATSAPP_TO no .env ou informe o destino no envio."
        )

    mensagem = _montar_mensagem_resumo_consumo(
        lote=lote,
        data_inicio=data_inicio,
        data_fim=data_fim,
        consumo_litros=consumo_litros,
        url_relatorio=url_relatorio,
    )

    payload = {
        "phone": destino,
        "message": mensagem,
    }
    response, data = _zapi_request(config, "POST", "send-text", payload=payload, timeout=30)

    if not response.ok:
        mensagem_erro = _mensagem_erro_zapi(response, data)
        if config["auto_recover_on_send"] and _erro_indica_desconexao(mensagem_erro):
            LOGGER.warning("Falha de envio por desconexao; tentando reconectar e reenviar texto.")
            garantir_conexao_whatsapp_ou_erro()
            response, data = _zapi_request(config, "POST", "send-text", payload=payload, timeout=30)

    if not response.ok:
        mensagem_erro = _mensagem_erro_zapi(response, data)
        raise RuntimeError(
            f"Falha ao enviar mensagem para a Z-API (HTTP {response.status_code}): {mensagem_erro}"
        )

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

    if config["auto_recover_on_send"]:
        garantir_conexao_whatsapp_ou_erro()

    destino = normalizar_numero_whatsapp(to_whatsapp or config["to_whatsapp_padrao"])

    if not destino:
        raise ConfiguracaoWhatsAppInvalida(
            "Defina ZAPI_WHATSAPP_TO no .env ou informe o destino no envio."
        )

    nome_arquivo = (
        f"relatorio_lote_{lote}_{str(data_inicio).replace('/', '-')}_{str(data_fim).replace('/', '-')}.pdf"
    )
    document_ref = url_pdf
    if url_pdf and str(url_pdf).lower().endswith(".pdf"):
        caminho_local = Path(str(url_pdf))
        if caminho_local.exists() and caminho_local.is_file():
            import base64

            with open(caminho_local, "rb") as pdf_file:
                encoded_b64 = base64.b64encode(pdf_file.read()).decode("ascii")
            document_ref = f"data:application/pdf;base64,{encoded_b64}"

    # Se o documento for URL, valida previamente para evitar envio de HTML/login como "PDF".
    if isinstance(document_ref, str) and document_ref.lower().startswith(("http://", "https://")):
        try:
            response_validacao = requests.get(
                document_ref,
                timeout=30,
                allow_redirects=False,
                stream=True,
            )
        except Exception as exc:  # noqa: BLE001
            if not fallback_texto:
                raise RuntimeError(f"Falha ao validar URL do PDF antes do envio: {exc}") from exc

            resultado_texto = enviar_resumo_consumo_whatsapp(
                lote=lote,
                data_inicio=data_inicio,
                data_fim=data_fim,
                consumo_litros=consumo_litros,
                url_relatorio=url_relatorio,
                to_whatsapp=destino,
            )
            resultado_texto["tipo"] = "texto_fallback"
            resultado_texto["erro_pdf"] = f"Falha ao validar URL do PDF: {exc}"
            return resultado_texto

        try:
            content_type = (response_validacao.headers.get("Content-Type") or "").lower()
            assinatura = response_validacao.raw.read(4, decode_content=True)

            if response_validacao.status_code != 200:
                raise RuntimeError(
                    f"URL do PDF retornou status {response_validacao.status_code}."
                )

            if "application/pdf" not in content_type:
                raise RuntimeError(
                    f"URL do PDF retornou Content-Type invalido: {content_type or '-'}"
                )

            if not assinatura.startswith(b"%PDF"):
                raise RuntimeError("Conteudo da URL nao possui assinatura de PDF valida.")
        except Exception as exc:  # noqa: BLE001
            if not fallback_texto:
                raise RuntimeError(f"URL de PDF invalida para envio: {exc}") from exc

            resultado_texto = enviar_resumo_consumo_whatsapp(
                lote=lote,
                data_inicio=data_inicio,
                data_fim=data_fim,
                consumo_litros=consumo_litros,
                url_relatorio=url_relatorio,
                to_whatsapp=destino,
            )
            resultado_texto["tipo"] = "texto_fallback"
            resultado_texto["erro_pdf"] = str(exc)
            return resultado_texto
        finally:
            try:
                response_validacao.close()
            except Exception:
                pass

    payload = {
        "phone": destino,
        "document": document_ref,
        "fileName": nome_arquivo,
        "caption": _montar_mensagem_resumo_consumo(
            lote=lote,
            data_inicio=data_inicio,
            data_fim=data_fim,
            consumo_litros=consumo_litros,
            url_relatorio=url_relatorio,
        ),
    }
    response, data = _zapi_request(config, "POST", "send-document/pdf", payload=payload, timeout=30)

    if not response.ok:
        mensagem_erro = _mensagem_erro_zapi(response, data)
        if config["auto_recover_on_send"] and _erro_indica_desconexao(mensagem_erro):
            LOGGER.warning("Falha de envio de PDF por desconexao; tentando reconectar e reenviar.")
            garantir_conexao_whatsapp_ou_erro()
            response, data = _zapi_request(config, "POST", "send-document/pdf", payload=payload, timeout=30)

    if response.ok:
        if data.get("error"):
            raise RuntimeError(
                f"Falha ao enviar PDF para a Z-API: {data.get('message') or data.get('error')}"
            )

        if not (data.get("messageId") or data.get("id") or data.get("zaapId")):
            raise RuntimeError("Resposta inesperada da Z-API no envio de PDF (sem identificador de mensagem).")

        return {
            "sid": data.get("zaapId") or data.get("messageId") or data.get("id"),
            "status": data.get("status") or "sent",
            "to": destino,
            "from": data.get("from") or "z-api",
            "tipo": "pdf",
        }

    mensagem_erro = _mensagem_erro_zapi(response, data)

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
