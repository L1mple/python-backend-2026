# API магазина с хранением в БД

Это продолжение ДЗ2. В ветках hw2/hw3 используется память процесса,
а в этой ветке данные уже сохраняются через SQLAlchemy (задание ДЗ4).

Из корня установите `python -m pip install -r hw2/hw/requirements.txt`.
Локальный запуск из hw2/hw:
`python -m uvicorn shop_api.main:app --host 127.0.0.1 --port 28000 --reload`.

Без переменной SHOP_DATABASE_URL создаётся файл hw2/hw/shop.db (SQLite).
В Docker используется PostgreSQL. Инструкция ДЗ4: docs/HW4.md.
Исходные тесты из hw2/hw: `python -m pytest test_homework2.py -v`.
Дополнительный WebSocket-чат не реализован.
