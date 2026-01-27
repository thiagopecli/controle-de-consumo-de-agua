@echo off
echo ========================================
echo Populando sistema com 1 ano de dados
echo ========================================
echo.
python manage.py popular_ano_completo
echo.
echo Pressione qualquer tecla para fechar...
pause > nul
