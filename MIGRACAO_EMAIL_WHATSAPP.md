# Mudanças do Sistema - Migração de WhatsApp para Email

**Data**: 12 de maio de 2026  
**Status**: ✅ Concluído

## Resumo das Mudanças

O sistema de envio de relatórios foi modificado para utilizar **exclusivamente email**, removendo todas as dependências de WhatsApp via Z-API.

## O que foi modificado

### 1. ✅ Remoção de Webhooks (views.py)
- Removida função: `webhook_zapi_desconectado()`
- Removida função: `webhook_zapi_conectado()`
- Removida importação: `processar_webhook_desconexao_whatsapp`

### 2. ✅ Remoção de Rotas de Webhook (urls.py)
```python
# REMOVIDAS:
path('webhooks/zapi/disconnected/', ...) 
path('webhooks/zapi/connected/', ...)
```

### 3. ✅ Limpeza do Admin (admin.py)
- Removida classe: `LoteForm` (que normalizava telefones WhatsApp)
- Removidos campos: `telefone_whatsapp` e `telefone_whatsapp_2` do list_display
- Removidos campos da busca

### 4. ✅ Remoção de Comandos Management
Os seguintes comandos foram **removidos** pois estavam duplicados/deprecated:
- `enviar_whatsapp_mensal.py`
- `enviar_whatsapp_teste.py`
- `auditar_whatsapp_lotes.py`
- `precheck_envio_whatsapp_mensal.py`
- `reconectar_whatsapp.py`

**Substitutos recomendados:**
- Use `enviar_email_mensal` para envio de relatórios
- Use `enviar_email_teste` para testes
- Use `precheck_envio_email_mensal` para validação

## Campos do Modelo

Os campos `telefone_whatsapp` e `telefone_whatsapp_2` **foram mantidos** no modelo `Lote` para possível uso futuro em outros contextos, mas não são utilizados para envio de relatórios.

## Fluxo de Envio de Relatórios

### ✅ Novo Fluxo (Apenas Email)

```
Agendamento (Dia 15 / Dia 20)
    ↓
pregerar_relatorios_mensais.py (gera PDFs - dia 15)
    ↓
enviar_email_mensal.py (envia via email - dia 20)
    ↓
Relatório em email com opção de PDF
```

## Configurações Necessárias

Para envio de email, configure no `.env`:

```env
# Email
DEFAULT_FROM_EMAIL=relatorios@condominio.com
EMAIL_HOST=smtp.seuservidor.com
EMAIL_PORT=587
EMAIL_HOST_USER=seu_usuario
EMAIL_HOST_PASSWORD=sua_senha
EMAIL_USE_TLS=True

# App
APP_BASE_URL=https://seu-dominio.com
```

## Dados Mantidos

- ✅ Histórico de leituras
- ✅ Modelos e migrações
- ✅ Service de email intacto
- ✅ Campos de telefone no banco (desusados para relatórios)

## Dados Removidos

- ❌ Webhooks Z-API
- ❌ Rotas de webhook
- ❌ Comandos deprecados de WhatsApp
- ❌ Validação de telefone WhatsApp no admin

## Próximos Passos Opcionais

1. **Remover service de WhatsApp** (quando não for mais necessário):
   - `consumo/services/whatsapp.py` contém apenas funções deprecadas
   - Pode ser removido quando nenhum outro sistema o usar

2. **Migração de banco de dados** (opcional):
   - Os campos `telefone_whatsapp` podem ser removidos em uma migração futura
   - Não é urgente, pois não prejudicam o sistema

## Testes Recomendados

Execute o comando de teste para validar:

```bash
python manage.py enviar_email_teste --to seu@email.com --enviar-pdf
```

## Suporte

Em caso de dúvidas sobre o novo fluxo de email, consulte:
- [README.md](README.md)
- [Documentação de Relatórios](docs/PROJETO_TECNICO.md)
