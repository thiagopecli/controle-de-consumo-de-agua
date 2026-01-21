# Comandos Úteis - Sistema de Controle de Consumo de Água

## Ambiente Virtual

### Ativar ambiente virtual (Windows PowerShell)
```powershell
.venv\Scripts\Activate.ps1
```

### Desativar ambiente virtual
```powershell
deactivate
```

## Django

### Criar migrações
```powershell
python manage.py makemigrations
```

### Aplicar migrações
```powershell
python manage.py migrate
```

### Criar superusuário
```powershell
python manage.py createsuperuser
```

### Iniciar servidor de desenvolvimento
```powershell
python manage.py runserver
```

### Iniciar servidor em porta específica
```powershell
python manage.py runserver 8080
```

### Coletar arquivos estáticos
```powershell
python manage.py collectstatic
```

### Popular banco com dados de exemplo
```powershell
python manage.py popular_dados
```

### Shell interativo do Django
```powershell
python manage.py shell
```

## Banco de Dados PostgreSQL

### Conectar ao PostgreSQL (psql)
```powershell
psql -U postgres -d controle_agua
```

### Criar banco de dados
```sql
CREATE DATABASE controle_agua;
```

### Listar bancos de dados
```sql
\l
```

### Conectar a um banco
```sql
\c controle_agua
```

### Listar tabelas
```sql
\dt
```

### Ver estrutura de uma tabela
```sql
\d consumo_lote
\d consumo_hidrometro
\d consumo_leitura
```

### Backup do banco de dados
```powershell
pg_dump -U postgres controle_agua > backup.sql
```

### Restaurar backup
```powershell
psql -U postgres controle_agua < backup.sql
```

## Git

### Inicializar repositório
```powershell
git init
```

### Adicionar arquivos
```powershell
git add .
```

### Fazer commit
```powershell
git commit -m "Mensagem do commit"
```

### Ver status
```powershell
git status
```

### Ver histórico
```powershell
git log
```

## API - Exemplos com curl

### Listar todos os lotes
```powershell
curl http://localhost:8000/api/lotes/
```

### Criar um lote
```powershell
curl -X POST http://localhost:8000/api/lotes/ `
  -H "Content-Type: application/json" `
  -d '{\"numero\": \"999\", \"tipo\": \"residencial\", \"endereco\": \"Teste\", \"ativo\": true}'
```

### Listar hidrômetros
```powershell
curl http://localhost:8000/api/hidrometros/
```

### Criar leitura
```powershell
curl -X POST http://localhost:8000/api/leituras/ `
  -H "Content-Type: application/json" `
  -d '{\"hidrometro\": 1, \"leitura\": 125.450, \"data_leitura\": \"2026-01-20T08:30:00\", \"periodo\": \"manha\", \"responsavel\": \"João\"}'
```

### Obter estatísticas de hidrômetro
```powershell
curl http://localhost:8000/api/hidrometros/1/estatisticas/?dias=30
```

### Últimas leituras
```powershell
curl http://localhost:8000/api/leituras/ultimas_leituras/
```

## Testes

### Executar todos os testes
```powershell
python manage.py test
```

### Executar testes de um app específico
```powershell
python manage.py test consumo
```

### Executar testes com verbosidade
```powershell
python manage.py test --verbosity=2
```

## Manutenção

### Limpar cache
```powershell
python manage.py clearsessions
```

### Verificar problemas no projeto
```powershell
python manage.py check
```

### Ver informações de debug
```powershell
python manage.py diffsettings
```

## Instalação de Dependências

### Instalar dependências do requirements.txt
```powershell
pip install -r requirements.txt
```

### Atualizar pip
```powershell
python -m pip install --upgrade pip
```

### Gerar requirements.txt
```powershell
pip freeze > requirements.txt
```

## URLs Importantes

- Dashboard: http://localhost:8000/
- Admin: http://localhost:8000/admin/
- API Root: http://localhost:8000/api/
- Hidrômetros: http://localhost:8000/hidrometros/
- Registrar Leitura: http://localhost:8000/registrar-leitura/
- Gráficos: http://localhost:8000/graficos/

## Atalhos Úteis

### Ver versão do Python
```powershell
python --version
```

### Ver versão do Django
```powershell
python -m django --version
```

### Ver pacotes instalados
```powershell
pip list
```

### Verificar sintaxe de um arquivo Python
```powershell
python -m py_compile arquivo.py
```
