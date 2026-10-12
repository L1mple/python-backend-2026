.PHONY: sync install test test-hw2 test-hw4 lint lint-ruff lint-mypy format run-hw2 up-hw3 down-hw3 demo-hw3 up-hw4 down-hw4 db-hw4 demo-hw4

sync:
	uv sync --locked
	uv run pre-commit install

install: sync

test: test-hw2

test-hw2:
	uv run pytest hw2/hw

lint: lint-ruff lint-mypy

lint-ruff:
	uv run ruff format --check hw2/hw/shop_api hw2/hw/conftest.py hw2/hw/tests hw3 hw4
	uv run ruff check hw2/hw/shop_api hw2/hw/conftest.py hw2/hw/tests hw3 hw4

lint-mypy:
	uv run mypy hw2/hw/shop_api hw3 hw4

format:
	uv run ruff check --fix hw2/hw/shop_api hw2/hw/conftest.py hw2/hw/tests hw3 hw4
	uv run ruff format hw2/hw/shop_api hw2/hw/conftest.py hw2/hw/tests hw3 hw4

run-hw2:
	uv run uvicorn hw2.hw.shop_api.main:app --reload

up-hw3:
	docker compose up --build -d --wait

down-hw3:
	docker compose down

demo-hw3:
	uv run python hw3/generate_traffic.py

up-hw4:
	docker compose up --build -d --wait

down-hw4:
	docker compose down

db-hw4:
	docker compose up -d --wait postgres

demo-hw4:
	uv run python hw4/isolation_demo.py

test-hw4: db-hw4
	HW4_TEST_DATABASE_URL=postgresql+psycopg://shop:shop@127.0.0.1:7432/shop uv run pytest hw2/hw
	$(MAKE) demo-hw4
