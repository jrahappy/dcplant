.PHONY: help build up down migrate test lint format clean

help:
	@echo "Available commands:"
	@echo "  make build    - Build Docker images"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make migrate  - Run database migrations"
	@echo "  make test     - Run tests"
	@echo "  make lint     - Run linting"
	@echo "  make format   - Format code"
	@echo "  make clean    - Clean up containers and volumes"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

migrate:
	docker-compose exec web python manage.py makemigrations
	docker-compose exec web python manage.py migrate

test:
	docker-compose exec web pytest

lint:
	docker-compose exec web flake8 .

format:
	docker-compose exec web black .
	docker-compose exec web isort .

clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete