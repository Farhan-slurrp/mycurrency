.PHONY: help install dev migrate run test lint clean docker-up docker-down shell celery

help:
	@echo "MyCurrency - Currency Exchange Platform"
	@echo ""
	@echo "Available commands:"
	@echo "  make install      Install dependencies"
	@echo "  make dev          Set up development environment"
	@echo "  make migrate      Run database migrations"
	@echo "  make run          Start development server"
	@echo "  make test         Run tests"
	@echo "  make lint         Run linting"
	@echo "  make clean        Clean up generated files"
	@echo "  make docker-up    Start Docker services"
	@echo "  make docker-down  Stop Docker services"
	@echo "  make shell        Open Django shell"
	@echo "  make celery       Start Celery worker"
	@echo "  make load-data    Load initial fixture data"
	@echo "  make superuser    Create superuser"

install:
	pip install -r requirements.txt

# Development setup
dev: install migrate load-data
	@echo "Development environment ready!"

migrate:
	python manage.py makemigrations
	python manage.py migrate

# Run development server
run:
	python manage.py runserver

test:
	pytest -v --cov=apps --cov=adapters --cov=services

lint:
	flake8 apps adapters services tasks
	black --check apps adapters services tasks
	isort --check-only apps adapters services tasks

format:
	black apps adapters services tasks
	isort apps adapters services tasks

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-build:
	docker-compose build

# Django shell
shell:
	python manage.py shell

celery:
	celery -A config.celery worker --loglevel=info

# Celery beat scheduler
celery-beat:
	celery -A config.celery beat --loglevel=info

# Load fixture data
load-data:
	python manage.py loaddata fixtures/initial_data.json

superuser:
	python manage.py createsuperuser

# Generate historical mock data
generate-mock-data:
	python manage.py shell -c "from scripts.generate_mock_data import generate_mock_data; generate_mock_data()"
