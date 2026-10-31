# ДЗ2: API магазина

Реализованы ручки товаров и корзин из README. Данные хранятся в словарях в памяти
одного процесса. Это разрешено условиями ДЗ2. После перезапуска сервера данные
пропадают; хранение в БД добавлено отдельно в ветке hw4.

Из корня репозитория:

```powershell
conda activate python-backend
python -m pip install -r hw2/hw/requirements.txt
cd hw2/hw
python -m uvicorn shop_api.main:app --host 127.0.0.1 --port 28000 --reload
```

Документация API: http://127.0.0.1:28000/docs.
В другом терминале из hw2/hw: `python -m pytest test_homework2.py -v`.

Исходные тесты преподавателя не изменены. Дополнительный WebSocket-чат не реализован.
