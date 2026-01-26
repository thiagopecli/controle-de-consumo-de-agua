"""
Script para testar a geração de gráficos no Excel
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hidrometro_project.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.test import RequestFactory
from consumo.views import exportar_graficos_consumo_excel, exportar_graficos_lote_excel
from consumo.models import Lote

print("🧪 Testando geração de Excel com gráficos matplotlib...")
print("=" * 60)

# Criar request factory
factory = RequestFactory()

# Teste 1: Exportar gráficos do condomínio
print("\n1️⃣ Testando exportação de gráficos do condomínio...")
request = factory.get('/exportar-graficos-consumo-excel/', {'periodo': '15dias'})
try:
    response = exportar_graficos_consumo_excel(request)
    
    if response.status_code == 200:
        filename = 'teste_excel_condominio.xlsx'
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        file_size = os.path.getsize(filename)
        print(f"   ✅ Excel do condomínio gerado: {filename}")
        print(f"   📊 Tamanho: {file_size:,} bytes")
        print(f"   📁 Localização: {os.path.abspath(filename)}")
    else:
        print(f"   ❌ Erro: Status code {response.status_code}")
except Exception as e:
    print(f"   ❌ Erro ao gerar Excel do condomínio: {str(e)}")

# Teste 2: Exportar gráficos de um lote
print("\n2️⃣ Testando exportação de gráficos de um lote...")
try:
    lote = Lote.objects.filter(ativo=True).first()
    
    if lote:
        request = factory.get(f'/exportar-graficos-lote-excel/{lote.id}/')
        response = exportar_graficos_lote_excel(request, lote.id)
        
        if response.status_code == 200:
            filename = f'teste_excel_lote_{lote.numero}.xlsx'
            with open(filename, 'wb') as f:
                f.write(response.content)
            
            file_size = os.path.getsize(filename)
            print(f"   ✅ Excel do lote {lote.numero} gerado: {filename}")
            print(f"   📊 Tamanho: {file_size:,} bytes")
            print(f"   📁 Localização: {os.path.abspath(filename)}")
        else:
            print(f"   ❌ Erro: Status code {response.status_code}")
    else:
        print("   ⚠️  Nenhum lote ativo encontrado no banco")
except Exception as e:
    print(f"   ❌ Erro ao gerar Excel do lote: {str(e)}")

print("\n" + "=" * 60)
print("✅ Testes concluídos!")
print("\n💡 Dica: Abra os arquivos .xlsx gerados para verificar os gráficos")
print("   Os gráficos agora são imagens geradas com matplotlib (iguais ao PDF)")
