.PHONY: help install migrate makemigrations run shell test superuser clean

DJANGO_SETTINGS ?= config.settings.dev
MANAGE = python manage.py

help:
	@echo "FitTrack — comandos disponíveis:"
	@echo "  make install         Instala as dependências"
	@echo "  make migrate         Aplica as migrations"
	@echo "  make makemigrations  Gera novas migrations"
	@echo "  make run             Inicia o servidor de desenvolvimento"
	@echo "  make shell           Abre o shell do Django"
	@echo "  make test            Roda a suíte de testes"
	@echo "  make superuser       Cria um superusuário"
	@echo "  make clean           Remove arquivos de cache (.pyc, __pycache__)"

install:
	pip install -r requirements.txt

migrate:
	$(MANAGE) migrate --settings=$(DJANGO_SETTINGS)

makemigrations:
	$(MANAGE) makemigrations --settings=$(DJANGO_SETTINGS)

run:
	$(MANAGE) runserver --settings=$(DJANGO_SETTINGS)

shell:
	$(MANAGE) shell --settings=$(DJANGO_SETTINGS)

test:
	$(MANAGE) test --settings=$(DJANGO_SETTINGS)

superuser:
	$(MANAGE) createsuperuser --settings=$(DJANGO_SETTINGS)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete