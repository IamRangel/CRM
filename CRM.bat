@echo off
title Iniciador CRM Phd - Rangel Semi Deus
echo --------------------------------------------------
echo INICIANDO O SISTEMA CRM PHD...
echo --------------------------------------------------

:: Abrir o navegador no endereço local (espera 2 segundos para o Flask subir)
start "" "http://127.0.0.1:5000"

:: Rodar o Python (certifique-se de que o nome do arquivo e o caminho estao certos)
python app.py

pause