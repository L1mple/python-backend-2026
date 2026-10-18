# HW4 — Shop API на Postgres + уровни изоляции транзакций

Shop API из ДЗ-2 теперь хранит данные в PostgreSQL, а не в памяти процесса.

## Как устроено
- `docker-compose.yml` — `postgres:16` (том `pgdata`, healthcheck `pg_isready`) + `shop-api`; сервис стартует только после того, как база `healthy`, адрес базы — в `DATABASE_URL`
- `shop_api/db.py` — engine (пул соединений), фабрика сессий, `Base`
- `shop_api/models.py` — таблицы `items`, `carts`, `cart_items` (many-to-many через третью таблицу, составной PK, внешние ключи)
- `shop_api/store.py` — Data Mapper: SQLAlchemy-модели отдельно от доменных `ItemRecord` / `CartRecord`; каждая функция — одна транзакция
- `shop_api/items.py`, `carts.py` — ручки те же, что в ДЗ-2; фильтр и пагинация товаров — в SQL
- `isolation/` — скрипты с аномалиями транзакций

Решения:
- синхронный SQLAlchemy + psycopg, поэтому хендлеры `def`, а не `async def` — FastAPI запускает их в пуле потоков и не блокирует event loop
- добавление в корзину — один атомарный запрос `INSERT … ON CONFLICT DO UPDATE SET quantity = quantity + 1`, без lost update
- таблицы создаются `create_all` при старте приложения (миграции в задании не требовались)

## Запуск
```bash
cd hw4
docker compose up --build
```
Shop API: http://127.0.0.1:8080/docs. Данные переживают `docker compose restart` и `down` / `up` (без `-v`).

## Уровни изоляции
База из compose должна быть запущена (порт 5432 проброшен на хост):
```bash
cd hw4
pip install -r requirements.txt
python -m isolation.dirty_read
python -m isolation.non_repeatable_read
python -m isolation.phantom_read
```
В каждом скрипте два соединения A и B, шаги идут строго по очереди; меняется уровень изоляции A. Скрипт печатает, что видит A, и вердикт.

| Пункт задания | Результат в Postgres 16 |
| --- | --- |
| dirty read при Read Uncommitted | не воспроизводится: Postgres принимает уровень (`SHOW transaction_isolation` → `read uncommitted`), но работает как Read Committed |
| нет dirty read при Read Committed | ✅ A видит 1500, а не незакоммиченную 1 |
| non-repeatable read при Read Committed | ❗ 300 → 350 в одной транзакции |
| нет non-repeatable read при Repeatable Read | ✅ 300 → 300 |
| phantom read при Repeatable Read | не воспроизводится: Repeatable Read в Postgres — снимок данных, строже стандарта; фантом показан на Read Committed: ❗ 2 → 3 |
| нет phantom read при Serializable | ✅ 2 → 2 (и на Repeatable Read тоже) |

Цена — `float`, как в контрактах ДЗ-2; для денег в реальном сервисе нужен `Numeric`.
