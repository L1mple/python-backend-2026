# Демонстрация уровней изоляции транзакций

Скрипты используют Postgres из `../docker-compose.yml` (localhost:7432, БД `shop_db`).

Запуск:

```sh
docker compose up -d postgres
cd isolation
python dirty_read.py
python non_repeatable_read.py
python phantom_reads.py
