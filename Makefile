# Makefile
.PHONY: help install test lint format run clean docker-build docker-run

help:
	@echo "Доступные команды:"
	@echo "  install     - Установка зависимостей"
	@echo "  test        - Запуск тестов"
	@echo "  lint        - Проверка кода"
	@echo "  format      - Форматирование кода"
	@echo "  run         - Запуск приложения"
	@echo "  cli         - Запуск CLI"
	@echo "  clean       - Очистка временных файлов"
	@echo "  docker-build - Сборка Docker образа"
	@echo "  docker-run  - Запуск в Docker"

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v --cov=. --cov-report=html

lint:
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

format:
	black . --line-length 100
	isort . --profile black

run:
	python main.py

cli:
	python cli.py --help

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/

docker-build:
	cd docker && docker-compose build

docker-run:
	cd docker && docker-compose up -d

docker-stop:
	cd docker && docker-compose down