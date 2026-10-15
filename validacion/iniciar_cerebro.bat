@echo off
rem Arranca el cerebro de la PC 4 (validación por IP). Dejar esta ventana abierta.
cd /d "%~dp0.."
python -m validacion.cerebro_red
pause
