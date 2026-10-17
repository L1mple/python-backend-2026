# Уровни изоляции транзакций: демо на SQLAlchemy

## Как запустить

    docker compose up -d postgres mysql
    pip install -r isolation_demo/requirements.txt
    python isolation_demo/isolation_demo.py > isolation_demo/output.txt

MySQL стартует долго, после `docker compose up` подождите около минуты.

## Что делает скрипт

Скрипт открывает две транзакции (T1 и T2) и по очереди выполняет в них запросы.
Для каждого уровня изоляции он смотрит, что реально увидела T1, и пишет, есть аномалия или нет.

- **Dirty read** (грязное чтение): T1 видит данные T2, которые T2 ещё не сохранила и потом откатила.
- **Non-repeatable read** (неповторяемое чтение): T1 читает одну строку дважды и получает разные значения, потому что T2 изменила её между чтениями.
- **Phantom read** (фантомное чтение): T1 повторяет запрос с условием и видит новые строки, которые добавила T2.

## Результат

Есть аномалия или нет:

| Аномалия и уровень изоляции         | PostgreSQL 15 | MySQL 8 |
|-------------------------------------|---------------|---------|
| Dirty read, READ UNCOMMITTED        | нет           | есть    |
| Dirty read, READ COMMITTED          | нет           | нет     |
| Non-repeatable read, READ COMMITTED | есть          | есть    |
| Non-repeatable read, REPEATABLE READ| нет           | нет     |
| Phantom read, REPEATABLE READ       | нет           | есть    |
| Phantom read, SERIALIZABLE          | нет           | нет     |

## Почему нужны две базы

В Postgres некоторые аномалии просто невозможны:

- Уровень READ UNCOMMITTED в нём работает как READ COMMITTED, поэтому грязного чтения нет.
- REPEATABLE READ в нём работает по снимку данных, поэтому фантомов тоже нет.

Поэтому dirty read и phantom read показаны на MySQL. Это та самая оговорка из задания:
разные БД поддерживают разные уровни изоляции.

## Как показан phantom read в MySQL

Обычный SELECT вставку из T2 не видит. Но если T1 после этого делает UPDATE по тому же условию,
UPDATE затрагивает и новую строку (3 строки вместо 2), и она появляется в SELECT.

На уровне SERIALIZABLE вставка в T2 блокируется, пока T1 не завершится, поэтому фантома нет.