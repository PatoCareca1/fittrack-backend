.PHONY: help install migrate makemigrations run shell test superuser clean \
        docker-build docker-up docker-down docker-logs docker-migrate \
        docker-superuser docker-shell

DJANGO_SETTINGS ?= config.settings.dev
MANAGE = poetry run python manage.py

help:
	@echo "FitTrack — comandos disponíveis:"
	@echo ""
	@echo "  Local:"
	@echo "    make install          Instala as dependências via Poetry"
	@echo "    make run              Inicia o servidor de desenvolvimento"
	@echo "    make migrate          Aplica as migrations"
	@echo "    make makemigrations   Gera novas migrations"
	@echo "    make shell            Abre o Django shell"
	@echo "    make test             Roda os testes"
	@echo "    make superuser        Cria um superusuário"
	@echo "    make clean            Remove arquivos de cache"
	@echo ""
	@echo "  Docker:"
	@echo "    make docker-build     Builda as imagens"
	@echo "    make docker-up        Sobe os containers em background"
	@echo "    make docker-down      Derruba os containers"
	@echo "    make docker-logs      Exibe logs do container web"
	@echo "    make docker-migrate   Roda migrate dentro do container"
	@echo "    make docker-superuser Cria superusuário dentro do container"
	@echo "    make docker-shell     Abre o Django shell dentro do container"

install:
	poetry install

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

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f web

docker-migrate:
	docker compose exec web python manage.py migrate

docker-superuser:
	docker compose exec web python manage.py createsuperuser

docker-shell:
	docker compose exec web python manage.py shell