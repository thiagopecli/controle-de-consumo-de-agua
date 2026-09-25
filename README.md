# Sistema de Controle de Consumo de Água

Sistema web para registrar, consultar e acompanhar leituras de hidrômetros de um condomínio, com geração de relatórios em PDF, envio mensal por email e integração opcional com Z-API/WhatsApp.

## Visão geral

- Cadastro de lotes residenciais e de uso do condomínio.
- Cadastro de hidrômetros vinculados a lotes.
- Registro de leituras nos períodos `manha` e `tarde`.
- Foto da leitura obrigatória no cadastro pela interface e pela API de criação.
- Operação offline no navegador, com armazenamento local e sincronização posterior.
- Dashboard, histórico, gráficos por período e gráficos por lote.
- Exportação de gráficos em PDF e relatórios individuais dos lotes em ZIP.
- Relatórios mensais pré-gerados e persistidos em `MEDIA_ROOT`.
- Envio mensal de relatórios por email.
- Rotinas opcionais de WhatsApp por Z-API, executadas manualmente ou por automação externa.
- API REST com paginação, busca, filtros e ordenação.

## Stack

- Python 3.12 (produção no Render) e Django 5.0.1
- PostgreSQL com `dj-database-url` e `psycopg2-binary`
- Django REST Framework 3.14
- ReportLab para PDFs
- Matplotlib para gráficos gerados no backend
- Chart.js para gráficos no navegador
- Pillow para imagens
- WhiteNoise para arquivos estáticos
- Gunicorn para produção

As versões exatas estão em [requirements.txt](requirements.txt).

## Acesso e perfis

O cadastro público está disponível em `/cadastro/`, mas o novo usuário começa com situação `pendente` e precisa ser aprovado pela administração.

- Usuários comuns: podem registrar leituras e consultar o histórico permitido.
- Administração e superusuários: acessam dashboard, hidrômetros, gráficos, relatórios e rotinas administrativas.
- Login: `/login/`, aceitando email ou telefone.
- Logout: `/logout/`.
- Administração Django: `/admin/`.

O login possui limite padrão de 5 tentativas e bloqueio temporário padrão de 900 segundos. Esses valores podem ser alterados por `LOGIN_MAX_ATTEMPTS` e `LOGIN_LOCKOUT_SECONDS`.

## Modelo de dados

### Lote

Possui número único, tipo (`residencial` ou `administracao`), endereço, proprietário, até dois telefones WhatsApp, até dois emails para relatórios e status ativo/inativo.

### Hidrômetro

Possui número serial único, lote, localização, data de instalação, observações e status ativo/inativo.

### Leitura

Possui hidrômetro, valor em m³, data/hora, período, responsável, observações e foto opcional no modelo. Na criação pela interface e pela API, a foto é obrigatória. As fotos são armazenadas em `MEDIA_ROOT/leituras/AAAA/MM/DD/`.

### Perfil de usuário

Cada usuário possui telefone de contato, tipo de acesso (`comum` ou `administracao`) e situação (`pendente`, `aprovado` ou `recusado`).

## Regras de negócio

- A leitura deve estar entre `0` e `99999.999` m³.
- Uma leitura não pode ser menor que a leitura anterior do mesmo hidrômetro.
- Não pode existir mais de uma leitura para a combinação hidrômetro, data/hora e período.
- O consumo é calculado pela diferença entre leituras consecutivas.
- O consumo diário só é calculado quando existem pelo menos duas leituras no dia.
- Os relatórios usam o ciclo mensal padrão do dia 16 do mês anterior ao dia 15 do mês de referência.
- A tela de gráficos destaca lotes que ultrapassam o limite mensal configurado de 15.000 litros.

## Instalação local

### 1. Ambiente virtual e dependências

No Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Variáveis de ambiente

Copie o modelo e edite os valores:

```powershell
Copy-Item .env.example .env
```

Para a configuração atual do projeto, use uma URL de banco:

```env
DEBUG=True
SECRET_KEY=chave-local
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
DATABASE_URL=postgresql://usuario:senha@localhost:5432/controle_agua
APP_BASE_URL=http://127.0.0.1:8000
JOB_SECRET_TOKEN=token-local
```

O arquivo `.env.example` também contém variáveis `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` e `DB_PORT`, mas `settings.py` atualmente configura o banco pela variável `DATABASE_URL`. Em PostgreSQL local, a configuração atual exige uma conexão compatível com SSL (`ssl_require=True`).

Para desenvolvimento sem um servidor SMTP, o backend de email padrão é o console do Django quando `DEBUG=True`.

### 3. Banco e aplicação

Crie o banco `controle_agua` no PostgreSQL e execute as migrações já versionadas:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`. A raiz redireciona para o dashboard ou para o login, conforme o usuário autenticado.

`makemigrations` só deve ser executado quando houver alteração nos modelos. Para uma instalação normal, não é necessário gerar novas migrações.

## Variáveis de ambiente

### Django e segurança

| Variável | Uso |
|---|---|
| `SECRET_KEY` | Chave criptográfica; obrigatória fora do modo debug. |
| `DEBUG` | Ativa recursos de desenvolvimento, incluindo a Browsable API. |
| `ALLOWED_HOSTS` | Hosts aceitos, separados por vírgula. |
| `CSRF_TRUSTED_ORIGINS` | Origens confiáveis, separadas por vírgula. |
| `APP_VERSION` | Versão exibida na aplicação. Padrão atual: `2026.03.18.1`. |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` | Comportamento seguro de cookies e HTTPS. |

### Banco e arquivos

| Variável | Uso |
|---|---|
| `DATABASE_URL` | URL de conexão do banco. |
| `MEDIA_ROOT` | Diretório de fotos e PDFs; em produção deve ser persistente. |

### Email

Para o envio mensal, configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL` e `DEFAULT_FROM_EMAIL`.

### Jobs e WhatsApp

Jobs internos exigem `JOB_SECRET_TOKEN` no header `X-Job-Token`. A integração Z-API usa `ZAPI_INSTANCE_ID`, `ZAPI_INSTANCE_TOKEN`, `ZAPI_CLIENT_TOKEN` e, opcionalmente, `ZAPI_WHATSAPP_TO`, `ZAPI_AUTO_RECOVER_ON_SEND`, `ZAPI_RECONNECT_ATTEMPTS`, `ZAPI_RECONNECT_WAIT_SECONDS` e `ZAPI_WEBHOOK_SECRET`.

Não versionar `.env` nem reutilizar segredos de produção no ambiente local.

## Interface web

| Rota | Função |
|---|---|
| `/` | Redirecionamento inicial. |
| `/dashboard/` | Indicadores e visão geral administrativa. |
| `/hidrometros/` | Lista e manutenção de hidrômetros. |
| `/registrar-leitura/` | Registro online/offline de leitura com foto. |
| `/leituras/` | Histórico e filtros de leituras. |
| `/graficos/` | Gráficos gerais e exportação em PDF. |
| `/lotes/<id>/graficos/` | Gráficos e relatório de um lote. |
| `/graficos/exportar/relatorios-lotes/` | Download em ZIP de relatórios dos lotes. |
| `/leituras/<id>/foto/` | Visualização autenticada da foto. |
| `/offline/` | Tela exibida quando a aplicação está sem conexão. |

## API REST

Base: `/api/`. Os endpoints CRUD são:

- `/api/lotes/`
- `/api/hidrometros/`
- `/api/leituras/`

Cada recurso possui operações de listagem, criação, consulta, atualização e exclusão. Também existem:

- `/api/lotes/<id>/hidrometros/`
- `/api/lotes/<id>/consumo_total/`
- `/api/hidrometros/<id>/leituras_periodo/`
- `/api/hidrometros/<id>/estatisticas/`
- `/api/leituras/ultimas_leituras/`
- `/api/leituras/leitura_em_lote/`

Filtros disponíveis incluem `search`, `lote`, `ativo`, `hidrometro`, `data_inicio`, `data_fim` e `periodo`. A ordenação usa `ordering`, e a paginação padrão é de 100 itens por página.

Para criar uma leitura, envie `multipart/form-data`, incluindo a foto:

```bash
curl -X POST http://localhost:8000/api/leituras/ \
  -F "hidrometro=1" \
  -F "leitura=125.450" \
  -F "data_leitura=2026-01-20T08:30:00" \
  -F "periodo=manha" \
  -F "responsavel=Joao Silva" \
  -F "foto=@leitura.jpg"
```

A Browsable API só fica disponível com `DEBUG=True`. Em produção, o renderer configurado é JSON. Os ViewSets não definem autenticação própria; portanto, a API deve ser protegida antes de ser exposta publicamente.

## Relatórios e automações

### Relatórios mensais

O comando de pré-geração cria PDFs em `MEDIA_ROOT/relatorios_mensais/<data>/`. A sincronização de fotos ocorre antes da geração quando necessário. O armazenamento persistente é obrigatório em produção para manter fotos e PDFs após reinicializações.

```powershell
python manage.py pregerar_relatorios_mensais --data-coleta 2026-02-15
python manage.py enviar_email_mensal --dry-run
python manage.py enviar_email_mensal
```

### WhatsApp/Z-API

O envio por WhatsApp está disponível por comandos, mas não há cron de envio WhatsApp no `render.yaml` atual. Antes do envio, use os prechecks e valide os contatos:

```powershell
python manage.py precheck_envio_whatsapp_mensal
python manage.py auditar_whatsapp_lotes
python manage.py enviar_whatsapp_mensal --dry-run --data-referencia 2026-02-20
python manage.py enviar_whatsapp_teste --to 55219SEUNUMERO
```

Também existem comandos para reconectar a instância e sincronizar fotos. Os endpoints `/jobs/...` são internos e protegidos por `X-Job-Token`; não devem ser tratados como endpoints públicos.

### Agendamento atual no Render

Conforme [render.yaml](render.yaml), o deploy possui:

- Pré-geração de relatórios: diariamente à 00:00 UTC, equivalente a 21:00 do dia anterior em Brasília.
- Precheck de email: dia 19 de cada mês, às 08:00 de Brasília.
- Envio mensal de email: dia 20 de cada mês, às 08:00 de Brasília.
- Auditoria de contatos WhatsApp: dia 18 de cada mês, às 08:00 de Brasília.

O cron de pré-geração chama `/jobs/pregerar-relatorios/` usando `APP_BASE_URL` e `JOB_SECRET_TOKEN`. Configure essas variáveis no serviço web e no cron quando aplicável.

## Comandos de manutenção

Para consultar todos os comandos disponíveis:

```powershell
python manage.py help
```

Principais comandos:

- `popular_estrutura`: cria a estrutura inicial de lotes e hidrômetros.
- `popular_dados`: insere dados de exemplo.
- `adicionar_leituras_teste`: adiciona leituras de teste.
- `popular_ano_completo`: gera leituras para o período definido pelo comando.
- `gerar_relatorios_lotes_periodo`: gera relatórios de um período.
- `sincronizar_fotos_leituras`: recupera/sincroniza fotos.
- `corrigir_leituras`: corrige leituras conforme as opções do comando.
- `limpar_leituras`, `limpar_leituras_producao` e `limpar_dados_producao`: removem dados; use somente após confirmar o ambiente e os parâmetros.

Comandos de população e limpeza podem alterar ou apagar dados. Não execute rotinas destrutivas em produção sem backup e conferência explícita.

## Deploy no Render

O arquivo [render.yaml](render.yaml) define um serviço web Django, banco PostgreSQL, disco persistente em `/var/data` e cron jobs. O serviço web executa instalação de dependências, `collectstatic`, migrações e criação opcional de superusuário.

No painel do Render, configure os segredos marcados como `sync: false`, especialmente `DATABASE_URL` quando não vier do banco definido no blueprint, `JOB_SECRET_TOKEN`, `APP_BASE_URL` e as credenciais SMTP. Para criação automática do superusuário, configure também `DJANGO_SUPERUSER_USERNAME` e `DJANGO_SUPERUSER_PASSWORD` conforme o comando usado no deploy.

## Estrutura principal

```text
consumo/                  App Django, modelos, views, API e comandos
consumo/services/         Cache de relatórios, jobs e integração WhatsApp
hidrometro_project/       Configurações Django, WSGI e ASGI
templates/consumo/        Interface HTML
static/                   CSS, JavaScript, ícones e logo
consumo/migrations/       Migrações do banco
render.yaml               Deploy e agendamentos no Render
requirements.txt          Dependências fixadas
.env.example              Modelo de configuração local
```

## Status

Versão padrão da aplicação: `2026.03.18.1`.

O projeto está em produção no Render. Antes de qualquer mudança operacional, faça backup do banco, valide as variáveis de ambiente e execute os testes:

```powershell
python manage.py test
```

Projeto de uso interno do condomínio.