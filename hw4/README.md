# Домашнее задание №4

Во второй домашней работе товары и корзины хранились в обычных словарях. Здесь
те же данные сохраняются в PostgreSQL через SQLAlchemy. После перезапуска API
товары, корзины и их содержимое не пропадают.

## Что сделано

- PostgreSQL добавлен отдельным сервисом в `docker-compose.yml`;
- для таблиц `items`, `carts` и `cart_items` описаны SQLAlchemy-модели;
- все операции Shop API переведены с хранения в памяти на запросы к БД;
- строка корзины блокируется через `SELECT FOR UPDATE`, поэтому параллельные
  запросы не теряют изменения количества;
- добавлен healthcheck, который проверяет не только API, но и соединение с БД;
- добавлены запускаемые примеры для dirty read, non-repeatable read, phantom
  read и write skew на разных уровнях изоляции.

## Запуск приложения

```bash
cd hw4
docker compose up --build -d
```

После запуска доступны:

- Swagger: <http://localhost:8000/docs>
- проверка приложения и БД: <http://localhost:8000/health>
- PostgreSQL с хоста: `localhost:7432`

Остановить сервисы:

```bash
docker compose down
```

Удалить сервисы вместе с сохраненными данными:

```bash
docker compose down -v
```

## Проблемы транзакций

Сначала нужно запустить контейнеры, затем выполнить все примеры одной командой:

```bash
docker compose exec api python -m transaction_isolation.run_all
```

Можно запускать примеры отдельно:

```bash
docker compose exec api python -m transaction_isolation.dirty_read
docker compose exec api python -m transaction_isolation.non_repeatable_read
docker compose exec api python -m transaction_isolation.phantom_read
docker compose exec api python -m transaction_isolation.serialization
```

Скрипты открывают две независимые транзакции и печатают значения, которые
видит первая транзакция до и после изменения данных во второй.

| Пример | Уровень | Результат в PostgreSQL |
|---|---|---|
| Dirty read | READ UNCOMMITTED | Незакоммиченное изменение не видно |
| Dirty read | READ COMMITTED | Незакоммиченное изменение не видно |
| Non-repeatable read | READ COMMITTED | Второе чтение видит новое значение |
| Non-repeatable read | REPEATABLE READ | Оба чтения возвращают одно значение |
| Phantom read | READ COMMITTED | Второе чтение видит новую строку |
| Phantom read | REPEATABLE READ | Оба чтения видят один набор строк |
| Phantom read | SERIALIZABLE | Оба чтения видят один набор строк |
| Write skew | REPEATABLE READ | Обе транзакции завершаются, правило нарушается |
| Write skew | SERIALIZABLE | Одна транзакция отклоняется с ошибкой `40001` |

PostgreSQL не позволяет получить dirty read: уровень `READ UNCOMMITTED` в нем
работает как `READ COMMITTED`. Также его `REPEATABLE READ` основан на снимке
данных и уже защищает от phantom read. Поэтому скрипты отдельно показывают эти
особенности выбранной БД, как и допускается в условии домашней работы.
Чтобы отдельно показать усиление изоляции на `SERIALIZABLE`, добавлен пример с
двумя дежурными. Обе транзакции видят, что дежурных двое, и пытаются снять с
дежурства разные строки. На `REPEATABLE READ` обе могут завершиться, а на
`SERIALIZABLE` PostgreSQL отменяет одну из них.

## Тесты

Для тестов используется отдельная временная SQLite-база, чтобы их можно было
запустить без Docker. Само приложение в `docker-compose` работает с PostgreSQL.

```bash
cd hw4
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
