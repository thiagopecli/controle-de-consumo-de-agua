# Comandos WhatsApp Deprecados

Estes comandos foram deprecados em favor dos comandos de envio por email:

## Comandos Removidos

1. **enviar_whatsapp_mensal.py** - Use `enviar_email_mensal.py`
   - Enviava resumos de consumo via WhatsApp
   - Substituído por: `python manage.py enviar_email_mensal`

2. **enviar_whatsapp_teste.py** - Use `enviar_email_teste.py`
   - Testava envio de mensagens via WhatsApp
   - Substituído por: `python manage.py enviar_email_teste --to seu@email.com`

3. **auditar_whatsapp_lotes.py** - Use `auditar_email_lotes.py`
   - Auditava cobertura de contatos WhatsApp
   - Substituído por: `python manage.py auditar_email_lotes`

4. **precheck_envio_whatsapp_mensal.py** - Use `precheck_envio_email_mensal.py`
   - Verificava pré-requisitos para envio mensal via WhatsApp
   - Substituído por: `python manage.py precheck_envio_email_mensal`

5. **reconectar_whatsapp.py** - Já não é necessário
   - Reconectava a instância Z-API do WhatsApp
   - Removido: sistema agora usa apenas email

## Mudanças no Envio de Relatórios

A partir de [data da mudança], todos os relatórios são enviados **exclusivamente por email**:

- ✅ Email de resumo mensal
- ✅ PDF dos gráficos (opcional)
- ❌ WhatsApp (removido)

## Campos de Modelo Mantidos

Os campos `telefone_whatsapp` e `telefone_whatsapp_2` foram mantidos no modelo Lote para possível uso futuro em outros contextos, mas **não são mais usados para envio de relatórios**.

## Migração para Email

Para configurar o envio de relatórios por email, certifique-se de que:

1. `DEFAULT_FROM_EMAIL` está definido em `.env`
2. `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` estão configurados
3. Cada lote tem pelo menos um dos campos preenchidos:
   - `email_responsavel` ou
   - `email_responsavel_2`

## Contato e Suporte

Para dúvidas sobre a migração de WhatsApp para email, consulte a documentação do projeto.
