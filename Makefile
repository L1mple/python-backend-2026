HOMEWORK_DIRS := $(sort $(dir $(wildcard hw*/test_*.py hw*/hw/test_*.py)))

.PHONY: sync install test test-hw1 test-hw2 lint lint-ruff lint-mypy format run-hw1 run-hw2

sync:
	uv sync
	uv run pre-commit install

install: sync

test:
	@set -e; for homework in $(HOMEWORK_DIRS); do \
		echo "Testing $$homework"; \
		(cd "$$homework" && uv run --project "$(CURDIR)" pytest); \
	done

test-hw1:
	cd hw1 && uv run --project .. pytest test_app.py

test-hw2:
	cd hw2/hw && uv run --project ../.. pytest

lint: lint-ruff lint-mypy

lint-ruff:
	uv run ruff format --check .
	uv run ruff check .

lint-mypy:
	uv run mypy hw1/app.py hw2/hw/shop_api

format:
	uv run ruff check --fix .
	uv run ruff format .

run-hw1:
	cd hw1 && uv run --project .. python app.py

run-hw2:
	uv run uvicorn hw2.hw.shop_api.main:app --reload
