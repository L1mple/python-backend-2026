# ДЗ4 и ДЗ5: хранение данных в БД, уровни изоляции, тесты и CI

Это сервис магазина из [ДЗ2](../hw2/hw/shop_api/main.py) (REST + RPC API и WebSocket-чат), переписанный на
хранение данных в БД. Код ДЗ2 остался как был: версия с БД лежит отдельно, в этой папке, поэтому проверки
ДЗ2 в CI не затронуты.

## ДЗ4

| Пункт | Что сделано |
|---|---|
| 1. БД в docker-compose | [`docker-compose.yml`](./docker-compose.yml): PostgreSQL 16 (с healthcheck), сервис `api` (стартует, когда БД готова), MySQL 8.4 для демонстрации изоляции (профиль `isolation`) |
| 2. Код работает с БД | [`shop_api/`](./shop_api): SQLAlchemy 2 (модели в [`models.py`](./shop_api/models.py), подключение в [`database.py`](./shop_api/database.py), ручки в [`main.py`](./shop_api/main.py)) |
| 3. Скрипты про изоляцию транзакций | [`isolation/demo.py`](./isolation/demo.py), результаты ниже |

### Как запустить

```sh
docker compose up --build              # PostgreSQL + сервис на http://localhost:8080 (документация: /docs)
docker compose down                    # остановить (-v: заодно удалить данные БД)
```

Данные хранятся в томе `pgdata`, поэтому переживают перезапуск сервиса.

### Что изменилось по сравнению с ДЗ2

- Товары, корзины и товары в корзинах лежат в таблицах `items`, `carts`, `cart_items`.
- Цена и количество корзины считаются в БД (`SUM(quantity * price)` с `GROUP BY`), фильтры по цене и
  количеству в `GET /cart` реализованы через `HAVING`, пагинация через `OFFSET/LIMIT`.
- Добавление товара в корзину (`POST /cart/{cart_id}/add/{item_id}`) берет блокировку строки корзины
  (`SELECT ... FOR UPDATE`), поэтому параллельные запросы не теряют количество (это проверяет отдельный тест).
- Поведение API (коды ответов, форматы) не менялось: те же 39 тестов из ДЗ2 проходят без изменений.

### Уровни изоляции транзакций

Скрипт открывает две параллельные транзакции (T1 и T2) через SQLAlchemy, выставляет уровень изоляции
(`execution_options(isolation_level=...)`) и проверяет, видит ли T1 аномалию. Результат каждого сценария
сравнивается с ожидаемым для конкретной БД, при расхождении скрипт завершается с ошибкой.

Какую БД использовать, решает каждый сам (так сказано в задании), поэтому сценарии запускаются на двух:

- **PostgreSQL**, на которой работает сервис;
- **MySQL (InnoDB)**: в PostgreSQL нельзя показать dirty read (`READ UNCOMMITTED` там работает как
  `READ COMMITTED`), а `REPEATABLE READ` защищает и от phantom read. MySQL ведет себя так, как описано в учебниках.

```sh
pip install -r requirements-test.txt
docker compose up -d db
docker compose --profile isolation up -d mysql
python -m isolation.demo --db postgres
python -m isolation.demo --db mysql
```

Сводка (подробный вывод каждого сценария ниже):

| Сценарий | Уровень | MySQL | PostgreSQL |
|---|---|---|---|
| 1. Dirty read | READ UNCOMMITTED | **есть** | нет (работает как READ COMMITTED) |
| 2. Нет dirty read | READ COMMITTED | нет | нет |
| 3. Non-repeatable read | READ COMMITTED | **есть** | **есть** |
| 4. Нет non-repeatable read | REPEATABLE READ | нет | нет |
| 5. Phantom read | REPEATABLE READ | **есть** (после UPDATE по тому же условию) | нет (снимок данных) |
| 6. Нет phantom read | SERIALIZABLE | нет (вставка T2 блокируется) | нет (конфликтующая транзакция откатывается) |

Как читать сценарии: товары Milk(50), Bread(150), Cheese(200). T1 меняет или читает, T2 вмешивается.

<details>
<summary>Вывод на MySQL</summary>

```
1. Dirty read при READ UNCOMMITTED  [READ UNCOMMITTED]
  T1 поставила цену 999 и не зафиксировала; T2 прочитала цену = 999 (в БД лежало 50)
  аномалия dirty read: ЕСТЬ (ожидали: есть) -> OK

2. Нет dirty read при READ COMMITTED  [READ COMMITTED]
  T1 поставила цену 999 и не зафиксировала; T2 прочитала цену = 50 (в БД лежало 50)
  аномалия dirty read: нет (ожидали: нет) -> OK

3. Non-repeatable read при READ COMMITTED  [READ COMMITTED]
  T1 прочитала цену 50, T2 изменила ее на 70 и зафиксировала; T1 читает снова: 70
  аномалия non-repeatable read: ЕСТЬ (ожидали: есть) -> OK

4. Нет non-repeatable read при REPEATABLE READ  [REPEATABLE READ]
  T1 прочитала цену 50, T2 изменила ее на 70 и зафиксировала; T1 читает снова: 50
  аномалия non-repeatable read: нет (ожидали: нет) -> OK

5. Phantom read при REPEATABLE READ  [REPEATABLE READ]
  T1 насчитала дорогих товаров: 2; T2 добавила Wine(500) и зафиксировала; повторный SELECT: 2; после UPDATE по тому же условию: 3
  аномалия phantom read: ЕСТЬ (ожидали: есть) -> OK

6. Нет phantom read при SERIALIZABLE  [SERIALIZABLE]
  T1 насчитала 2; вставка T2 заблокирована (Lock wait timeout); T1 считает снова: 2
  аномалия phantom read: нет (ожидали: нет) -> OK

=== Итог (mysql) ===
Сценарий                                           Уровень           Аномалия   Результат
1. Dirty read при READ UNCOMMITTED                 READ UNCOMMITTED  есть       OK
2. Нет dirty read при READ COMMITTED               READ COMMITTED    нет        OK
3. Non-repeatable read при READ COMMITTED          READ COMMITTED    есть       OK
4. Нет non-repeatable read при REPEATABLE READ     REPEATABLE READ   нет        OK
5. Phantom read при REPEATABLE READ                REPEATABLE READ   есть       OK
6. Нет phantom read при SERIALIZABLE               SERIALIZABLE      нет        OK

Все сценарии совпали с ожиданием.
```

</details>

<details>
<summary>Вывод на PostgreSQL</summary>

```
1. Dirty read при READ UNCOMMITTED  [READ UNCOMMITTED]
  T1 поставила цену 999 и не зафиксировала; T2 прочитала цену = 50 (в БД лежало 50)
  аномалия dirty read: нет (ожидали: нет) -> OK
  Примечание: В PostgreSQL уровень READ UNCOMMITTED работает как READ COMMITTED: грязное чтение там невозможно ни на одном уровне (так это описано в документации).

2. Нет dirty read при READ COMMITTED  [READ COMMITTED]
  T1 поставила цену 999 и не зафиксировала; T2 прочитала цену = 50 (в БД лежало 50)
  аномалия dirty read: нет (ожидали: нет) -> OK

3. Non-repeatable read при READ COMMITTED  [READ COMMITTED]
  T1 прочитала цену 50, T2 изменила ее на 70 и зафиксировала; T1 читает снова: 70
  аномалия non-repeatable read: ЕСТЬ (ожидали: есть) -> OK

4. Нет non-repeatable read при REPEATABLE READ  [REPEATABLE READ]
  T1 прочитала цену 50, T2 изменила ее на 70 и зафиксировала; T1 читает снова: 50
  аномалия non-repeatable read: нет (ожидали: нет) -> OK

5. Phantom read при REPEATABLE READ  [REPEATABLE READ]
  T1 насчитала дорогих товаров: 2; T2 добавила Wine(500) и зафиксировала; повторный SELECT: 2; после UPDATE по тому же условию: 2
  аномалия phantom read: нет (ожидали: нет) -> OK
  Примечание: REPEATABLE READ в PostgreSQL построен на снимках (snapshot isolation), поэтому призраков нет уже на этом уровне - это строже, чем требует стандарт SQL.

6. Нет phantom read при SERIALIZABLE  [SERIALIZABLE]
  T1 насчитала 2; T2 добавила Wine(500) и зафиксировалась; T1 считает снова: 2; коммит T1 с вставкой на основании старого результата: отклонен (SerializationFailure)
  аномалия phantom read: нет (ожидали: нет) -> OK

=== Итог (postgres) ===
Сценарий                                           Уровень           Аномалия   Результат
1. Dirty read при READ UNCOMMITTED                 READ UNCOMMITTED  нет        OK
2. Нет dirty read при READ COMMITTED               READ COMMITTED    нет        OK
3. Non-repeatable read при READ COMMITTED          READ COMMITTED    есть       OK
4. Нет non-repeatable read при REPEATABLE READ     REPEATABLE READ   нет        OK
5. Phantom read при REPEATABLE READ                REPEATABLE READ   нет        OK
6. Нет phantom read при SERIALIZABLE               SERIALIZABLE      нет        OK

Все сценарии совпали с ожиданием.
```

</details>

## ДЗ5

### Тесты и покрытие

Тесты лежат в [`test_homework2.py`](./test_homework2.py) (39 исходных тестов ДЗ2, без изменений) и в
[`tests/`](./tests): ошибки 404 и валидация, фильтры и пагинация, расчеты корзины, параллельные
добавления в корзину, WebSocket-чат, ожидание БД при старте и сценарии изоляции.

```sh
docker compose up -d db
pytest --cov=shop_api --cov-report=term-missing --cov-fail-under=95
```

Покрытие `shop_api`: **100%** (порог 95%).

### CI

Workflow [`hw4-tests.yml`](./ci/hw4-tests.yml) (в репозитории лежит в `.github/workflows/`) запускает те же тесты на
Python 3.13 и 3.14 с PostgreSQL как сервисным контейнером и падает, если покрытие ниже 95%.
Срабатывает на изменения в `hw4/**`.
