#!/bin/bash

banco_local=resumebot

echo "Apagando banco $banco_local"
dropdb -Upostgres -h localhost $banco_local -e --if-exists

echo "Criando banco $banco_local"
createdb -Upostgres -h localhost $banco_local

# Exclui todos os arquivos de migração na pasta base/migrations
find chatbot/migrations -name "00*.py" -exec rm {} \;
#rm base/migrations/__pycache__/*

echo "Criando as migrações"
python manage.py makemigrations

echo "Executando as migrações"
python manage.py migrate

echo "Criando superusuário admin"
export DJANGO_SUPERUSER_USERNAME=admin
export DJANGO_SUPERUSER_EMAIL=admin@example.com
export DJANGO_SUPERUSER_PASSWORD=admin
python manage.py createsuperuser --noinput

echo "Carregando dados iniciais"
python manage.py loaddata initial_data.json

echo "Projeto resetado com sucesso."