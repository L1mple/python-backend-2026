# ДЗ4: БД и транзакции

Магазин из ДЗ2 хранит товары, корзины и их содержимое в MySQL 8.4 / InnoDB
через SQLAlchemy. Мониторинг из ДЗ3 продолжает работать.

## Запуск

Из корня репозитория:

```sh
docker compose -f hw3/docker-compose.yml -f hw4/docker-compose.yml up --build -d --wait
```

Второй Compose-файл добавляет MySQL и подключает к нему магазин.
Все относительные пути в объединённой конфигурации считаются от `hw3/`.

- API и Swagger: http://localhost:8080/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- MySQL: `127.0.0.1:3307`, база `shop`, пользователь `shop`, пароль `shop`.

Учебные пароли заданы в Compose-файле; порты опубликованы только на localhost.
Данные MySQL сохраняются в volume `mysql-data` после перезапуска и пересоздания
контейнеров. Проверка `/health` выполняет запрос к БД.

На этом Mac `docker` указывает на Podman; для запущенной Colima:

```sh
DOCKER_HOST="unix://$HOME/.colima/default/docker.sock" /opt/homebrew/bin/docker-compose -f hw3/docker-compose.yml -f hw4/docker-compose.yml up --build -d --wait
```

Остановка без удаления данных:

```sh
docker compose -f hw3/docker-compose.yml -f hw4/docker-compose.yml down
```

## Хранение данных

Код находится в `hw2/hw/shop_api`:

- `database.py`: таблицы `items`, `carts`, `cart_items`, подключение и сессии.
- `main.py`: запросы SQLAlchemy вместо словарей. Каждая операция записи
  выполняется в отдельной транзакции и фиксируется до возврата ответа.
- В `cart_items` составной первичный ключ `(cart_id, item_id)` и внешние ключи.
  Перед добавлением товара блокируется строка корзины через `SELECT FOR UPDATE`,
  поэтому одновременные добавления не теряют количество и не создают дубликаты.

Товары удаляются логически, остаются в корзинах как недоступные и не входят в
их стоимость. Фильтры применяются до пагинации; цена и количество вычисляются
по актуальным данным. MySQL-сессии используют `REPEATABLE READ`, чтобы несколько
запросов при чтении корзин видели один снимок данных.

Таблицы создаются при первом запуске через `Base.metadata.create_all`.
Подключение задаётся `DATABASE_URL`. Без переменной локальный запуск использует
SQLite в `./shop.db`; контейнер без MySQL использует `/data/shop.db` в volume
`shop-data`. Это позволяет запускать исходные тесты ДЗ2 без отдельного сервера.
Проверки блокировок и сценарии изоляции выполняются на MySQL.

## Эксперименты с изоляцией

Запуск всех сценариев без установки Python-зависимостей на хосте:

```sh
docker compose -f hw3/docker-compose.yml -f hw4/docker-compose.yml run --rm --build transactions
```

Или локально, с уже запущенным MySQL:

```sh
python -m pip install -r hw2/hw/requirements.txt
python hw4/transactions.py
python hw4/transactions.py --scenario dirty
python hw4/transactions.py --scenario non-repeatable
python hw4/transactions.py --scenario phantom
```

Скрипт использует два независимых подключения, явно задаёт уровень изоляции
читателя и проверяет результаты. Последовательность SQL-запросов определяет
порядок событий; случайных задержек нет. Для каждого запуска создаётся отдельная
таблица `isolation_demo_<uuid>`, которая удаляется в конце; данные магазина
не меняются. При неожиданном результате скрипт завершается с ошибкой.

| Сценарий | Уровень изоляции | Результат |
| --- | --- | --- |
| Dirty read | READ UNCOMMITTED | Видно незакоммиченное значение 99; после отката снова 10 |
| Dirty read | READ COMMITTED | Незакоммиченное значение не видно: 10 |
| Non-repeatable read | READ COMMITTED | После чужого COMMIT повторное чтение меняется: 10 → 99 |
| Non-repeatable read | REPEATABLE READ | Оба чтения возвращают 10; новая транзакция видит 99 |
| Phantom read | READ COMMITTED | После вставки другой транзакцией число строк меняется: 1 → 2 |
| Phantom read | REPEATABLE READ | Вставка успешна, но снимок читателя сохраняет 1 строку |
| Phantom read | SERIALIZABLE | Вставка блокируется; читатель оба раза видит 1 строку |

В формулировке задания предложено показать фантомы при `REPEATABLE READ`,
но отдельно разрешены различия между БД. В MySQL/InnoDB обычные `SELECT` на
этом уровне читают один снимок и **уже не видят фантомов**. Поэтому скрипт
показывает фантом при `READ COMMITTED` и проверяет его отсутствие как при
`REPEATABLE READ`, так и при `SERIALIZABLE`.
См. [уровни изоляции MySQL](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html)
и [чтение из снимка](https://dev.mysql.com/doc/refman/8.4/en/innodb-consistent-read.html).

При `SERIALIZABLE` обычный `SELECT` в транзакции становится блокирующим чтением.
Скрипт ограничивает ожидание вставки одной секундой и проверяет именно ошибку
MySQL 1205 (lock wait timeout). После завершения транзакции читателя повторная
вставка проходит, а новая транзакция видит 2 строки. Остальные ошибки не скрываются.

Пример фактического вывода: [transactions-output.txt](transactions-output.txt).

## Проверка API

Установить зависимости и выполнить исходные тесты ДЗ2, тесты мониторинга и БД:

```sh
python -m pip install -r hw2/hw/requirements.txt -r hw3/requirements.txt
DATABASE_URL='mysql+pymysql://shop:shop@127.0.0.1:3307/shop?charset=utf8mb4' PYTHONPATH=hw2/hw:. python -m pytest hw2/hw/test_homework2.py hw2/hw/test_shop_api.py hw3/test_monitoring.py hw4/test_database.py -q
```

На MySQL проходят 53 теста: в том числе сохранность данных при переподключении,
откат неудачной транзакции и 32 параллельных добавления в одну корзину.
Без `DATABASE_URL` используются SQLite и файл `shop.db`; проверка блокировок
MySQL в этом случае пропускается.
