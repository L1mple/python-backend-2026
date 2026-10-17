# HW4

PostgreSQL и SQLAlchemy для магазина из ДЗ2. Товары, корзины и позиции корзин
хранятся в БД. Операции одного HTTP-запроса выполняются в одной транзакции.
Повторное добавление товара атомарно увеличивает его количество.

## Запуск

Из корня репозитория:

```sh
docker compose -f hw4/docker-compose.yml up --build -d --wait

```

API: <http://localhost:8081/docs>. Метрики: <http://localhost:8081/metrics>.
PostgreSQL доступен на `localhost:7432`, база, пользователь и пароль — `shop`.
Это настройки для локального учебного запуска.

Таблицы создаются при старте приложения. Данные сохраняются в Docker volume
и остаются после перезапуска приложения или `docker compose down`.

```sh
docker compose -f hw4/docker-compose.yml down

```

## Демонстрации изоляции

```sh
docker compose -f hw4/docker-compose.yml exec app python isolation.py

```

Скрипт открывает независимые соединения и чередует действия пересекающихся
транзакций. Для каждого случая проверяются ожидаемые значения. Создаётся
отдельная схема со случайным именем, которая удаляется после выполнения.
Таблицы магазина не меняются. Ожидание запросов и блокировок ограничено.

| Случай | Результат в PostgreSQL |
| --- | --- |
| Грязное чтение, READ UNCOMMITTED | Недоступно: уровень работает как READ COMMITTED |
| Грязное чтение, READ COMMITTED | Незавершённые изменения другой транзакции не видны |
| Повторное чтение, READ COMMITTED | Видно изменение 100 → 200 после чужого COMMIT |
| Повторное чтение, REPEATABLE READ | Сохраняется исходное значение 100 |
| Фантомы, READ COMMITTED | После чужой вставки число строк меняется с 1 на 2 |
| Фантомы, REPEATABLE READ | Число строк остаётся 1, гарантии PostgreSQL сильнее минимума SQL |
| Фантомы, SERIALIZABLE | Число строк остаётся 1 |
| Write skew, REPEATABLE READ | Две транзакции меняют разные строки и нарушают общее условие |
| Write skew, SERIALIZABLE | Вторая транзакция отклоняется с SQLSTATE 40001; повтор сохраняет условие |

В последнем примере хотя бы одна из двух записей должна оставаться активной.
Обе транзакции сначала видят две активные записи и пытаются выключить свою.
Повторять после конфликта нужно всю транзакцию с новым чтением.

Особенности PostgreSQL описаны в [документации по изоляции транзакций](https://www.postgresql.org/docs/17/transaction-iso.html).

## Локальный запуск и тесты

Нужны Python 3.13 или 3.14 и PostgreSQL. Можно поднять только БД:

```sh
docker compose -f hw4/docker-compose.yml up -d --wait postgres
python -m pip install -r hw2/hw/requirements.txt
export DATABASE_URL=postgresql+psycopg://shop:shop@localhost:7432/shop
export PYTHONPATH="$PWD/hw2/hw"
uvicorn shop_api.main:app --port 8081

```

Для проверок:

```sh
export TEST_DATABASE_URL=postgresql+psycopg://shop:shop@localhost:7432/shop
PYTHONPATH=hw2/hw pytest hw2/hw/test_homework2.py hw2/hw/test_storage.py -v
python hw4/isolation.py

```

Тесты создают и удаляют собственную схему в БД из `TEST_DATABASE_URL`.
Пользователю БД нужны права создания схем. Преподавательские тесты сохранены.
В CI проверки запускаются на PostgreSQL с Python 3.13 и 3.14.
