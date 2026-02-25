"""
Demonstração da correção do bug de filtro de período "últimos 2 meses".

ANTES DA CORREÇÃO:
- Filtrava leituras desde 01/01/2026 até 15/02/2026
- Não incluía a última leitura ANTES de 01/01/2026 (ex: 31/12/2025)
- Resultado: Consumo de janeiro não era calculado (sem leitura de comparação)
- Gráfico mostrava apenas fevereiro

DEPOIS DA CORREÇÃO:
- Busca a última leitura ANTES do período (ex: 31/12/2025)
- Combina com as leituras do período (01/01 até 15/02)
- Calcula consumo corretamente: diferença entre leituras consecutivas
- Só contabiliza se a leitura ATUAL estiver dentro do período
- Gráfico mostra janeiro E fevereiro corretamente
"""

# Simulação do cálculo de período
from datetime import datetime

def _inicio_mes_menos(data_referencia, meses_anteriores):
    """Calcula início do período X meses antes."""
    total_meses = data_referencia.year * 12 + (data_referencia.month - 1) - meses_anteriores
    ano = total_meses // 12
    mes = (total_meses % 12) + 1
    return data_referencia.replace(year=ano, month=mes, day=1)

# Exemplo: última coleta em 15/02/2026, filtro "últimos 2 meses"
hoje = datetime(2026, 2, 15)
print(f"Data da última coleta: {hoje.strftime('%d/%m/%Y')}")

# Para "2meses", calcula _inicio_mes_menos(hoje, 1)
data_inicio = _inicio_mes_menos(hoje, 1)
print(f"Início do período (2 meses): {data_inicio.strftime('%d/%m/%Y')}")
print(f"Fim do período: {hoje.strftime('%d/%m/%Y')}")

print("\n✅ CORREÇÃO APLICADA:")
print("1. Busca última leitura ANTES de 01/01/2026 (ex: 31/12/2025)")
print("2. Combina com leituras de 01/01/2026 até 15/02/2026")
print("3. Calcula consumo entre leituras consecutivas (31/12 → 01/01, 01/01 → 15/01, etc.)")
print("4. Só contabiliza consumo se leitura_atual >= 01/01/2026")
print("5. Resultado: JANEIRO e FEVEREIRO aparecem no gráfico!")
