#!/usr/bin/env python
"""
Script para executar a aplicação Django como app desktop.
Inicia o servidor e abre o navegador automaticamente.
Para usar com PyInstaller ou diretamente com Python.
"""

import os
import sys
import time
import webbrowser
import subprocess
from pathlib import Path


def should_skip_setup() -> bool:
    """Return True when env var SKIP_SETUP is set to a truthy value."""
    value = os.environ.get('SKIP_SETUP', '').lower()
    return value in {'1', 'true', 'yes', 'on'}


def run_setup(app_dir: str) -> None:
    """Run migrate and collectstatic unless skipped."""
    if should_skip_setup():
        print("Pulando migrate/collectstatic (SKIP_SETUP=1).")
        return

    print("\nPreparando banco de dados...")
    subprocess.run([
        sys.executable, 'manage.py', 'migrate', '--noinput'
    ], cwd=app_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("Coletando arquivos estáticos...")
    subprocess.run([
        sys.executable, 'manage.py', 'collectstatic', '--noinput'
    ], cwd=app_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    """Função principal."""
    # Configurar diretório da aplicação
    if getattr(sys, 'frozen', False):
        # Executado como .exe (PyInstaller)
        app_dir = sys._MEIPASS
    else:
        # Executado como script Python
        app_dir = str(Path(__file__).parent)
    
    os.chdir(app_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hidrometro_project.settings')
    
    # Preparar banco de dados (executa apenas se nao houver SKIP_SETUP)
    print("=" * 60)
    print("INICIANDO SISTEMA DE CONTROLE DE AGUA")
    print("=" * 60)
    run_setup(app_dir)
    
    # Iniciar servidor
    print("\n" + "=" * 60)
    print("Servidor iniciando...")
    print("Acesse: http://localhost:8000")
    print("=" * 60)
    print()
    
    # Abrir navegador após curta espera (pode ser desativado com NO_BROWSER)
    if os.environ.get('NO_BROWSER', '').lower() not in {'1', 'true', 'yes', 'on'}:
        time.sleep(1.5)
        try:
            webbrowser.open('http://localhost:8000')
        except Exception:
            pass
    
    # Executar servidor Django
    fast_start = os.environ.get('FAST_START', '').lower() in {'1', 'true', 'yes', 'on'}
    use_reload = os.environ.get('USE_RELOAD', '').lower() in {'1', 'true', 'yes', 'on'}
    runserver_cmd = [
        sys.executable, 'manage.py', 'runserver', '127.0.0.1:8000'
    ]
    # Por padrao desliga autoreload/threads para evitar processos duplicados e abas extras
    if fast_start or not use_reload:
        runserver_cmd.extend(['--noreload', '--nothreading'])

    try:
        subprocess.call(runserver_cmd, cwd=app_dir)
    except KeyboardInterrupt:
        print("\n\nSistema encerrado.")
        sys.exit(0)

if __name__ == '__main__':
    main()
