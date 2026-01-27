import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hidrometro_project.settings')
django.setup()

# Importar e executar o comando
from django.core.management import call_command

print("="*50)
print("Populando sistema com 1 ano de dados")
print("="*50)
print()

call_command('popular_ano_completo')

print()
print("Concluído! Pressione Enter para fechar...")
input()
