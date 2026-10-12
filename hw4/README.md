добавлена PostgreSQL, товары и корзины хранятся в базе данных. Скрипт `isolation/demo.py` демонстрирует аномалии транзакций на разных уровнях изоляции.
## Запуск
```bash
docker compose up --build
```
## Тесты
```bash
PYTHONPATH=. pytest test_homework2.py -v
```
Тесты используют SQLite в памяти.

## Проверка изоляции транзакций
При запущенном Docker Compose

```bash
export DATABASE_URL=postgresql+psycopg2://shop:shop@localhost:7432/shop
python -m isolation.demo
```
Скрипт проверяет dirty read, non-repeatable read и phantom read. 
Подробно сценарии описаны при запуске demo.py 