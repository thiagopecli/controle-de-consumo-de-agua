# 🚀 Guia de Início Rápido

Este guia te ajudará a colocar o sistema em funcionamento rapidamente.

## ✅ Pré-requisitos

Antes de começar, certifique-se de ter instalado:

- ✅ Python 3.10+ (já configurado)
- ✅ PostgreSQL 12+ (precisa ser instalado e configurado)
- ✅ Git (opcional)

## 📝 Passo a Passo

### 1. Instalar e Configurar PostgreSQL

Se ainda não tem o PostgreSQL instalado:

1. Baixe em: https://www.postgresql.org/download/windows/
2. Durante a instalação, anote a senha do usuário `postgres`
3. Após a instalação, abra o pgAdmin ou SQL Shell (psql)

### 2. Criar o Banco de Dados

Abra o SQL Shell (psql) e execute:

```sql
CREATE DATABASE controle_agua;
```

### 3. Configurar Variáveis de Ambiente

O arquivo `.env` já está criado. Edite-o com suas configurações:

```env
DB_NAME=controle_agua
DB_USER=postgres
DB_PASSWORD=SUA_SENHA_AQUI  # ← Altere para sua senha do PostgreSQL
DB_HOST=localhost
DB_PORT=5432

SECRET_KEY=django-insecure-change-this-in-production-7knypu@wq==wa!w__oi^@!5_^kf
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. Ativar Ambiente Virtual

```powershell
.venv\Scripts\Activate.ps1
```

### 5. Aplicar Migrações

```powershell
python manage.py migrate
```

### 6. Criar Superusuário

```powershell
python manage.py createsuperuser
```

Siga as instruções na tela para criar seu usuário admin.

### 7. Popular com Dados de Exemplo (Opcional)

Para ter dados iniciais para testar:

```powershell
python manage.py popular_dados
```

Isso criará:
- 310 lotes residenciais
- 10 lotes administrativos
- 320 hidrômetros
- Leituras de exemplo dos últimos 7 dias

### 8. Iniciar o Servidor

```powershell
python manage.py runserver
```

### 9. Acessar o Sistema

Abra seu navegador e acesse:

- **Dashboard Principal:** http://localhost:8000/
- **Painel Admin:** http://localhost:8000/admin/
- **API REST:** http://localhost:8000/api/
- **Hidrômetros:** http://localhost:8000/hidrometros/
- **Registrar Leitura:** http://localhost:8000/registrar-leitura/
- **Gráficos:** http://localhost:8000/graficos/

## 🎉 Pronto!

Seu sistema está funcionando! Você pode:

1. **Explorar o Dashboard** para ver estatísticas gerais
2. **Registrar novas leituras** através do formulário
3. **Visualizar gráficos** de consumo
4. **Gerenciar dados** através do painel admin
5. **Usar a API REST** para integrações

## 🔧 Solução de Problemas

### Erro de conexão com PostgreSQL

Se aparecer erro de conexão:
1. Verifique se o PostgreSQL está rodando (procure por "PostgreSQL" nos serviços do Windows)
2. Confirme que a senha no arquivo `.env` está correta
3. Verifique se o banco `controle_agua` foi criado

### Erro ao executar migrações

Se houver erro nas migrações:
```powershell
python manage.py migrate --run-syncdb
```

### Servidor não inicia

Certifique-se de que:
1. O ambiente virtual está ativado (você deve ver `(.venv)` no prompt)
2. Todas as dependências foram instaladas: `pip install -r requirements.txt`
3. A porta 8000 não está em uso por outro programa

## 📚 Próximos Passos

Após configurar o sistema:

1. Leia o [README.md](README.md) para documentação completa
2. Consulte [COMANDOS.md](COMANDOS.md) para comandos úteis
3. Explore a API REST em http://localhost:8000/api/
4. Personalize os dados conforme suas necessidades

## 💡 Dicas

- Use o painel admin para gerenciamento rápido de dados
- A API REST aceita JSON para todas as operações
- Os gráficos são atualizados automaticamente quando você filtra por período
- Você pode fazer upload de fotos das leituras pelo formulário web ou API

## 🆘 Precisa de Ajuda?

Consulte:
- [README.md](README.md) - Documentação completa
- [COMANDOS.md](COMANDOS.md) - Lista de comandos úteis
- Django Documentation: https://docs.djangoproject.com/
- PostgreSQL Documentation: https://www.postgresql.org/docs/

---

**Boa sorte com seu sistema de controle de consumo de água! 💧**
