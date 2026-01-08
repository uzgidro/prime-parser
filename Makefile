.PHONY: install test lint format run-dev run-prod docker-build docker-run-dev docker-run-prod clean help

help:
	@echo "Available commands:"
	@echo "  make install        - Install dependencies"
	@echo "  make test          - Run tests with coverage"
	@echo "  make lint          - Run linters (ruff + mypy)"
	@echo "  make format        - Format code (black + ruff)"
	@echo "  make run-dev       - Run dev server"
	@echo "  make run-prod      - Run prod server"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run-dev  - Run Docker container (dev)"
	@echo "  make docker-run-prod - Run Docker container (prod)"
	@echo "  make clean         - Clean temporary files"

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=src/prime_parser --cov-report=html --cov-report=term

lint:
	ruff check src/ tests/
	mypy src/ tests/

format:
	black src/ tests/
	ruff check --fix src/ tests/

run-dev:
	set ENVIRONMENT=dev && uvicorn src.prime_parser.main:app --reload --port 19779

run-prod:
	set ENVIRONMENT=prod && uvicorn src.prime_parser.main:app --host 0.0.0.0 --port 19779

docker-build:
	docker build -f docker/Dockerfile -t prime-parser:latest .

docker-run-dev:
	docker run -p 19779:19779 -e ENVIRONMENT=dev prime-parser:latest

docker-run-prod:
	docker run -p 19779:19779 -e ENVIRONMENT=prod prime-parser:latest

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>nul || true
	find . -type f -name "*.pyc" -delete 2>nul || true
	if exist .pytest_cache rmdir /s /q .pytest_cache
	if exist .coverage del .coverage
	if exist htmlcov rmdir /s /q htmlcov
	if exist .ruff_cache rmdir /s /q .ruff_cache
	if exist .mypy_cache rmdir /s /q .mypy_cache
