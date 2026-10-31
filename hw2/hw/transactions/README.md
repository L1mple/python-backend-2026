# Транзакции и уровни изоляции

Рассмотрим проблемы параллельного выполнения транзакций: Dirty Read, Non-repeatable Read и Phantom Read. Для экспериментов используем SQLite и библиотеку SQLAlchemy.

## Структура

```text
transactions/
├── database.py
├── dirty_read.py
├── dirty_read_prevention.py
├── non_repeatable_read.py
├── phantom_read.py
├── serializable.py
└── data/
```

## Запуск

Из директории `hw2/hw`:

```bash
python -m transactions.database
python -m transactions.dirty_read
python -m transactions.dirty_read_prevention
python -m transactions.non_repeatable_read
python -m transactions.phantom_read
python -m transactions.serializable
```

## Эксперименты

**1. Dirty Read (`dirty_read.py`)**

Одна транзакция изменяет цену товара, но не фиксирует изменения. Другая транзакция читает новое значение. Для этого используется `shared cache` и `PRAGMA read_uncommitted = 1`.

Результат: удалось прочитать незафиксированные данные. После отката первой транзакции изменение исчезло.

**2. Предотвращение Dirty Read (`dirty_read_prevention.py`)**

Повторяем эксперимент с `PRAGMA read_uncommitted = 0`.

Результат: SQLite блокирует чтение таблицы, пока другая транзакция не завершит запись. Dirty Read не происходит.

**3. Non-repeatable Read (`non_repeatable_read.py`)**

Первая транзакция читает цену товара. Вторая изменяет её и фиксирует изменения. Первая транзакция повторяет запрос.

Результат: значение не изменилось. В режиме WAL SQLite сохраняет снимок базы данных для читающей транзакции.

**4. Phantom Read (`phantom_read.py`)**

Первая транзакция выбирает товары дороже 100. Вторая добавляет новый подходящий товар. Первая повторяет запрос.

Результат: новый товар не появился в выборке. SQLite продолжает использовать исходный снимок данных.

**5. Serializable (`serializable.py`)**

Первая транзакция читает товар, после чего вторая изменяет его и фиксирует изменения. Первая пытается выполнить запись на основании старого снимка.

Результат: SQLite отклоняет операцию первой транзакции. Изменения второй транзакции сохраняются.

## SQLite

SQLite не поддерживает отдельные уровни `READ COMMITTED` и `REPEATABLE READ`, поэтому эксперименты показывают поведение самой SQLite, а не переключение между этими уровнями изоляции. Конфликтующие изменения также успешно предотвращаются.