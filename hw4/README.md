## ДЗ

За каждый пункт - 1 балл

Внедрить во вторую домашку хранение данных в БД, для этого надо:
1) Добавить БД в docket-compose.yml (если БД - это отдельный сервис, если хотите использовать sqlite, то можно скипнуть этот шаг)
2) Переписать код на взаимодействие с вашей БД (если вы еще этого не сделали, если вы уже написали код с БД, подзравляю, вам остался только 3 пункт)
3) В свободной форме, напишите скрипты, которые просимулируют разные "проблемы" которые могут возникнуть в транзакциях (dirty read, not-repeatable read, serialize) и настраивая уровне изоляции покажите, что они действительно решаются (через SQLAlchemy например), то есть:
показать dirty read при read uncommited
показать что нет dirty read при read commited
показать non-repeatable read при read commited
показать что нет non-repeatable read при repeatable read
показать  phantom reads при repeatable read
показать что нет phantom reads при serializable
*Тут зависит от того какую БД вы выбрали, разные БД могут поддерживать разные уровни изоляции

## Решение

1) В [docker-compose.yml](./docker-compose.yml) добавлен сервис `postgres`, `shop` подключается к нему через `DATABASE_URL`.
2) [shop_api/db.py](./shop_api/db.py) — модели SQLAlchemy (`items`, `carts`, `cart_items`), [shop_api/main.py](./shop_api/main.py) — API поверх БД. Без `DATABASE_URL` используется SQLite (`shop.db`), так тесты запускаются без Postgres:

    ```sh
    pytest -v hw4
    ```

3) [isolation_demo.py](./isolation_demo.py) — аномалии транзакций на разных уровнях изоляции:

    ```sh
    docker compose up -d postgres
    python isolation_demo.py
    ```

    В PostgreSQL `READ UNCOMMITTED` работает как `READ COMMITTED` (dirty read невозможен), а на `REPEATABLE READ` нет фантомов. Поэтому phantom read показан на `READ COMMITTED`, а для `REPEATABLE READ` и `SERIALIZABLE` показана аномалия сериализации (write skew).
