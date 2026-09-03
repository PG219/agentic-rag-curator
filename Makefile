.PHONY: help install dev test lint format docker-up docker-down clean

help:
	@echo "Available commands:"
	@echo "  make install      - Install project dependencies"
	@echo "  make dev          - Run local FastAPI development server"
	@echo "  make test         - Run test suite"
	@echo "  make lint         - Run linter (ruff)"
	@echo "  make format       - Format code (ruff)"
	@echo "  make docker-up    - Start PostgreSQL & OpenSearch in background"
	@echo "  make docker-down  - Stop Docker containers"
	@echo "  make clean        - Remove caches and temporary files"

install:
	pip install -e ".[dev]"

dev:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
