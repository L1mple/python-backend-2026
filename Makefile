.PHONY: sync install test test-hw2 lint lint-ruff lint-mypy format run-hw2

sync:
	uv sync --locked
	uv run pre-commit install

install: sync

test: test-hw2

test-hw2:
	uv run pytest hw2/hw

lint: lint-ruff lint-mypy

lint-ruff:
	uv run ruff format --check hw2/hw/shop_api hw2/hw/tests
	uv run ruff check hw2/hw/shop_api hw2/hw/tests

lint-mypy:
	uv run mypy hw2/hw/shop_api

format:
	uv run ruff check --fix hw2/hw/shop_api hw2/hw/tests
	uv run ruff format hw2/hw/shop_api hw2/hw/tests

run-hw2:
	uv run uvicorn hw2.hw.shop_api.main:app --reload
