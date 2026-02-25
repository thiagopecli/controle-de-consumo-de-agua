#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para atualizar os defaults de período nas views
"""

with open('consumo/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all instances of '30dias' -> 'ano_atual'
content = content.replace("periodo = request.GET.get('periodo', '30dias')", "periodo = request.GET.get('periodo', 'ano_atual')")

# Replace all instances of 'mes_atual' -> 'ano_atual'
content = content.replace("periodo_selecionado = request.GET.get('periodo', 'mes_atual')", "periodo_selecionado = request.GET.get('periodo', 'ano_atual')")

with open('consumo/views.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Replacements completed successfully')
