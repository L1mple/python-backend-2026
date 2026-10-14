# HW4: Shop API + PostgreSQL

Основа — Shop API из HW2-3. Хранение в памяти заменено PostgreSQL.

## Запуск

```
docker compose -f hw4/docker-compose.yml up -d --build --wait
```

| Сервис                                 | Адрес                                                           |
|----------------------------------------|-----------------------------------------------------------------|
| API / Swagger                          | http://127.0.0.1:8000/docs                                      |
| Проверка приложения и подключения к БД | http://127.0.0.1:8000/health                                    |
| Метрики                                | http://127.0.0.1:8000/metrics                                   |
| Prometheus                             | http://127.0.0.1:9090                                           |
| Grafana                                | http://127.0.0.1:3000 — `admin` / `admin`                       |
| PostgreSQL                             | `127.0.0.1:7432`, БД `shop`, пользователь `shop`, пароль `shop` |

```
# Остановка
docker compose -f hw4/docker-compose.yml down
```
При пересоздании контейнеров данные сохраняются.
`db/init.sql` выполняется разово при создании пустой БД.

## Реализация

- PostgreSQL 15, SQLAlchemy 2, psycopg 3; синхронные обработчики FastAPI.
- `database.py` — engine с пулом соединений и отдельная Session на запрос.
- `models.py` — ORM-модели; `storage.py` — операции магазина.
- Каждая изменяющая операция выполняется в одной транзакции через `session.begin()`.
  Commit завершается до успешного ответа; при ошибке выполняется rollback.
- Уровень изоляции магазина — `READ COMMITTED`.
- Pydantic-схемы, URL, HTTP-статусы и семантика API сохранены из HW3.

| Таблица      | Содержимое                       |
|--------------|----------------------------------|
| `items`      | `id`, `name`, `price`, `deleted` |
| `carts`      | `id`                             |
| `cart_items` | `cart_id`, `item_id`, `quantity` |

## Уровни изоляции

После запуска стека:

```
# Все сценарии
docker compose -f hw4/docker-compose.yml exec shop python -m transaction_demos.run

# Отдельные сценарии
docker compose -f hw4/docker-compose.yml exec shop python -m transaction_demos.run dirty
docker compose -f hw4/docker-compose.yml exec shop python -m transaction_demos.run nonrepeatable
docker compose -f hw4/docker-compose.yml exec shop python -m transaction_demos.run phantom
docker compose -f hw4/docker-compose.yml exec shop python -m transaction_demos.run write-skew
```

### Что ожидается именно в PostgreSQL

| Сценарий            | Уровень          | Ожидаемый результат                                                 |
|---------------------|------------------|---------------------------------------------------------------------|
| Dirty read          | Read Uncommitted | T1 меняет 100 на 999 без commit; T2 видит 100                       |
| Dirty read          | Read Committed   | T2 также видит 100                                                  |
| Non-repeatable read | Read Committed   | После commit T2 повторное чтение T1 меняется: 100 → 150             |
| Non-repeatable read | Repeatable Read  | Повторное чтение T1 остаётся 100 → 100                              |
| Phantom read        | Read Committed   | После вставки T2 количество строк у T1 меняется: 2 → 3              |
| Phantom read        | Repeatable Read  | Количество остаётся 2 → 2                                           |
| Phantom read        | Serializable     | Количество остаётся 2 → 2                                           |
| Write skew          | Repeatable Read  | Обе транзакции фиксируются и нарушают совместное правило            |
| Write skew          | Serializable     | Одна транзакция отклоняется с SQLSTATE `40001`; правило сохраняется |

В PostgreSQL `READ UNCOMMITTED` фактически работает как `READ COMMITTED`: грязное
чтение невозможно. `REPEATABLE READ` реализован через снимок данных и уже защищает
от фантомных чтений. Поэтому два ожидаемых по общей таблице SQL-стандарта проявления
аномалий из задания здесь не возникают.

Для демонстрации отличия Serializable добавлен write skew с искусственным правилом
«хотя бы один товар должен оставаться доступным». Две транзакции видят два товара
и отключают разные строки. На Repeatable Read обе могут завершиться, оставив ноль
товаров. На Serializable одна получает ошибку сериализации. После этого скрипт
повторяет всю отклонённую операцию в новой транзакции: она видит последний товар
и отказывается его отключать.