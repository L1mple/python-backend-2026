# ДЗ 4: БД и уровни изоляции

Задание в [lecture4/README.md](../lecture4/README.md).

Взял Shop API из ДЗ 2 и перевёл хранилище со словарей в памяти на PostgreSQL
(SQLAlchemy 2 + psycopg 3). Ручки и контракты остались те же.

- `store/db.py` — engine, сессии, `init_db()` (таблицы создаются через `create_all` при старте)
- таблицы `items`, `carts` и `cart_items` (корзина -> товар -> количество)
- фильтры и пагинация делаются в SQL, корзина с товарами грузится одним join
- добавление в корзину — `INSERT ... ON CONFLICT DO UPDATE quantity = quantity + 1`, чтобы параллельные запросы не теряли количество
- обработчики стали `def` вместо `async def`, т.к. драйвер синхронный, и FastAPI гоняет их в пуле потоков

## Запуск

```sh
cd hw4
docker compose -p hw4-shop up -d --build --wait
```

API: http://localhost:8080/docs, Postgres: `localhost:7432` (shop/shop).

Тесты из ДЗ 2 гоняются против этой базы:

```sh
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest
```

## Уровни изоляции

```sh
.venv/bin/python -m isolation.run_all
```

Две транзакции A и B по шагам работают с таблицей `accounts`, меняется уровень у A.
Вывод лежит в [results/isolation.txt](results/isolation.txt).

| Что показать | Что вышло |
| --- | --- |
| dirty read при read uncommitted | в Postgres не получить: read uncommitted [работает как read committed](https://www.postgresql.org/docs/16/transaction-iso.html), A видит 100 |
| нет dirty read при read committed | A видит 100, а не 0 |
| non-repeatable read при read committed | 100, потом 50 |
| нет non-repeatable read при repeatable read | 100 и 100 |
| phantom read при repeatable read | в Postgres тоже не получить, repeatable read работает на снимке. Фантом есть на read committed: 2, потом 3 строки |
| нет phantom read при serializable | 2 и 2 (на repeatable read тоже) |

Ещё `serialization.py` показывает write skew: обе транзакции видят сумму 200 и
снимают по 150 каждая. На repeatable read итог -100, на serializable второй
commit падает с `SerializationFailure`.
