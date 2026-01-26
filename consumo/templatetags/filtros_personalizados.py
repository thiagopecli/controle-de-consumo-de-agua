from django import template

register = template.Library()


@register.filter
def formatar_litros(valor):
    """
    Formata um número de litros com separador de milhar.
    Exemplo: 1234567 -> 1.234.567
    """
    if valor is None or valor == '':
        return '—'
    
    try:
        # Converter para float e depois para int para remover casas decimais
        numero = int(float(valor))
        # Formatar com separador de milhar
        return f"{numero:,}".replace(',', '.')
    except (ValueError, TypeError):
        return str(valor)


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
