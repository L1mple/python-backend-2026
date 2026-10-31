# HW5 — тесты Shop API (ДЗ-2 на Postgres из ДЗ-4) + CI

## Что сделано
1. **Покрытие 100 %** (порог 95 % зашит в `pytest.ini` через `--cov-fail-under=95`: ниже — тесты падают).
   - `tests/test_homework2.py` — тесты ДЗ-2 из репозитория курса, без изменений;
   - `tests/test_extra.py` — ветки ошибок (404 / 304), lifespan, повторное добавление товара в корзину (`quantity: 2`).
2. **CI** — `.github/workflows/hw5-tests.yml`: GitHub Actions на Python 3.13 и 3.14, Postgres 16 как `services` (с healthcheck), запуск при изменениях в `hw5/`.

## Как устроены тесты
- Тесты ходят в отдельную базу `shop_test`, а не в рабочую `shop`: `tests/conftest.py` задаёт `DATABASE_URL` до импорта приложения.
- Предохранитель: если имя базы не оканчивается на `_test`, прогон падает сразу и ничего не удаляет.
- Перед прогоном таблицы пересоздаются (`drop_all` + `create_all`) — каждый запуск с чистой базы.

## Запуск локально
~~~bash
cd hw5
docker compose up -d --wait postgres
docker compose exec postgres createdb -U shop shop_test
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
~~~
