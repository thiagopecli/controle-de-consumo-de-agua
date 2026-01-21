# Projeto: Sistema de Controle de Consumo de Água

## Especificações
- 310 lotes residenciais
- 10 hidrômetros adicionais para administração
- Leituras realizadas 2 vezes ao dia
- Stack: Python, Django, PostgreSQL, Django REST Framework, HTML, CSS

## Status
- [x] Criar arquivo copilot-instructions.md
- [x] Estruturar projeto Django
- [x] Criar modelos do banco de dados
- [x] Configurar Django REST Framework
- [x] Criar interface HTML/CSS
- [x] Implementar geração de gráficos
- [x] Criar documentação

## Próximos Passos
1. Iniciar PostgreSQL e criar o banco de dados `controle_agua`
2. Executar `python manage.py migrate` para aplicar as migrações
3. Executar `python manage.py createsuperuser` para criar usuário admin
4. Executar `python manage.py popular_dados` para popular com dados de exemplo
5. Executar `python manage.py runserver` para iniciar o servidor

## Estrutura do Projeto
```
controle de consumo de agua/
├── consumo/              # App principal Django
├── hidrometro_project/   # Configurações do projeto
├── templates/consumo/    # Templates HTML
├── static/               # CSS e JavaScript
├── .env                  # Variáveis de ambiente
├── requirements.txt      # Dependências Python
├── README.md            # Documentação completa
└── COMANDOS.md          # Comandos úteis
```
