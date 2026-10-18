# HW4: транзакции и уровни изоляции

Я взяла PostgreSQL. В нём нет настоящего `READ UNCOMMITTED` (эмулируется как `READ COMMITTED`), поэтому dirty read в PG невозможен. Преподаватель это разрешил в чате курса.

## Соответствие заданию

| #   | Что просили                                   | Что показываю                                                      | Файл                     |
| --- | --------------------------------------------- | ------------------------------------------------------------------ | ------------------------ |
| 1   | Dirty read при `READ UNCOMMITTED`             | Не воспроизводится: T2 видит старое значение (100), не новое (200) | `dirty_read_attempt.py`  |
| 2   | Нет dirty read при `READ COMMITTED`           | То же — не воспроизводится                                         | `dirty_read_attempt.py`  |
| 3   | Non-repeatable read при `READ COMMITTED`      | Воспроизводится: 100 → 200                                         | `non_repeatable_read.py` |
| 4   | Нет non-repeatable read при `REPEATABLE READ` | Исчезает: 100 → 100                                                | `non_repeatable_read.py` |
| 5   | Phantom read при `REPEATABLE READ`            | В PG не воспроизводится (snapshot isolation)                       | `phantom_read.py`        |
| 6   | Нет phantom read при `SERIALIZABLE`           | Исчезает: count не меняется                                        | `phantom_read.py`        |

## Почему phantom read не показываю «в лоб»

PostgreSQL реализует `REPEATABLE READ` через snapshot isolation, поэтому phantom read в нём не возникает ни на `REPEATABLE READ`, ни на `SERIALIZABLE`. Показываю, что его нет на обоих уровнях.

## Как запустить

```bash
cd hw3
docker compose up -d db
docker compose ps          # дождись healthy

cd transactions
python dirty_read_attempt.py
python non_repeatable_read.py
python phantom_read.py
```
