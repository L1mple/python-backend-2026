# Отчёт по ДЗ 5: покрытие тестами HW2 и CI

## Что сделано

- Добавлены тесты для обработки отсутствующих корзин и товаров, проверки входных данных, фильтрации списка корзин, мягкого удаления товаров и расчёта стоимости корзины.
- Проверены WebSocket-рассылки между участниками одной комнаты, изоляция разных комнат, отключение отправителя и удаление недоступного клиента.
- Добавлен `requirements-hw5.txt`, который включает `requirements.txt` и добавляет `pytest-cov`; зависимости существующего HW2 pipeline не меняются.
- Добавлен отдельный workflow `.github/workflows/hw5-tests.yml`: он поднимает PostgreSQL 15 с health check, задаёт приложению `DATABASE_URL` и запускает тесты на Python 3.13 и 3.14. Job выводит пропущенные строки и завершается с ошибкой, если покрытие `shop_api` ниже 95%.
- Новый workflow запускается при изменении файлов HW2 или самого workflow: при push в любую ветку и при pull request в `main`. Существующий workflow `.github/workflows/hw2-tests.yml` оставлен без изменений.

## Покрытие

Проверка выполнена на PostgreSQL 15 — той же основной версии, что используется в `docker-compose.yml`.

| Python | Тесты | `shop_api` | `main.py` | `database.py` |
| --- | ---: | ---: | ---: | ---: |
| 3.13 | 47 passed | 96.79% | 100% | 83% |
| 3.14 | 47 passed | 96.76% | 100% | 83% |

Покрытие `database.py` ниже, потому что CI запускает PostgreSQL и не исполняет SQLite-specific создание engine и обработчик внешних ключей. Общее покрытие пакета остаётся выше требуемых 95%.

## Запуск тестов

Из корня репозитория:

```bash
cd hw2/hw
pip install -r requirements-hw5.txt
PYTHONPATH="$PWD" pytest -v --cov=shop_api --cov-report=term-missing --cov-fail-under=95
```

## CI

После push GitHub Actions запускает отдельную проверку покрытия. Результаты доступны в [workflow HW5 Coverage](https://github.com/AlexeyVorobyev/python-backend-2026/actions/workflows/hw5-tests.yml).
