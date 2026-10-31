# ДЗ5: тестирование и CI

Добавлены тесты к магазину с БД из ДЗ4. Исходные тесты преподавателя не изменены.
CI проверяет Python 3.13/3.14 и SQLite/PostgreSQL. Порог покрытия строк и ветвлений — 95%.

Из корня: `python -m pip install -r hw2/hw/requirements-dev.txt`.
Затем из hw2/hw:

```powershell
python -m pytest test_homework2.py tests -v --cov=shop_api --cov-branch --cov-report=term-missing --cov-fail-under=95
```

Локальная проверка: SQLite — 95 тестов, 97,06%; PostgreSQL — 95 тестов, 96,64%.
По умолчанию тесты используют отдельную SQLite в памяти, данные магазина не трогают.
Для PostgreSQL укажите SHOP_DATABASE_URL с отдельной БД shop_test.
Тестовые таблицы в этой БД очищаются перед и после тестов.

Workflow: .github/workflows/shop-tests.yml. Срабатывает при push в hw5/main и при PR в main.
Четыре задания должны завершиться успешно, XML покрытия сохраняется как артефакт.
В заданиях PostgreSQL также проверяются примеры изоляции транзакций.
