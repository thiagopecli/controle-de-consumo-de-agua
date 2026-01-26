import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hidrometro_project.settings')
django.setup()

from consumo.models import Leitura, Hidrometro
from django.utils import timezone
from datetime import timedelta

print("=" * 80)
print("TESTE: SIMULANDO LÓGICA DA VIEW graficos_consumo")
print("=" * 80)

hoje = timezone.now()
ano_atual = hoje.year

# Período do ano atual: de 1º de janeiro até agora
data_inicio_ano = timezone.datetime(ano_atual, 1, 1, 0, 0, 0, tzinfo=hoje.tzinfo)
data_fim = hoje

print(f"\nData atual: {hoje}")
print(f"Ano atual: {ano_atual}")
print(f"Período: {data_inicio_ano} até {data_fim}")
print()

hidrometros = Hidrometro.objects.filter(ativo=True)
print(f"Hidrômetros ativos: {hidrometros.count()}")

consumo_total_ano = 0.0
consumo_mensal = {}
consumo_por_lote = {}
consumo_periodo_manha = 0.0
consumo_periodo_tarde = 0.0

for hidro in hidrometros:
    leituras_ano = hidro.leituras.filter(
        data_leitura__gte=data_inicio_ano,
        data_leitura__lte=data_fim
    ).order_by('data_leitura')
    
    if not leituras_ano.exists():
        continue
    
    print(f"\nHidrômetro {hidro.numero} (Lote {hidro.lote.numero}): {leituras_ano.count()} leituras")
    
    for i in range(1, len(leituras_ano)):
        leitura_atual = leituras_ano[i]
        leitura_anterior = leituras_ano[i - 1]
        
        consumo_m3 = float(leitura_atual.leitura - leitura_anterior.leitura)
        if consumo_m3 < 0:
            print(f"  AVISO: Consumo negativo ignorado!")
            continue
        
        consumo_litros = consumo_m3 * 1000
        consumo_total_ano += consumo_litros
        
        print(f"  {leitura_anterior.data_leitura.strftime('%d/%m %H:%M')} ({leitura_anterior.leitura}m³) -> {leitura_atual.data_leitura.strftime('%d/%m %H:%M')} ({leitura_atual.leitura}m³) = {consumo_litros}L ({leitura_atual.periodo})")
        
        # Consumo por lote
        numero_lote = hidro.lote.numero
        consumo_por_lote.setdefault(numero_lote, 0.0)
        consumo_por_lote[numero_lote] += consumo_litros
        
        # Consumo por mês
        mes_key = (leitura_atual.data_leitura.year, leitura_atual.data_leitura.month)
        consumo_mensal.setdefault(mes_key, 0.0)
        consumo_mensal[mes_key] += consumo_litros
        
        # Consumo por período
        if leitura_atual.periodo == 'manha':
            consumo_periodo_manha += consumo_litros
        elif leitura_atual.periodo == 'tarde':
            consumo_periodo_tarde += consumo_litros

print("\n" + "=" * 80)
print("RESULTADOS")
print("=" * 80)
print(f"\nCONSUMO TOTAL DO ANO {ano_atual}: {consumo_total_ano:,.2f} L")
print(f"Consumo Manhã: {consumo_periodo_manha:,.2f} L")
print(f"Consumo Tarde: {consumo_periodo_tarde:,.2f} L")

print("\nConsumo por mês:")
nomes_meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
for (ano, mes), valor in sorted(consumo_mensal.items()):
    print(f"  {nomes_meses[mes - 1]}/{str(ano)[-2:]}: {valor:,.2f} L")

print("\nTop 10 Lotes:")
top_lotes = sorted(consumo_por_lote.items(), key=lambda x: x[1], reverse=True)[:10]
for i, (lote, consumo) in enumerate(top_lotes, 1):
    print(f"  {i}. Lote {lote}: {consumo:,.2f} L")
