@echo off
REM Script para executar o sistema de controle de agua
REM Este arquivo inicia o Django server automaticamente

echo Iniciando Sistema de Controle de Agua...
echo.

REM Obter o diretorio do script
cd /d "%~dp0"

REM Ativar o virtual environment se existir
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Executar o migrate e collectstatic
echo Preparando banco de dados...
python manage.py migrate --noinput >nul 2>&1
python manage.py collectstatic --noinput >nul 2>&1

REM Iniciar o servidor
echo.
echo ========================================
echo Iniciando servidor Django...
echo Sistema disponivel em: http://localhost:8000
echo ========================================
echo.

python -c "import webbrowser; webbrowser.open('http://localhost:8000')" >nul 2>&1

python manage.py runserver 127.0.0.1:8000

pause
