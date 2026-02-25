#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hidrometro_project.settings')
django.setup()

from django.core.management import call_command
from io import StringIO

# Executar testes
out = StringIO()
try:
    call_command('test', 'consumo.tests', verbosity=2, stdout=out, stderr=out)
    output = out.getvalue()
except Exception as e:
    output = f"Error: {str(e)}\n{out.getvalue()}"

# Salvar resultado
with open('test_results.txt', 'w') as f:
    f.write(output)

# Exibir
print("Test execution completed")
print(output[-2000:] if len(output) > 2000 else output)
