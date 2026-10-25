# hw4 — Shop API с PostgreSQL

Приложение (FastAPI) хранит данные в PostgreSQL вместо in-memory словарей.

## Запуск

```bash
docker compose up --build
# API: http://localhost:8080, docs: http://localhost:8080/docs
```

Контейнер `local` получает `DATABASE_URL=postgresql+psycopg2://ADMIN:123@db:5432/DB`,
таблицы создаются автоматически при старте (`Base.metadata.create_all`).
Схема БД — `shop_api/store/tables.py` (SQLAlchemy 2.0, ORM), доступ — через
сессии из `shop_api/store/db.py` (dependency `get_session` в роутах).

Локальный запуск без Docker (нужен свой PostgreSQL):

```bash
export DATABASE_URL=postgresql+psycopg2://user:pass@127.0.0.1:5432/dbname
uvicorn shop_api.main:app --port 8080
```

## Демонстрация аномалий транзакций

`scripts/isolation_demo.py` прогоняет 6 сценариев из задания, переключая
уровни изоляции через SQLAlchemy + psycopg2:

| # | Сценарий | Уровень | Результат в PostgreSQL |
|---|----------|---------|------------------------|
| 1 | dirty read | READ UNCOMMITTED | аномалии нет: PG трактует RU как RC |
| 2 | dirty read | READ COMMITTED | аномалии нет |
| 3 | non-repeatable read | READ COMMITTED | **аномалия воспроизводится** |
| 4 | non-repeatable read | REPEATABLE READ | аномалии нет |
| 5 | phantom read | REPEATABLE READ | аномалии нет: PG использует snapshot isolation |
| 5b | write skew | RR vs SERIALIZABLE | при RR нарушает инвариант, при SERIALIZABLE откат с SQLSTATE 40001 |
| 6 | аномалии | SERIALIZABLE | аномалий нет |

Запуск (БД должна быть поднята, например `docker compose up -d db`):

```bash
pip install -r requirements.txt
python scripts/isolation_demo.py
# или с явным URL:
python scripts/isolation_demo.py --db-url postgresql+psycopg2://ADMIN:123@127.0.0.1:5432/DB
```

Примечание: PostgreSQL не поддерживает «настоящий» READ UNCOMMITTED и
phantom read на REPEATABLE READ, поэтому сценарии 1 и 5 показывают защиту,
а не воспроизведение аномалии (сценарий 3 — единственный из шести, где
аномалия реально возникает; сценарий 5b показывает оставшуюся «дыру» RR и
её закрытие на SERIALIZABLE). Для «живого» показа всех аномалий подойдёт
MySQL/InnoDB.
