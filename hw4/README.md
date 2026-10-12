# ДЗ №4 — PostgreSQL и уровни изоляции

Задание: [lecture4/README.md](../lecture4/README.md).
Ветка `codex/hw4-database` создана от `codex/hw3-monitoring`.

## Что выполнено: 3 пункта задания

| Пункт | Где смотреть | Как проверить |
| --- | --- | --- |
| 1. БД в Docker Compose | [`docker-compose.yml`](../docker-compose.yml): сервис `postgres`, healthcheck, volume `postgres-data`, зависимость API от готовности БД | `make up-hw4`, затем `docker compose ps` |
| 2. Хранение данных API из ДЗ №2 в БД | [`database.py`](../hw2/hw/shop_api/database.py), [`store.py`](../hw2/hw/shop_api/store.py), [`main.py`](../hw2/hw/shop_api/main.py) | `make test-hw4`: исходные тесты преподавателя и дополнительные тесты на PostgreSQL |
| 3. Аномалии и уровни изоляции | [`isolation_demo.py`](isolation_demo.py), таблица ниже | `make demo-hw4`: 9 сценариев с проверками `assert`; при ошибке команда завершается ненулевым кодом |

## Быстрый запуск

Нужны Docker Compose и `uv`. Все команды выполняются из корня репозитория:

```bash
make install
make up-hw4
make test-hw4
make lint
```

- API и Swagger: <http://127.0.0.1:8000/docs>.
- PostgreSQL: `127.0.0.1:7432`, БД `shop`, пользователь/пароль `shop`.
- Prometheus и Grafana из HW3: <http://127.0.0.1:9090>, <http://127.0.0.1:3000>.

Учебные реквизиты БД заданы в Compose. В контейнере API используется
`postgresql+psycopg://shop:shop@postgres:5432/shop`; локально —
`postgresql+psycopg://shop:shop@127.0.0.1:7432/shop`.
При необходимости другой адрес передаётся через `DATABASE_URL`.

Если HW3 уже работает на стандартных портах, HW4 можно поднять рядом:

```bash
export API_PORT=8004 PROMETHEUS_PORT=9094 GRAFANA_PORT=3004
make up-hw4
```

Тогда Swagger будет на <http://127.0.0.1:8004/docs>. Проект Compose HW4
называется `shop-hw4`, поэтому у него свои контейнеры и volumes.

Остановить HW4, сохранив данные: `make down-hw4`.
Для локального запуска API достаточно `make db-hw4`, затем `make run-hw2`.

## Хранение и транзакции API

Используются PostgreSQL 16, SQLAlchemy 2 и драйвер psycopg 3.
Три таблицы:

- `items`: ID, имя, цена, флаг мягкого удаления;
- `carts`: ID корзины;
- `cart_items`: корзина, товар и количество; пара `(cart_id, item_id)` уникальна.

Внешние ключи связывают позиции с корзинами и товарами; `CHECK` запрещает
отрицательную цену и неположительное количество. Таблицы создаются при запуске
через `Base.metadata.create_all()`; для этой домашки с одной схемой этого достаточно.

На каждый HTTP-запрос `get_session()` создаёт отдельную SQLAlchemy Session
и транзакцию. При успехе выполняется commit, при исключении — rollback.
`Depends(..., scope="function")` завершает транзакцию **до отправки ответа**:
ошибка commit не превращается в успешный `201`. Синхронные HTTP-обработчики
выполняются FastAPI в пуле потоков; WebSocket-чат остаётся асинхронным.

Обновление товара блокирует его строку через `SELECT ... FOR UPDATE`.
Добавление в корзину сначала блокирует корзину, затем товар: параллельные
добавления корректно увеличивают количество. Это проверяется 24 запросами
из 8 потоков на настоящем PostgreSQL.

Контракт HW2 сохранён: `201` и `Location`, фильтры перед пагинацией,
`PUT`/`PATCH`, мягкое удаление и `304` для PATCH удалённого товара.
Корзина показывает актуальные имена и цены; удалённый товар остаётся в её
составе как недоступный и не входит в итоговую стоимость.
Метрики и дашборды HW3 продолжают работать.

### Проверка сохранения данных

В Swagger создайте товар (`POST /item`), корзину (`POST /cart`) и дважды
добавьте товар (`POST /cart/{cart_id}/add/{item_id}`). Запомните полученные ID.
Затем выполните:

```bash
docker compose restart postgres shop-api
docker compose up -d --wait postgres shop-api
```

`GET /item/{item_id}` и `GET /cart/{cart_id}` должны вернуть прежние данные
и количество `2`. То же сохраняется после `make down-hw4` / `make up-hw4`,
поскольку данные PostgreSQL находятся в именованном volume.
Автотест также закрывает приложение и пул соединений, запускает приложение
заново и проверяет товар, корзину, количество и флаг удаления.
Оба варианта проверены через HTTP на полном Docker-стенде;
результат и строки PostgreSQL: [`evidence/runtime.txt`](evidence/runtime.txt).

## Уровни изоляции: что именно показывает скрипт

В PostgreSQL `READ UNCOMMITTED` работает как `READ COMMITTED`, а
`REPEATABLE READ` предотвращает фантомы благодаря снимку транзакции.
Поэтому dirty read на RU и phantom read на RR воспроизвести в этой СУБД нельзя.
Это учтено в примечании задания о различиях между БД и подтверждено
[официальной документацией PostgreSQL, таблица 13.1](https://www.postgresql.org/docs/16/transaction-iso.html).
Скрипт проверяет фактическое поведение этих уровней, а фантом демонстрирует на RC.

| Сценарий | Уровень | Действия двух транзакций | Проверяемый результат |
| --- | --- | --- | --- |
| Dirty read | Read Uncommitted | A меняет 100 → 999 без commit; B читает; A делает rollback | B читает 100 до и после rollback: dirty read в PostgreSQL отсутствует |
| Dirty read | Read Committed | То же | B читает 100: незакоммиченные данные не видны |
| Non-repeatable read | Read Committed | A читает 100; B меняет на 200 и делает commit; A читает повторно | 100 → 200: аномалия воспроизведена |
| Non-repeatable read | Repeatable Read | То же | 100 → 100: аномалия устранена |
| Phantom read | Read Committed | A считает 2 подходящие строки; B вставляет третью и делает commit; A считает снова | 2 → 3: фантом воспроизведён |
| Phantom read | Repeatable Read | То же | 2 → 2: PostgreSQL предотвращает фантом уже на RR |
| Phantom read | Serializable | То же | 2 → 2: фантом отсутствует |
| Serialization anomaly / write skew | Repeatable Read | Две транзакции видят общий баланс 200 и снимают по 100 с разных строк | Обе делают commit, итог 0: нарушено правило «оставить минимум 100» |
| Serialization anomaly / write skew | Serializable | То же | PostgreSQL отменяет один commit с `SQLSTATE 40001`; итог 100. Повтор всей транзакции читает 100 и отказывает в снятии |

Каждый сценарий использует два независимых соединения и перекрывающиеся
транзакции. Порядок SQL-запросов задан явно; таймеры и случайные задержки
не нужны. Уровень задаётся через SQLAlchemy
`connection.execution_options(isolation_level=...)` до первого запроса.
Новый снимок после окончания транзакции также проверяется: он видит
зафиксированное значение 200 или третью строку.

Для каждого запуска создаётся отдельная схема `hw4_demo_<uuid>` с одной
учебной таблицей. В `finally` удаляется только эта схема; таблицы магазина
не затрагиваются. Скрипт печатает действия A/B и фактические значения.
Успешное завершение: `ALL 9 SCENARIOS PASSED`.
Фактический вывод проверенного запуска: [`evidence/isolation.txt`](evidence/isolation.txt).

## Проверки

```bash
make test       # быстрые тесты API на временных SQLite-файлах, без Docker
make test-hw4   # те же тесты на PostgreSQL + все сценарии изоляции
make lint      # Ruff и mypy
```

Тесты PostgreSQL используют отдельные схемы `hw4_test_<uuid>` и удаляют
только их. Исходный `test_homework2.py` преподавателя не изменён.
GitHub Actions запускает тесты и скрипт изоляции на PostgreSQL 16
с Python 3.13 и 3.14 и собирает Docker-образ API из `uv.lock`.

Проверено локально 12 октября 2026 года: **89 тестов прошли на PostgreSQL**,
**9 сценариев изоляции прошли**, Ruff и mypy — без ошибок.
Все четыре контейнера healthy; данные пережили restart и down/up,
Prometheus собирает метрики, оба дашборда Grafana загружены.
В быстром наборе SQLite — 88 тестов прошли, а проверка параллельных
добавлений пропущена: она выполняется на PostgreSQL в `make test-hw4`.
