# ДЗ5 — тестирование Shop API

## Цель

1. Добиться покрытия минимум **95% строк** у API интернет-магазина из ДЗ2 (`hw2/hw/shop_api`).
2. Настроить GitHub Actions CI: установка зависимостей, запуск тестов и проверка порога покрытия. Пайплайн должен завершаться успешно только при успешных тестах и покрытии от 95%.

## Что добавлено

- `hw5/tests/test_shop_api_extra.py` — дополнительные тесты граничных случаев (несуществующие корзины и товары, фильтрация по цене, удалённые товары, обновление количества в корзине).
- `.github/workflows/hw5-tests.yml` — workflow для PR 


## Локальный запуск

Из корня репозитория установите зависимости:

```powershell
python -m pip install -r hw2/hw/requirements.txt pytest-cov
```

Для PowerShell задайте путь к пакету `shop_api` и запустите тесты:

```powershell
$env:PYTHONPATH = (Resolve-Path .\hw2\hw).Path
python -m pytest -v hw2/hw/test_homework2.py hw5/tests --cov=shop_api --cov-report=term-missing --cov-fail-under=95
```

В CI те же тесты запускаются в Linux с Python 3.13. Порог `--cov-fail-under=95` не позволит успешно завершить job при низком покрытии.

