# Демонстрация уровней изоляции PostgreSQL

В этой папке находятся четыре независимых сценария, которые показывают, как уровни изоляции влияют на параллельные транзакции.

## Как запустить

Команды нужно выполнять из папки `hw4`.

Сначала запустите PostgreSQL и приложение:

```bash
docker compose up -d --build postgres app
```

Затем запустите нужный сценарий:

```bash
docker compose exec app python -m transaction_levels.dirty_read
docker compose exec app python -m transaction_levels.non_repeatable_read
docker compose exec app python -m transaction_levels.phantom_read
docker compose exec app python -m transaction_levels.serialization_anomaly
```

Скрипты запускаются как модули Python, поэтому используется формат `python -m`. В самих скриптах нет итоговых сообщений: вывод показывает только порядок SQL-команд и прочитанные значения.

## Таблица doctors

Все сценарии работают с одной таблицей `doctors`. Перед каждым сценарием она создаётся и наполняется двумя дежурными врачами:

```sql
CREATE TABLE doctors(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    on_call BOOLEAN NOT NULL
);

INSERT INTO doctors(id, name, on_call) VALUES
    (1, 'Alice', true),
    (2, 'Bob', true);
```

После завершения сценария таблица `doctors` удаляется.

## 1. Dirty read

Dirty read — чтение одной транзакцией данных, которые другая транзакция ещё не зафиксировала через `COMMIT`.

Сценарий:

1. T1 изменяет `on_call` у Alice на `false`, но не выполняет `COMMIT`.
2. T2 читает Alice до завершения T1.
3. T1 выполняет `ROLLBACK`.
4. T2 повторно читает Alice.

```bash
docker compose exec app python -m transaction_levels.dirty_read

T1 (Read Committed): BEGIN ISOLATION LEVEL READ COMMITTED
T2 (Read Uncommitted): BEGIN ISOLATION LEVEL READ UNCOMMITTED
T1 (Read Committed): UPDATE doctors SET on_call = false WHERE id = 1
T2 (Read Uncommitted): SELECT on_call FROM doctors WHERE id = 1
T2 (Read Uncommitted): получил значение True
T1 (Read Committed): ROLLBACK
T2 (Read Uncommitted): SELECT on_call FROM doctors WHERE id = 1
T2 (Read Uncommitted): получил значение True
T2 (Read Uncommitted): ROLLBACK

T1 (Read Committed): BEGIN ISOLATION LEVEL READ COMMITTED
T2 (Read Committed): BEGIN ISOLATION LEVEL READ COMMITTED
T1 (Read Committed): UPDATE doctors SET on_call = false WHERE id = 1
T2 (Read Committed): SELECT on_call FROM doctors WHERE id = 1
T2 (Read Committed): получил значение True
T1 (Read Committed): ROLLBACK
T2 (Read Committed): SELECT on_call FROM doctors WHERE id = 1
T2 (Read Committed): получил значение True
T2 (Read Committed): ROLLBACK
```

Скрипт сравнивает `READ UNCOMMITTED` и `READ COMMITTED`. В PostgreSQL `READ UNCOMMITTED` фактически работает как `READ COMMITTED`, поэтому грязное чтение не возникает.

## 2. Non-repeatable read

Non-repeatable read — ситуация, когда одна транзакция дважды читает одну строку и получает разные значения, потому что другая транзакция изменила и зафиксировала эту строку между чтениями.

Сценарий:

1. T1 читает `on_call` у Alice.
2. T2 меняет значение Alice на `false` и выполняет `COMMIT`.
3. T1 повторно читает Alice.

Вывод скрипта:

```bash
docker compose exec app python -m transaction_levels.non_repeatable_read

T1 (Read Committed): BEGIN ISOLATION LEVEL READ COMMITTED
T2 (Read Committed): BEGIN ISOLATION LEVEL READ COMMITTED
T1 (Read Committed): SELECT on_call FROM doctors WHERE id = 1
T1 (Read Committed): получил значение True
T2 (Read Committed): UPDATE doctors SET on_call = false WHERE id = 1
T2 (Read Committed): COMMIT
T1 (Read Committed): SELECT on_call FROM doctors WHERE id = 1
T1 (Read Committed): получил значение False
T1 (Read Committed): ROLLBACK

T1 (Repeatable Read): BEGIN ISOLATION LEVEL REPEATABLE READ
T2 (Read Committed): BEGIN ISOLATION LEVEL READ COMMITTED
T1 (Repeatable Read): SELECT on_call FROM doctors WHERE id = 1
T1 (Repeatable Read): получил значение True
T2 (Read Committed): UPDATE doctors SET on_call = false WHERE id = 1
T2 (Read Committed): COMMIT
T1 (Repeatable Read): SELECT on_call FROM doctors WHERE id = 1
T1 (Repeatable Read): получил значение True
T1 (Repeatable Read): ROLLBACK
```

В `READ COMMITTED` каждый `SELECT` получает новый снимок данных. В `REPEATABLE READ` транзакция продолжает использовать один и тот же снимок, поэтому повторное чтение возвращает прежнее значение.

## 3. Phantom read

Phantom read — появление новых строк, подходящих под тот же фильтр, между двумя одинаковыми запросами одной транзакции.

Сценарий:

1. T1 считает количество дежурных врачей.
2. T2 добавляет Charlie с `on_call = true` и выполняет `COMMIT`.
3. T1 повторяет тот же `SELECT count(*)`.

Вывод скрипта:

```bash
docker compose exec app python -m transaction_levels.phantom_read

T1 (Repeatable Read): BEGIN ISOLATION LEVEL REPEATABLE READ
T2 (Read Committed): BEGIN ISOLATION LEVEL READ COMMITTED
T1 (Repeatable Read): SELECT count(*) FROM doctors WHERE on_call
T1 (Repeatable Read): получил значение 2
T2 (Read Committed): INSERT INTO doctors(id, name, on_call) VALUES (3, 'Charlie', true)
T2 (Read Committed): COMMIT
T1 (Repeatable Read): SELECT count(*) FROM doctors WHERE on_call
T1 (Repeatable Read): получил значение 2
T1 (Repeatable Read): ROLLBACK

T1 (Serializable): BEGIN ISOLATION LEVEL SERIALIZABLE
T2 (Read Committed): BEGIN ISOLATION LEVEL READ COMMITTED
T1 (Serializable): SELECT count(*) FROM doctors WHERE on_call
T1 (Serializable): получил значение 2
T2 (Read Committed): INSERT INTO doctors(id, name, on_call) VALUES (3, 'Charlie', true)
T2 (Read Committed): COMMIT
T1 (Serializable): SELECT count(*) FROM doctors WHERE on_call
T1 (Serializable): получил значение 2
T1 (Serializable): ROLLBACK
```

В PostgreSQL `REPEATABLE READ` основан на снимке транзакции и также предотвращает phantom read, хотя минимальное требование стандарта SQL для этого уровня слабее.

## 4. Serialization anomaly / write skew

Write skew — аномалия, при которой две транзакции читают одно и то же согласованное состояние, изменяют разные строки, а после совместной фиксации нарушают общее бизнес-правило.

В сценарии есть два дежурных врача. Каждая транзакция видит двух дежурных и выключает одного своего врача:

```bash
T1: UPDATE doctors SET on_call = false WHERE id = 1
T2: UPDATE doctors SET on_call = false WHERE id = 2
```

Вывод скрипта:

```bash
docker compose exec app python -m transaction_levels.serialization_anomaly

T1 (Repeatable Read): BEGIN ISOLATION LEVEL REPEATABLE READ
T2 (Repeatable Read): BEGIN ISOLATION LEVEL REPEATABLE READ
T1 (Repeatable Read): SELECT count(*) FROM doctors WHERE on_call
T1 (Repeatable Read): получил значение 2
T2 (Repeatable Read): SELECT count(*) FROM doctors WHERE on_call
T2 (Repeatable Read): получил значение 2
T1 (Repeatable Read): UPDATE doctors SET on_call = false WHERE id = 1
T2 (Repeatable Read): UPDATE doctors SET on_call = false WHERE id = 2
T1 (Repeatable Read): COMMIT
T2 (Repeatable Read): COMMIT
T1 (Read Committed): BEGIN ISOLATION LEVEL READ COMMITTED
T1 (Read Committed): SELECT count(*) FROM doctors WHERE on_call
T1 (Read Committed): получил значение 0
T1 (Read Committed): ROLLBACK

T1 (Serializable): BEGIN ISOLATION LEVEL SERIALIZABLE
T2 (Serializable): BEGIN ISOLATION LEVEL SERIALIZABLE
T1 (Serializable): SELECT count(*) FROM doctors WHERE on_call
T1 (Serializable): получил значение 2
T2 (Serializable): SELECT count(*) FROM doctors WHERE on_call
T2 (Serializable): получил значение 2
T1 (Serializable): UPDATE doctors SET on_call = false WHERE id = 1
T2 (Serializable): UPDATE doctors SET on_call = false WHERE id = 2
T1 (Serializable): COMMIT
T2 (Serializable): COMMIT
T2 (Serializable): COMMIT -> SERIALIZATION FAILURE (40001)
T1 (Read Committed): BEGIN ISOLATION LEVEL READ COMMITTED
T1 (Read Committed): SELECT count(*) FROM doctors WHERE on_call
T1 (Read Committed): получил значение 1
T1 (Read Committed): ROLLBACK
```

В `REPEATABLE READ` обе транзакции фиксируются, и итоговое количество дежурных становится `0`: возникает serialization anomaly. В `SERIALIZABLE` PostgreSQL отменяет T2 с ошибкой `40001`, поэтому итоговое количество дежурных равно `1`. После этого приложение должно повторить отменённую транзакцию.
