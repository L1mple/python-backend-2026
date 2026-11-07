# Уровни изоляции в PostgreSQL

Скрипты показывают аномалии транзакций на разных уровнях изоляции. Они работают через SQLAlchemy (async, драйвер asyncpg) с той же БД, что и магазин, но в отдельной таблице `isolation_items`. Таблица создаётся заново перед каждым сценарием и удаляется в конце, данные магазина скрипты не трогают.

Каждый сценарий открывает две транзакции, T1 и T2, в разных соединениях и выполняет их шаги по очереди. Шаги печатаются, поэтому видно, кто что прочитал и в какой момент. Первым запросом каждая транзакция спрашивает у БД `current_setting('transaction_isolation')`: так видно, что уровень действительно выставлен.

## Запуск

В контейнере, после `docker compose up --build -d` в `hw2/hw`:

```sh
docker compose exec shop python -m isolation
```

С хоста (PostgreSQL из docker-compose слушает 127.0.0.1:5432):

```sh
cd hw2/hw
pip install -r requirements.txt
python -m isolation                      # все сценарии
python -m isolation.non_repeatable_read  # один: dirty_read, phantom_read, write_skew
```

Если поведение БД не совпало с ожидаемым, скрипт завершается с кодом 1. В CI он запускается после тестов (`hw2-tests.yml`).

## Результаты

| Сценарий | Уровень | Аномалия |
|---|---|---|
| Dirty read | READ UNCOMMITTED | нет (см. ниже) |
| Dirty read | READ COMMITTED | нет |
| Non-repeatable read | READ COMMITTED | есть |
| Non-repeatable read | REPEATABLE READ | нет |
| Phantom read | READ COMMITTED | есть |
| Phantom read | REPEATABLE READ | нет (см. ниже) |
| Phantom read | SERIALIZABLE | нет |
| Write skew | REPEATABLE READ | есть |
| Write skew | SERIALIZABLE | нет: вторая транзакция откатывается с ошибкой 40001 |

## Два пункта, которые PostgreSQL не воспроизводит

В задании есть «показать dirty read при read uncommitted» и «показать phantom reads при repeatable read». В PostgreSQL обеих аномалий нет, и это описано в документации: [Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html), таблица 13.1.

- READ UNCOMMITTED PostgreSQL принимает, но выполняет как READ COMMITTED. В сценарии БД подтверждает уровень `read uncommitted`, а незакоммиченную цену T1 всё равно не видит. Диалект asyncpg в SQLAlchemy этот уровень не принимает, поэтому скрипт задаёт его командой `SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED`.
- REPEATABLE READ в PostgreSQL построен на снимке данных: транзакция видит данные на момент своего первого запроса. Строки, которые другие транзакции добавили позже, в снимок не попадают, поэтому фантомов нет. Стандарт SQL на этом уровне фантомы допускает, в таблице документации это отмечено как «Allowed, but not in PG».

Поэтому фантомы показаны на READ COMMITTED, где они действительно появляются.

## Чем SERIALIZABLE отличается от REPEATABLE READ

Фантомов нет уже на REPEATABLE READ, поэтому разницу между ним и SERIALIZABLE показывает отдельный сценарий, write skew. Правило магазина: в продаже должен остаться хотя бы один товар. Две транзакции одновременно проверяют правило, видят два товара и снимают с продажи разные. На REPEATABLE READ коммитятся обе, и в продаже не остаётся ничего, хотя каждая по отдельности правило соблюдала. На SERIALIZABLE PostgreSQL замечает, что такой результат не получить ни при каком последовательном порядке транзакций, и откатывает вторую с ошибкой `could not serialize access` (SQLSTATE 40001). В настоящем приложении такую транзакцию нужно повторить.
