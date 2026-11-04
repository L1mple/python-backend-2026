# ДЗ5: решение

ДЗ5 выполнено на сервисе из ДЗ2 с хранением в БД (версия с PostgreSQL лежит в папке hw4).

1. Покрытие тестами: 100% кода shop_api (требовалось 95%).
   - тесты: hw4/test_homework2.py (исходные тесты ДЗ2) и hw4/tests/
   - запуск: cd hw4 && pytest --cov=shop_api --cov-report=term-missing --cov-fail-under=95
2. Автозапуск в CI с PostgreSQL как сервисным контейнером (Python 3.13 и 3.14):
   .github/workflows/hw4-tests.yml
   Описание и результаты: hw4/README.md
