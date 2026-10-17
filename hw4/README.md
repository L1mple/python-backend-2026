# HW4 — PostgreSQL, SQLAlchemy и изоляция транзакций

Реализация задания из `lecture4/README.md`

## Что сделано

1. В Docker Compose настроены два сервиса: **PostgreSQL 16** и **Shop API**.
2. API из ДЗ2 (`item`, `cart`) переведено с глобальных словарей в оперативной памяти на **SQLAlchemy ORM**. Данные товаров, корзин и их содержимого сохраняются в PostgreSQL даже после перезапуска API. Исходные `hw2` и `hw3` не меняются.
3. `isolation_demo.py` запускает параллельные транзакции, измеряет результаты чтений и демонстрирует изоляционные аномалии (см. таблицу ниже).

## Запуск в Windows PowerShell

Перейдите в корень репозитория `python-backend-2026` и запустите Docker Desktop.

```powershell
docker compose -f hw4/docker-compose.yml up --build -d
docker compose -f hw4/docker-compose.yml ps
```

После запуска:

- API + Swagger: http://localhost:8001/docs
- PostgreSQL: `127.0.0.1:5433`, база `shop`, пользователь `shop`, пароль `shop` (учебные локальные учётные данные).

Создание таблиц происходит автоматически при старте приложения через `Base.metadata.create_all()`; для учебного проекта миграции не используются.

### Пример работы с API

```powershell
$item = Invoke-RestMethod -Method Post -Uri http://localhost:8001/item -ContentType "application/json" -Body '{"name":"Milk","price":149.9}'
$cart = Invoke-RestMethod -Method Post -Uri http://localhost:8001/cart
Invoke-RestMethod -Method Post -Uri "http://localhost:8001/cart/$($cart.id)/add/$($item.id)"
Invoke-RestMethod -Uri "http://localhost:8001/cart/$($cart.id)"
```

перезапустить `api`, **не удаляя том PostgreSQL**, и снова запросить товары:

```powershell
docker compose -f hw4/docker-compose.yml restart api
Invoke-RestMethod -Uri http://localhost:8001/item
```

## Демонстрация уровней изоляции (пункт 3)

```powershell
docker compose -f hw4/docker-compose.yml exec api python isolation_demo.py
```

Один запуск создаёт отдельные таблицы `hw4_tx_*`, выполняет эксперименты и проверяет результаты через `assert`. Таблицы магазина при этом не изменяются. Запускать скрипт нужно **один раз за раз**, без одновременных запусков: между опытами данные сбрасываются.

| Аномалия / сценарий | Уровень изоляции PostgreSQL | Результат |
|---|---|---|
| Dirty read: T1 изменила значение без `COMMIT`, T2 читает | READ UNCOMMITTED | **Грязного чтения нет**: PostgreSQL трактует этот уровень как READ COMMITTED |
| Dirty read | READ COMMITTED | Грязного чтения нет |
| Non-repeatable read: T2 изменила значение и закоммитила между двумя SELECT T1 | READ COMMITTED | **Возникает:** T1 читает 100, затем 200 |
| Non-repeatable read | REPEATABLE READ | Нет: T1 читает 100, затем 100 |
| Phantom read: T2 добавила строку между двумя `COUNT(*)` T1 | READ COMMITTED | **Возникает:** T1 считает 1, затем 2 |
| Phantom read | REPEATABLE READ | **Нет:** PostgreSQL использует snapshot isolation, оба чтения дают 1 |
| Phantom read | SERIALIZABLE | Нет: оба чтения дают 1 |
| Write skew: оба врача одновременно снимают себя с дежурства | REPEATABLE READ | Обе транзакции проходят, дежурных остаётся 0 |
| Write skew | SERIALIZABLE | Одна транзакция откатывается с SQLSTATE `40001`, остаётся 1 дежурный |

**Почему пункты «dirty read при READ UNCOMMITTED» и «phantom read при REPEATABLE READ» нельзя воспроизвести буквально?** Это особенности реализации PostgreSQL, а не ошибка скрипта. PostgreSQL не поддерживает грязное чтение и предотвращает фантомы уже при REPEATABLE READ. В качестве дополнительного сценария показан **write skew** — настоящая аномалия REPEATABLE READ, которую предотвращает SERIALIZABLE.


