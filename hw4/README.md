# HW4: PostgreSQL и изоляция транзакций

Задание: [lecture4/README.md](https://github.com/L1mple/python-backend-2026/blob/main/lecture4/README.md).

Магазин из ДЗ2 хранит товары, корзины и их состав в БД через SQLAlchemy 2.
В Docker Compose используется PostgreSQL 17, данные находятся в отдельном
томе `postgres-data`. Мониторинг Prometheus и Grafana из ДЗ3 сохранён.

## Запуск

Из корня репозитория, при работающем Docker:

```sh
docker compose -f hw4/docker-compose.yml config --quiet
docker compose -f hw4/docker-compose.yml up -d --build --wait
```

| Сервис | Адрес |
| --- | --- |
| Shop API / Swagger | http://localhost:8080/docs |
| Метрики | http://localhost:8080/metrics |
| Prometheus | http://localhost:9090/targets |
| Grafana | http://localhost:3000 |

Порты API и мониторинга доступны только локально. PostgreSQL доступен
сервисам внутри сети Compose. Логин и пароль `shop` предназначены для
локального учебного окружения.

Остановка сохраняет том с БД:

```sh
docker compose -f hw4/docker-compose.yml down
```

## Хранение данных

- `items` — товары с ценой и признаком мягкого удаления.
- `carts` — корзины.
- `cart_lines` — пары «корзина / товар» и количество, с внешними ключами
  и составным первичным ключом.

Каждый HTTP-запрос использует отдельную сессию и транзакцию. Изменения
фиксируются до отправки ответа; при исключении выполняется откат.
Добавление товара использует `INSERT ... ON CONFLICT DO UPDATE`, увеличивая
количество в SQL. В PostgreSQL также блокируется строка корзины, чтобы
параллельные добавления возвращали согласованное состояние корзины.

Фильтры, порядок по ID и пагинация применяются в SQL. Стоимость корзины
вычисляется по текущим ценам товаров. Удалённые товары остаются в корзине
с `available: false`; повторное добавление удалённого товара возвращает 404.
WebSocket-чат сохраняет поведение ДЗ2, а его подключения хранятся в памяти.

Схема создаётся при старте через `Base.metadata.create_all`. Это начальная
схема учебного проекта: миграции существующих таблиц эта команда не выполняет.

Без `DATABASE_URL` используется файловая SQLite `shop.db` в текущем каталоге.
Она тоже сохраняет данные между запусками. Для локального запуска:

```sh
python3 -m venv .venv
.venv/bin/pip install -r hw2/hw/requirements.txt
PYTHONPATH=hw2/hw .venv/bin/python -m uvicorn shop_api.main:app --port 8080
```

## Опыты с транзакциями

```sh
docker compose -f hw4/docker-compose.yml exec -T shop \
  python hw4/isolation.py --output /tmp/isolation.json
docker compose -f hw4/docker-compose.yml cp \
  shop:/tmp/isolation.json hw4/results/isolation.json
```

Скрипт открывает два настоящих соединения SQLAlchemy. Транзакции перекрываются:
A читает данные, B изменяет их, затем A читает повторно. Для грязного чтения
B ещё не закоммичена; для неповторяемого чтения и фантомов B уже закоммичена.
Порядок команд задан явно, без `sleep` и зависимости от планировщика потоков.

Каждый запуск создаёт уникальную схему `hw4_isolation_<uuid>` с таблицей счетов
и удаляет только эту схему в конце. Таблицы магазина не затрагиваются.
Проверки внутри скрипта завершают запуск ошибкой, если поведение отличается
от ожидаемого. Таймауты SQL ограничены пятью секундами.

| Опыт | Уровень | До → после | Аномалия |
| --- | --- | --- | --- |
| Dirty read | READ UNCOMMITTED | 100 → 100 | Нет |
| Dirty read | READ COMMITTED | 100 → 100 | Нет |
| Non-repeatable read | READ COMMITTED | 100 → 200 | Есть |
| Non-repeatable read | REPEATABLE READ | 100 → 100 | Нет |
| Phantom read | READ COMMITTED | 2 → 3 | Есть |
| Phantom read | REPEATABLE READ | 2 → 2 | Нет |
| Phantom read | SERIALIZABLE | 2 → 2 | Нет |
| Write skew | REPEATABLE READ | 200 → 0 | Есть |
| Write skew | SERIALIZABLE | 200 → 100 | Нет; одна транзакция отменена |

В PostgreSQL `READ UNCOMMITTED` работает как `READ COMMITTED`, а
`REPEATABLE READ` уже предотвращает фантомы. Поэтому два указанных в условии
эффекта на этих уровнях в выбранной БД не возникают. Это соответствует
оговорке задания о зависимости от БД и
[документации PostgreSQL](https://www.postgresql.org/docs/17/transaction-iso.html).

Чтобы показать отличие `REPEATABLE READ` от `SERIALIZABLE`, добавлен write skew.
Обе транзакции видят общую сумму 200 и независимо снимают по 100 с разных
счетов, рассчитывая сохранить минимум 100. На `REPEATABLE READ` обе коммитятся
и нарушают правило. На `SERIALIZABLE` PostgreSQL отклоняет одну транзакцию
с SQLSTATE `40001`, сумма остаётся 100. Приложение при такой ошибке должно
повторять всю транзакцию; в опыте повтор не выполняется, чтобы показать отказ.

Фактический результат запуска: [results/isolation.json](results/isolation.json).

## Проверки

Запускайте тесты на отдельной БД: исходные тесты ДЗ2 создают товары и корзины.
Пример с временной SQLite:

```sh
.venv/bin/pip install -r hw3/requirements.txt -r hw2/hw/requirements.txt
HW4_TEST_DIR=$(mktemp -d)
DATABASE_URL="sqlite:///$HW4_TEST_DIR/shop.db" PYTHONPATH=.:hw2/hw \
  .venv/bin/python -m pytest hw2/hw/test_homework2.py hw3/test_monitoring.py hw4/tests -v
```

Дополнительные тесты проверяют актуальную стоимость и мягкое удаление,
SQL-фильтры с пустыми корзинами, параллельные добавления, откат транзакции
и сохранение SQLite между двумя отдельными Python-процессами.

При реализации проверено:

- 47 тестов на SQLite (Python 3.13 и 3.14) и 47 тестов в контейнере: исходные
  проверки API и мониторинга с PostgreSQL, дополнительные проверки с SQLite.
- 24 параллельных запроса добавления в корзину работающего API с PostgreSQL:
  количество и цена совпали с ожидаемыми.
- Данные корзины и признак удаления товара сохранились после пересоздания
  контейнеров PostgreSQL и магазина с тем же томом БД.
- Все девять опытов изоляции успешно выполнены на PostgreSQL 17.11.

Контейнеры проверялись через отдельный профиль Colima `hw3-check`, поскольку
Docker Desktop не отвечал. Проверки HTTP выполнялись внутри контейнера
магазина из-за проблемы проброса портов Colima.
