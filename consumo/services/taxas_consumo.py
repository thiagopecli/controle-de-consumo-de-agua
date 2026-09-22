from decimal import Decimal


LIMITE_ISENTO_LITROS = Decimal('15000')
LIMITE_PRIMEIRA_FAIXA_LITROS = Decimal('20000')
LIMITE_SEGUNDA_FAIXA_LITROS = Decimal('25000')
VALOR_PRIMEIRA_FAIXA_M3 = Decimal('13.43')
VALOR_SEGUNDA_FAIXA_M3 = Decimal('60.00')
VALOR_TERCEIRA_FAIXA_M3 = Decimal('100.00')


def calcular_taxa_excesso(consumo_litros):
    """Calcula a taxa progressiva mensal para consumo acima de 15.000 litros."""
    consumo_litros = Decimal(str(consumo_litros or 0))
    if consumo_litros <= LIMITE_ISENTO_LITROS:
        return Decimal('0.00')

    primeira_faixa = min(consumo_litros, LIMITE_PRIMEIRA_FAIXA_LITROS) - LIMITE_ISENTO_LITROS
    segunda_faixa = min(consumo_litros, LIMITE_SEGUNDA_FAIXA_LITROS) - LIMITE_PRIMEIRA_FAIXA_LITROS
    terceira_faixa = max(consumo_litros - LIMITE_SEGUNDA_FAIXA_LITROS, Decimal('0'))

    taxa = (
        (max(primeira_faixa, Decimal('0')) / Decimal('1000')) * VALOR_PRIMEIRA_FAIXA_M3
        + (max(segunda_faixa, Decimal('0')) / Decimal('1000')) * VALOR_SEGUNDA_FAIXA_M3
        + (terceira_faixa / Decimal('1000')) * VALOR_TERCEIRA_FAIXA_M3
    )
    return taxa.quantize(Decimal('0.01'))
