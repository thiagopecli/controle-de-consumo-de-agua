from django import template

register = template.Library()


@register.filter
def formatar_litros(valor):
    """
    Formata valores em litros com abreviações dinâmicas (mil, mi, bi, tri)
    e remove decimais quando o valor for inteiro.
    """
    if valor is None or valor == '':
        return '—'
    
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return str(valor)

    if valor >= 1_000_000_000_000:
        trilhoes = valor / 1_000_000_000_000
        if trilhoes.is_integer():
            return f"{int(trilhoes)} tri"
        return f"{trilhoes:.1f}".replace('.', ',') + " tri"

    elif valor >= 1_000_000_000:
        bilhoes = valor / 1_000_000_000
        if bilhoes.is_integer():
            return f"{int(bilhoes)} bi"
        return f"{bilhoes:.1f}".replace('.', ',') + " bi"
        
    elif valor >= 1_000_000:
        milhoes = valor / 1_000_000
        if milhoes.is_integer():
            return f"{int(milhoes)} mi"
        return f"{milhoes:.1f}".replace('.', ',') + " mi"
        
    elif valor >= 1_000:
        mil = valor / 1_000
        if mil.is_integer():
            return f"{int(mil)} mil"
        return f"{mil:.1f}".replace('.', ',') + " mil"
    
    else:
        return f"{int(valor)}"


@register.filter
def formatar_numero(valor):
    """
    Formata qualquer número com separador de milhar.
    Exemplo: 1234567 -> 1.234.567
    """
    if valor is None or valor == '':
        return '—'
    
    try:
        # Converter para float e depois para int para remover casas decimais
        numero = int(float(valor))
        # Formatar com separador de milhar (Python usa vírgula por padrão)
        return f"{numero:,}".replace(',', '.')
    except (ValueError, TypeError):
        return str(valor)