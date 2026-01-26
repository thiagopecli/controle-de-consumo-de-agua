# 💧 Sistema de Controle de Consumo de Água

Sistema completo para gerenciamento e monitoramento de consumo de água através de hidrômetros, desenvolvido com Django, PostgreSQL e Django REST Framework.

## 📋 Características

- ✅ Gerenciamento de 310 lotes residenciais + 10 hidrômetros administrativos
- ✅ Registro de leituras 2x ao dia (Manhã e Tarde)
- ✅ API RESTful completa
- ✅ Interface web intuitiva com dashboard
- ✅ Gráficos interativos de consumo
- ✅ **Exportação de relatórios em PDF e Excel**
- ✅ Histórico completo de leituras
- ✅ Validação de dados
- ✅ Suporte a fotos de leituras

## 🛠️ Tecnologias

- **Backend:** Python 3.13, Django 5.0
- **Banco de Dados:** PostgreSQL
- **API:** Django REST Framework
- **Frontend:** HTML5, CSS3, JavaScript
- **Gráficos:** Chart.js
- **Relatórios:** ReportLab (PDF), openpyxl (Excel)
- **Outras:** Pandas, Matplotlib, Pillow

## 📚 Documentação

- [Início Rápido](docs/INICIO_RAPIDO.md) - Guia para começar rapidamente
- [Comandos Úteis](docs/COMANDOS.md) - Lista de comandos Django disponíveis
- [Documentação da API](docs/API.md) - Referência completa da API REST
- [Guia de Gráficos](docs/GUIA_USO_GRAFICOS.md) - Como usar os gráficos do sistema
- [**Exportação de Relatórios**](docs/EXPORTACAO_RELATORIOS.md) - Como exportar relatórios em PDF e Excel
- [Projeto Completo](docs/PROJETO_COMPLETO.md) - Documentação técnica completa

## 📦 Instalação

### Pré-requisitos

- Python 3.10 ou superior
- PostgreSQL 12 ou superior
- Git

### Passo a Passo

1. **Clone ou acesse o repositório:**
```bash
cd "c:\Users\Thiago Pereira\Documents\controle de consumo de agua"
```

2. **Ative o ambiente virtual (já criado):**
```powershell
.venv\Scripts\Activate.ps1
```

3. **Configure o banco de dados PostgreSQL:**

Crie o banco de dados no PostgreSQL:
```sql
CREATE DATABASE controle_agua;
CREATE USER postgres WITH PASSWORD 'sua_senha';
GRANT ALL PRIVILEGES ON DATABASE controle_agua TO postgres;
```

4. **Configure as variáveis de ambiente:**

Copie o arquivo `.env.example` para `.env`:
```powershell
Copy-Item .env.example .env
```

Edite o arquivo `.env` com suas configurações:
```env
DB_NAME=controle_agua
DB_USER=postgres
DB_PASSWORD=sua_senha_aqui
DB_HOST=localhost
DB_PORT=5432

SECRET_KEY=sua_chave_secreta_aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

5. **Execute as migrações do banco de dados:**
```powershell
python manage.py makemigrations
python manage.py migrate
```

6. **Crie um superusuário:**
```powershell
python manage.py createsuperuser
```

7. **Colete arquivos estáticos:**
```powershell
python manage.py collectstatic --noinput
```

8. **Inicie o servidor de desenvolvimento:**
```powershell
python manage.py runserver
```

Acesse: http://localhost:8000

## 📚 Estrutura do Projeto

```
controle de consumo de agua/
├── .venv/                      # Ambiente virtual Python
├── .github/
│   └── copilot-instructions.md # Instruções do projeto
├── consumo/                    # App principal
│   ├── models.py              # Modelos: Lote, Hidrometro, Leitura
│   ├── views.py               # Views e ViewSets da API
│   ├── serializers.py         # Serializers DRF
│   ├── admin.py               # Configuração do Django Admin
│   └── urls.py                # URLs da aplicação
├── hidrometro_project/        # Configurações do projeto
│   ├── settings.py            # Configurações gerais
│   ├── urls.py                # URLs principais
│   └── wsgi.py                # WSGI config
├── templates/consumo/         # Templates HTML
│   ├── base.html              # Template base
│   ├── dashboard.html         # Dashboard principal
│   ├── listar_hidrometros.html
│   ├── registrar_leitura.html
│   └── graficos_consumo.html
├── static/                    # Arquivos estáticos
│   ├── css/style.css          # Estilos CSS
│   └── js/main.js             # JavaScript
├── media/                     # Upload de arquivos
├── requirements.txt           # Dependências Python
├── .env.example              # Exemplo de variáveis de ambiente
├── .gitignore                # Arquivos ignorados pelo Git
└── README.md                 # Este arquivo
```

## 🎯 Modelos de Dados

### Lote
- Número do lote (único)
- Tipo (residencial/administração)
- Endereço
- Status (ativo/inativo)

### Hidrômetro
- Número do hidrômetro (único)
- Lote associado
- Localização
- Data de instalação
- Status (ativo/inativo)

### Leitura
- Hidrômetro
- Valor da leitura (m³)
- Data e hora
- Período (manhã/tarde)
- Responsável
- Observações
- Foto (opcional)

## 🔌 API Endpoints

### Lotes
- `GET /api/lotes/` - Listar todos os lotes
- `POST /api/lotes/` - Criar novo lote
- `GET /api/lotes/{id}/` - Detalhes de um lote
- `PUT /api/lotes/{id}/` - Atualizar lote
- `DELETE /api/lotes/{id}/` - Deletar lote
- `GET /api/lotes/{id}/hidrometros/` - Hidrômetros do lote
- `GET /api/lotes/{id}/consumo_total/` - Consumo total do lote

### Hidrômetros
- `GET /api/hidrometros/` - Listar todos os hidrômetros
- `POST /api/hidrometros/` - Criar novo hidrômetro
- `GET /api/hidrometros/{id}/` - Detalhes de um hidrômetro
- `PUT /api/hidrometros/{id}/` - Atualizar hidrômetro
- `DELETE /api/hidrometros/{id}/` - Deletar hidrômetro
- `GET /api/hidrometros/{id}/leituras_periodo/` - Leituras por período
- `GET /api/hidrometros/{id}/estatisticas/` - Estatísticas de consumo

### Leituras
- `GET /api/leituras/` - Listar todas as leituras
- `POST /api/leituras/` - Criar nova leitura
- `GET /api/leituras/{id}/` - Detalhes de uma leitura
- `PUT /api/leituras/{id}/` - Atualizar leitura
- `DELETE /api/leituras/{id}/` - Deletar leitura
- `GET /api/leituras/ultimas_leituras/` - Últimas leituras de todos os hidrômetros
- `POST /api/leituras/leitura_em_lote/` - Criar múltiplas leituras

### Filtros de Query

**Hidrômetros:**
- `?lote={id}` - Filtrar por lote
- `?ativo=true/false` - Filtrar por status

**Leituras:**
- `?hidrometro={id}` - Filtrar por hidrômetro
- `?data_inicio={data}` - Data inicial
- `?data_fim={data}` - Data final
- `?periodo=manha/tarde` - Filtrar por período

## 🌐 Interface Web

### Páginas Disponíveis

1. **Dashboard** (`/`)
   - Visão geral do sistema
   - Estatísticas principais
   - Ações rápidas

2. **Hidrômetros** (`/hidrometros/`)
   - Lista de todos os hidrômetros
   - Busca e filtros
   - Detalhes e ações

3. **Registrar Leitura** (`/registrar-leitura/`)
   - Formulário de registro
   - Validação em tempo real
   - Upload de fotos

4. **Gráficos** (`/graficos/`)
   - Consumo diário
   - Consumo acumulado
   - Consumo por período
   - Top 10 maiores consumos
   - **Exportação em PDF e Excel**

5. **Gráficos por Lote** (`/lotes/{id}/graficos/`)
   - Consumo do lote específico
   - Análise mensal e anual
   - **Exportação de relatórios individuais**

6. **Admin** (`/admin/`)
   - Painel administrativo completo
   - Gerenciamento de todos os dados

## 📊 Exemplos de Uso da API

### Criar uma leitura

```bash
curl -X POST http://localhost:8000/api/leituras/ \
  -H "Content-Type: application/json" \
  -d '{
    "hidrometro": 1,
    "leitura": 125.450,
    "data_leitura": "2026-01-20T08:30:00",
    "periodo": "manha",
    "responsavel": "João Silva"
  }'
```

### Obter estatísticas de um hidrômetro

```bash
curl http://localhost:8000/api/hidrometros/1/estatisticas/?dias=30
```

### Listar leituras de um período

```bash
curl "http://localhost:8000/api/leituras/?data_inicio=2026-01-01&data_fim=2026-01-31"
```

## 🔒 Segurança

- Validação de dados em todas as operações
- Proteção CSRF ativada
- Senhas criptografadas
- Configuração de CORS para APIs
- Variáveis de ambiente para dados sensíveis

## 🚀 Próximos Passos

Conforme mencionado, você pode adicionar:

- [ ] Autenticação JWT para API
- [ ] Notificações de consumo anormal
- [x] **Exportação de relatórios (PDF, Excel)** ✅
- [ ] Sistema de alertas por email
- [ ] Dashboard mobile responsivo
- [ ] Integração com sensores IoT
- [ ] Análise preditiva de consumo
- [ ] Relatórios personalizados

## 🤝 Contribuindo

Para contribuir com o projeto:

1. Faça um fork do repositório
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto é de uso interno do condomínio.

## 👨‍💻 Desenvolvedor

Desenvolvido com ❤️ para controle eficiente de consumo de água.

## 📞 Suporte

Para questões ou suporte:
- Abra uma issue no repositório
- Entre em contato com a administração

---

**Versão:** 1.0.0  
**Data:** Janeiro 2026  
**Status:** Em Produção ✅
