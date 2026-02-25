#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para remover também os if/elif chains para períodos não suportados
"""

with open('consumo/views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Encontrar and remover/atualizar as linhas com período antigos
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Atualizar defaults
    if "request.GET.get('periodo', 'mes_atual')" in line:
        line = line.replace("'mes_atual'", "'ano_atual'")
    elif "request.GET.get('periodo', '30dias')" in line:
        line = line.replace("'30dias'", "'ano_atual'")
    
    # Se encontrar if/elif para período remover ou manter apenas ano_atual e personalizado
    if line.strip().startswith("if periodo_selecionado == 'mes_atual':"):
        # Pular até próximo elif periodo_selecionado ou else
        i += 1
        indent_level = len(line) - len(line.lstrip())
        while i < len(lines):
            next_line = lines[i]
            next_indent = len(next_line) - len(next_line.lstrip())
            
            # Se é elif/else no mesmo nível, parar
            if next_indent <= indent_level and (next_line.strip().startswith('elif ') or next_line.strip().startswith('else:')):
                i -= 1  # Voltar para processar elif/else
                break
            i += 1
        i += 1
        continue
    
    elif line.strip().startswith("elif periodo_selecionado == '2meses':"):
        # Pular todos os meses_anteriores e próximos elif até ano_atual
        i += 1
        indent_level = len(line) - len(line.lstrip())
        while i < len(lines):
            next_line = lines[i]
            next_indent = len(next_line) - len(next_line.lstrip())
            
            if next_indent <= indent_level and next_line.strip().startswith('elif '):
                if 'ano_atual' not in next_line and 'personalizado' not in next_line:
                    i += 1
                    continue
                i -= 1
                break
            i += 1
        i += 1
        continue
        
    elif line.strip().startswith("elif periodo_selecionado == '3meses':"):
        # Similar - pular
        i += 1
        indent_level = len(line) - len(line.lstrip())
        while i < len(lines):
            next_line = lines[i]
            next_indent = len(next_line) - len(next_line.lstrip())
            
            if next_indent <= indent_level and next_line.strip().startswith('elif '):
                if 'ano_atual' not in next_line and 'personalizado' not in next_line:
                    i += 1
                    continue
                i -= 1
                break
            i += 1
        i += 1
        continue
    
    new_lines.append(line)
    i += 1

with open('consumo/views.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f'Updated {len(lines)} lines')
