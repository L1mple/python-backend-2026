# ДЗ4 

Во вторую домашнюю работу добавлено постоянное хранение данных в PostgreSQL 15 с использованием SQLAlchemy 2.0.

В Docker Compose добавлен сервис PostgreSQL. Реализованы ORM-модели для таблиц:

- `items` — товары;
- `carts` — корзины;
- `cart_items` — связь корзин и товаров с указанием количества.

Операции создания, чтения, изменения и удаления товаров, а также работа с корзинами переведены на SQLAlchemy.

Таблицы автоматически создаются при запуске Shop API.



## Эксперименты с транзакциями

Для каждого эксперимента используются два независимых подключения к PostgreSQL.

### 1. Dirty Read

Файл: `dirty_read.py`

Первая транзакция изменяет значение 100 на 200 без COMMIT. Вторая транзакция пытается прочитать изменение.

| Уровень | Прочитано | Dirty Read |
|---|---|---|
| READ UNCOMMITTED | 100 | Нет |
| READ COMMITTED | 100 | Нет |

PostgreSQL не допускает грязного чтения. Уровень READ UNCOMMITTED фактически работает как READ COMMITTED.

### 2. Non-repeatable Read

Файл: `non_repeatable_read.py`

| Уровень | Первое чтение | Второе чтение |
|---|---|---|
| READ UNCOMMITTED | 100 | 200 |
| READ COMMITTED | 100 | 200 |
| REPEATABLE READ | 100 | 100 |
| SERIALIZABLE | 100 | 100 |

Неповторяемое чтение возникает на READ COMMITTED и предотвращается на REPEATABLE READ.

### 3. Phantom Read

Файл: `phantom_read.py`

| Уровень | Первое чтение | Второе чтение |
|---|---|---|
| READ UNCOMMITTED | 1 | 2 |
| READ COMMITTED | 1 | 2 |
| REPEATABLE READ | 1 | 1 |
| SERIALIZABLE | 1 | 1 |

В PostgreSQL фантомное чтение предотвращается уже на уровне REPEATABLE READ благодаря MVCC.

## Запуск

Из корня репозитория:

```bash
docker compose -f hw3/docker-compose.yml up -d --build
```

Запуск экспериментов:

```bash
docker compose -f hw3/docker-compose.yml exec shop python hw4/dirty_read.py
docker compose -f hw3/docker-compose.yml exec shop python hw4/non_repeatable_read.py
docker compose -f hw3/docker-compose.yml exec shop python hw4/phantom_read.py
```



