# ДЗ4: база данных и транзакции

Продолжение магазина из ДЗ2 с инфраструктурой из ДЗ3. В этой ветке добавлено
хранение товаров и корзин через SQLAlchemy. В Docker используется PostgreSQL 17,
без Docker по умолчанию создаётся файл hw2/hw/shop.db (SQLite).

```powershell
python -m pip install -r hw2/hw/requirements.txt
docker compose up -d --build --wait
python scripts/transaction_demo.py
```

API: http://127.0.0.1:28000/docs.
Из hw2/hw можно запустить исходные тесты: `python -m pytest test_homework2.py -v`.

Семь проверок и особенности PostgreSQL описаны в [HW4_TRANSACTIONS.md](HW4_TRANSACTIONS.md).
Фактический вывод: [transaction-results.txt](transaction-results.txt).
Обычный `docker compose down` сохраняет данные PostgreSQL в volume.
