from __future__ import annotations

import os
from pathlib import Path

import requests
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email


class ConfiguracaoEmailInvalida(Exception):
    pass


def normalizar_email(valor):
    if not valor:
        return None

    email = str(valor).strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


def _formatar_litros(valor):
    try:
        inteiro = int(float(valor))
    except (TypeError, ValueError):
        inteiro = 0
    return f"{inteiro:,}".replace(",", ".")


def _montar_assunto(lote, data_inicio, data_fim):
    return f"Relatório de consumo de água - Lote {lote} ({data_inicio} a {data_fim})"


def _montar_corpo_email(lote, data_inicio, data_fim, consumo_litros, url_relatorio):
    consumo_formatado = _formatar_litros(consumo_litros)
    return (
        f"Olá! Segue o resumo mensal de consumo de água do Lote {lote}.\n\n"
        f"Período: {data_inicio} a {data_fim}\n"
        f"Consumo no período: {consumo_formatado} litros\n"
        "Limite mensal: 15.000 litros, valores excedentes sujeitos a cobrança.\n\n"
        "Esta é uma mensagem automática. Em caso de dúvidas, entre em contato com a administração.\n\n"
        "Atenciosamente,\n"
        "Condomínio Residencial Pedra de Inoã"
    )


def _obter_email_remetente():
    remetente = (os.getenv("DEFAULT_FROM_EMAIL") or "").strip()
    if not remetente:
        raise ConfiguracaoEmailInvalida("Defina DEFAULT_FROM_EMAIL no ambiente.")

    email_normalizado = normalizar_email(remetente)
    if not email_normalizado:
        raise ConfiguracaoEmailInvalida("DEFAULT_FROM_EMAIL inválido.")

    return email_normalizado


def _obter_pdf_bytes(url_pdf):
    if not url_pdf:
        return None

    caminho_local = Path(str(url_pdf))
    if caminho_local.exists() and caminho_local.is_file():
        return caminho_local.read_bytes()

    if isinstance(url_pdf, str) and str(url_pdf).lower().startswith(("http://", "https://")):
        response = requests.get(url_pdf, timeout=30)
        response.raise_for_status()

        content_type = (response.headers.get("Content-Type") or "").lower()
        payload = response.content
        if "application/pdf" not in content_type and not payload.startswith(b"%PDF"):
            raise RuntimeError("URL não retornou um PDF válido para anexo.")

        return payload

    return None


def enviar_resumo_consumo_email(
    lote,
    data_inicio,
    data_fim,
    consumo_litros,
    url_relatorio,
    to_email,
):
    destinatario = normalizar_email(to_email)
    if not destinatario:
        raise ConfiguracaoEmailInvalida("Destinatário de e-mail inválido.")

    remetente = _obter_email_remetente()
    subject = _montar_assunto(lote, data_inicio, data_fim)
    body = _montar_corpo_email(lote, data_inicio, data_fim, consumo_litros, url_relatorio)

    mensagem = EmailMessage(
        subject=subject,
        body=body,
        from_email=remetente,
        to=[destinatario],
    )
    mensagem.send(fail_silently=False)

    return {
        "sid": None,
        "status": "sent",
        "to": destinatario,
        "from": remetente,
        "tipo": "texto",
    }


def enviar_relatorio_pdf_email(
    lote,
    data_inicio,
    data_fim,
    consumo_litros,
    url_relatorio,
    url_pdf,
    to_email,
    fallback_texto=True,
):
    destinatario = normalizar_email(to_email)
    if not destinatario:
        raise ConfiguracaoEmailInvalida("Destinatário de e-mail inválido.")

    remetente = _obter_email_remetente()
    subject = _montar_assunto(lote, data_inicio, data_fim)
    body = _montar_corpo_email(lote, data_inicio, data_fim, consumo_litros, url_relatorio)

    mensagem = EmailMessage(
        subject=subject,
        body=body,
        from_email=remetente,
        to=[destinatario],
    )

    nome_arquivo = (
        f"relatorio_lote_{lote}_{str(data_inicio).replace('/', '-')}_{str(data_fim).replace('/', '-')}.pdf"
    )

    try:
        payload_pdf = _obter_pdf_bytes(url_pdf)
        if payload_pdf:
            mensagem.attach(nome_arquivo, payload_pdf, "application/pdf")
        elif not fallback_texto:
            raise RuntimeError("PDF não encontrado para anexo e fallback está desabilitado.")
    except Exception as exc:
        if not fallback_texto:
            raise

        mensagem.send(fail_silently=False)
        return {
            "sid": None,
            "status": "sent",
            "to": destinatario,
            "from": remetente,
            "tipo": "texto_fallback",
            "erro_pdf": str(exc),
        }

    mensagem.send(fail_silently=False)
    return {
        "sid": None,
        "status": "sent",
        "to": destinatario,
        "from": remetente,
        "tipo": "pdf",
    }
