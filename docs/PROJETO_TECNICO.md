# 📘 Documentação Técnica — Sistema de Controle de Consumo de Água

Este documento descreve a arquitetura completa, modelos, regras de negócio, API, interface web, relatórios, comandos de manutenção, configurações e diretrizes de implantação e operação do projeto.

## 1. Visão Geral
- **Objetivo:** Monitorar consumo de água em 310 lotes residenciais e 10 hidrômetros administrativos, com leituras 2x ao dia, relatórios e gráficos.
- **Stack:** Python 3.x, Django 5, Django REST Framework, PostgreSQL (produção), SQLite (dev/test), HTML/CSS/JS, Matplotlib, ReportLab, openpyxl.
- **Projeto:** `hidrometro_project` (configuração) e app `consumo` (domínio).
- **Base Web:** Interface HTML com páginas de dashboard, listagens e gráficos, além de exportação de relatórios.
- **Base API:** Endpoints REST para `Lote`, `Hidrometro`, `Leitura` + ações especializadas.

## 2. Arquitetura
- **Camada de Dados:** Modelos Django em `consumo/models.py` com relações, validações e ordenação padrão.
- **Camada de API:** ViewSets DRF em `consumo/views.py` e roteamento em `consumo/urls.py` via `DefaultRouter` (prefixo `/api/`).
- **Camada de Interface:** Views HTML em `consumo/views.py`, templates em `templates/consumo/`, estáticos em `static/` e `staticfiles/`.
- **Relatórios:** Geração de PDF e Excel em views específicas utilizando ReportLab, Matplotlib e openpyxl.
- **Comandos de Gestão:** Scripts em `consumo/management/commands/` para popular/limpar dados.
- **Configuração:** `hidrometro_project/settings.py` controla DB, estáticos, media, DRF e CORS.

Estrutura principal (resumo):
```
consumo/
  models.py       # Lote, Hidrometro, Leitura
  serializers.py  # DRF serializers, campos derivados
  views.py        # API ViewSets, ações e Views HTML
  urls.py         # Rotas HTML e API
  management/commands/*.py  # manutenção e dados
hidrometro_project/
  settings.py     # Configurações do projeto
  urls.py         # Inclusão das rotas do app
templates/consumo/  # HTML
static/               # CSS/JS
media/                # Uploads (fotos de leituras)
```

## 3. Modelagem de Dados
### 3.1 `Lote`
- `numero` (string, único): identificador do lote.
- `tipo` (enum): `residencial` ou `administracao`.
- `endereco` (opcional), `ativo` (bool), timestamps.
- Relacionamento: `hidrometros` (FK de `Hidrometro`).
- Ordenação: `numero`.

### 3.2 `Hidrometro`
- `numero` (string, único), `lote` (FK `Lote`).
- `localizacao` (opcional), `data_instalacao` (date), `ativo` (bool), `observacoes`.
- Timestamps; ordenação por `numero`.
- Métodos auxiliares: consumo diário atual (m³ e litros).

### 3.3 `Leitura`
- `hidrometro` (FK), `leitura` (decimal, m³), `data_leitura` (datetime).
- `periodo` (enum): `manha` ou `tarde`.
- `responsavel`, `observacoes`, `foto` (upload), timestamps.
- `unique_together`: (`hidrometro`, `data_leitura`, `periodo`).
- Métodos auxiliares: consumo desde última leitura (m³ e litros).

### 3.4 Índices sugeridos (produção)
- Índice composto em `Leitura(hidrometro, data_leitura)` para filtros por hidrômetro/período.
- Índice em `Leitura(periodo)` se filtragem por período for frequente.

## 4. Regras de Negócio
- Leituras realizadas 2x ao dia (`manha`, `tarde`).
- Validação de criação: leitura atual não pode ser menor que a última leitura do hidrômetro.
- Cálculo de consumo entre leituras: **m³ → litros**.
  - Fórmula: `consumo_litros = max(0, leitura_atual - leitura_anterior) * 1000`.
- Consumo por dia/mês/lote/hidrômetro: agregado a partir de deltas entre leituras ordenadas por `data_leitura`.

## 5. API REST (Resumo)
- Prefixo: `/api/` (veja documentação completa em `docs/API.md`).
- **Lotes:** CRUD, ações `hidrometros` e `consumo_total` por período.
- **Hidrometros:** CRUD, filtros (`lote`, `ativo`), ações `leituras_periodo` e `estatisticas`.
- **Leituras:** CRUD, filtros (`hidrometro`, `data_inicio`, `data_fim`, `periodo`), ações `ultimas_leituras` e `leitura_em_lote` (bulk). 
- **Busca e Ordenação:** via `SearchFilter` e `OrderingFilter` em campos relevantes.
- **Paginação:** PageNumberPagination com `PAGE_SIZE=100`.
- **Uploads:** suporte a `multipart/form-data` para `foto` de leitura.

## 6. Interface Web
### 6.1 Páginas
- `dashboard` (`/`): estatísticas agregadas do dia e totais de lotes/hidrômetros.
- `hidrometros` (`/hidrometros/`): listagem com paginação (50), contagem de leituras do dia, última leitura.
- `leituras` (`/leituras/`): listagem com paginação (50), filtro de lote (`residencial`/`administracao`).
- `registrar_leitura` (`/registrar-leitura/`): formulário para inclusão manual.
- `graficos_consumo` (`/graficos/`): gráficos do condomínio com período (7/15/30 dias, mês/ano atual, personalizado).
- `graficos_lote` (`/lotes/{id}/graficos/`): gráficos específicos do lote.

### 6.2 Gráficos
- Consumo por dia (últimos N dias), consumo por mês (acumulado), top 10 lotes, consumo por hidrômetro.
- Cálculos baseados em deltas positivos de leitura (em litros).
- Renderização: lógica Python (Matplotlib) para exportações; interface web pode usar JS para exibição (ex.: Chart.js).

## 7. Relatórios e Exportações
- **Condomínio:**
  - `exportar_graficos_consumo_pdf`: PDF com resumo, consumo diário e top 10 lotes.
  - `exportar_graficos_consumo_excel`: Excel com abas: Resumo, Consumo Diário, Top 10 Lotes, Consumo por Hidrômetro.
- **Lote específico:**
  - `exportar_graficos_lote_pdf`: PDF com consumo mensal, diário do mês vigente e distribuição por período (pizza).
  - `exportar_graficos_lote_excel`: Excel com abas: Resumo, Consumo Mensal, Consumo Diário (mês vigente).
- Bibliotecas: ReportLab (PDF), openpyxl (Excel), Matplotlib (gráficos incorporados como imagens).

## 8. Comandos de Manutenção (Management Commands)
Local: `consumo/management/commands/`
- `popular_dados.py`: popula dados exemplo básicos.
- `popular_ano_completo.py`: gera leituras para um ano completo.
- `popular_estrutura.py`: cria estrutura de lotes e hidrômetros.
- `adicionar_leituras_teste.py`: adiciona leituras de teste.
- `corrigir_leituras.py`: corrige inconsistências pontuais.
- `limpar_leituras.py`: remove leituras.
- `limpar_dados_producao.py`: limpeza de dados de produção (cautela).

Execução:
```
python manage.py popular_dados
python manage.py popular_ano_completo
python manage.py limpar_leituras
```

## 9. Configurações do Projeto
Arquivo: `hidrometro_project/settings.py`
- **DB (dev):** SQLite (`db.sqlite3`).
- **DB (prod) exemplo:** PostgreSQL — variáveis via `.env` (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`).
- **DRF:** `DEFAULT_PAGINATION_CLASS` PageNumberPagination, `PAGE_SIZE=100`, `JSONRenderer`, `BrowsableAPIRenderer`.
- **CORS:** `CORS_ALLOWED_ORIGINS` inclui `http://localhost:3000`.
- **Estáticos e Media:** `STATIC_URL`, `STATIC_ROOT`, `STATICFILES_DIRS`; `MEDIA_URL`, `MEDIA_ROOT`.
- **Internacionalização:** `LANGUAGE_CODE='pt-br'`, `TIME_ZONE='America/Sao_Paulo'`.

## 10. Implantação (Deploy)
- **Banco:** criar `controle_agua` em PostgreSQL e configurar `.env`.
- **Migrações:** `python manage.py migrate`.
- **Admin:** `python manage.py createsuperuser`.
- **Dados:** `python manage.py popular_dados` (opcional para exemplo).
- **Estáticos:** `python manage.py collectstatic --noinput`.
- **Servidor:** `python manage.py runserver` (dev) ou WSGI (prod) com reverse proxy.

## 11. Testes
- Local: `consumo/tests/` com testes para API, gráficos e views HTML.
- Execução:
```
python manage.py test consumo
```
- Coberturas principais:
  - Validação de criação de leitura (não-decrecente).
  - Bulk de leituras com retorno de sucesso/erro.
  - Últimas leituras endpoint.
  - Filtros de hidrômetro `lote` e `ativo`.
  - Ações de período e estatísticas.

## 12. Segurança e Boas Práticas (Produção)
- **Autenticação:** adicionar JWT (`django-rest-framework-simplejwt`).
- **Permissões:** `IsAuthenticated` e regras por rota; restringir `BrowsableAPIRenderer` em produção.
- **CORS:** limitar origens confiáveis.
- **Rate limiting:** throttling DRF.
- **HTTPS:** obrigatório.
- **Logs/Auditoria:** registrar alterações e acessos.

## 13. Performance
- **Querysets:** usar `select_related`/`prefetch_related` quando apropriado na API.
- **Índices:** conforme seção 3.4.
- **Paginação:** ajustar `PAGE_SIZE` conforme uso real.
- **Exportações:** preferir geração assíncrona/streaming se volumes crescerem.

## 14. Roadmap Sugerido
- Versionar API (`/api/v1/`).
- Adicionar schema OpenAPI (`drf-spectacular` ou `drf-yasg`).
- Alertas para consumo anormal e notificações.
- Integração IoT e análises preditivas.

---
**Versão do documento:** 1.0.0 · Atualizado em Jan/2026