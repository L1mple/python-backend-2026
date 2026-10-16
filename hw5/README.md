# ДЗ5: тесты магазина

Дополнены тесты API из HW2. Проверяются неизвестные ID, некорректные параметры,
изменение и удаление товаров в корзине, фильтры, пагинация и `/metrics`.
Тесты курса сохранены без изменений. Также запускаются проверки сохранения
данных и параллельных запросов из HW4.

Покрытие считается для всего пакета `shop_api`: `main.py`, `database.py`
и `__init__.py`. Учитываются строки и ветвления; файлы приложения
из отчёта не исключаются. Минимум — 95%, он задан в `coverage.ini`.

## Локальный запуск

Из корня репозитория, после запуска PostgreSQL из HW4:

```sh
pip install -r hw5/requirements.txt
docker compose -f hw4/docker-compose.yml up -d --wait db
docker compose -f hw4/docker-compose.yml exec db createdb -U shop shop_hw5_tests
```

Базу `shop_hw5_tests` нужно создать один раз. Затем в PowerShell:

```powershell
$env:PYTHONPATH = "$PWD/hw2/hw"
$env:DATABASE_URL = 'postgresql+psycopg://shop:shop@127.0.0.1:7433/shop_hw5_tests'
python -m pytest hw2/hw/test_homework2.py hw4 hw5 -v --cov=shop_api --cov-config=hw5/coverage.ini --cov-report=term-missing
```

Для запуска без PostgreSQL можно указать SQLite-файл в `DATABASE_URL`:

```powershell
$env:DATABASE_URL = 'sqlite:///./shop.db'
```

При этом проверка параллельного добавления из HW4 будет пропущена:
она проверяет блокировки строк PostgreSQL.

Новые API-тесты используют отдельную транзакцию с savepoint для каждого
запроса. В начале теста таблицы очищаются внутри внешней транзакции,
а в конце она откатывается вместе со всеми изменениями теста.
Тесты курса и HW4 создают свои записи, поэтому для всего набора
следует использовать отдельную тестовую БД.

## CI

Workflow `.github/workflows/hw5-tests.yml` поднимает PostgreSQL 15,
устанавливает зависимости и запускает весь набор с проверкой покрытия.
Если тест падает или покрытие ниже 95%, проверка завершается с ошибкой.
XML-отчёт доступен в артефакте `shop-coverage`.

Результат локального запуска с PostgreSQL: **68 тестов прошли,
покрытие строк и ветвлений — 100%**.
