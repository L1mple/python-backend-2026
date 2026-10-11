# Изоляция транзакций: H2 2.5.252

[H2](https://h2database.com/html/main.html) — небольшая реляционная SQL-БД,
написанная на Java; она может работать в памяти без отдельного сервера.
Здесь она используется только для опытов с изоляцией. Магазин хранит данные
в PostgreSQL, где [READ_UNCOMMITTED работает как READ_COMMITTED](https://www.postgresql.org/docs/17/transaction-iso.html),
поэтому dirty read на нём показать нельзя. H2 позволяет наблюдать эту аномалию.

Java 21/JDBC выполняет шесть опытов с двумя настоящими транзакциями.
Python читает JSONL-журнал и строит временные диаграммы. Java выбран как
прямой доступ к H2 с управлением изоляцией, соединениями и таймаутами;
язык клиента не определяет поведение транзакций.

**Ограничение задания:** на H2 2.5.252 повторный запрос к уже прочитанной
таблице при REPEATABLE_READ не видит вставленную строку. Поэтому пятый опыт
честно фиксирует отсутствие phantom read: `1 → 1`. Он не демонстрирует
требуемый в `lecture4/README.md` phantom read при REPEATABLE_READ.
Остальные пять опытов соответствуют ожидаемому результату задания.

## Можно ли сделать это на Python

Да. [JayDeBeApi](https://github.com/baztian/jaydebeapi) предоставляет Python
DB-API через JPype и JDBC: сценарии можно написать на Python, но JVM и H2 jar
всё равно нужны. Другой путь — запустить H2 с PostgreSQL-совместимым сетевым
сервером и подключиться из Python через `psycopg`. Тогда JVM работает только
на стороне H2. Это остаётся H2, а не PostgreSQL: изоляция определяется H2.
Его [PG-протокол](https://h2database.com/html/advanced.html#odbc_driver)
экспериментальный, реализован частично и не поддерживает отмену запросов;
для текущей лаборатории оставлен JDBC.

Для ручного наблюдения подходит [H2 Console](https://h2database.com/html/tutorial.html#tutorial_starting_h2_console):
нужны две отдельные SQL-сессии одной БД, отключённый autocommit и порядок
операций из раздела ниже. Одна сессия читает, другая изменяет данные и делает
COMMIT или ROLLBACK. Это позволяет увидеть те же значения без написания Java,
но автоматический runner дополнительно сохраняет порядок событий в журнал.

| Опыт | Изоляция T1 и T2 | Изменение T2 | Чтения T1 | Наблюдение |
|---|---|---|---|---|
| `dirty_ru` | READ_UNCOMMITTED | UPDATE без коммита, затем ROLLBACK | 100 → 200 → 100 | Dirty read есть; откат возвращает исходное значение |
| `dirty_rc` | READ_COMMITTED | UPDATE без коммита, затем ROLLBACK | 100 → 100 → 100 | Dirty read нет |
| `nonrepeatable_rc` | READ_COMMITTED | UPDATE и COMMIT | 100 → 200 | Non-repeatable read есть |
| `nonrepeatable_rr` | REPEATABLE_READ | UPDATE и COMMIT | 100 → 100 | Non-repeatable read нет |
| `phantom_rr` | REPEATABLE_READ | INSERT и COMMIT | 1 → 1 строка | Phantom read не воспроизводится на этой версии |
| `phantom_serializable` | SERIALIZABLE | INSERT и COMMIT | 1 → 1 строка | Phantom read нет |

## Запуск

Нужны Docker с работающим daemon и `uv`. Команды из корня репозитория:

```bash
docker build -t h2-isolation hw4/isolation
mkdir -p hw4/isolation/results
for run in 1 2 3; do
  docker run --rm \
    -v "$PWD/hw4/isolation/results:/output" \
    h2-isolation "/output/run-$run.jsonl" || exit 1
done

cd hw4/isolation
uv venv --python 3.13
uv pip install -r requirements.txt
uv run --no-project python -m unittest -v
for run in 1 2 3; do
  uv run --no-project python visualize.py "results/run-$run.jsonl" "results/run-$run.png" || exit 1
done
```

Для проверки Python 3.14 создайте отдельное окружение:

```bash
uv venv --python 3.14 /tmp/h2-python314
uv pip install --python /tmp/h2-python314/bin/python -r requirements.txt
uv run --no-project --python /tmp/h2-python314/bin/python python -m unittest -v
```

Dockerfile использует стандартные multiarch-образы Eclipse Temurin 21,
без привязки к архитектуре. Локальные свидетельства получены на Linux arm64
в Docker Desktop; дополнительный CI запускает Docker на Ubuntu amd64
и визуализатор на Python 3.13/3.14 для PR с bases `main`, `hw2`, `hw3`.
JDBC jar загружается при сборке с Maven Central; версия и SHA-256 зафиксированы.
`javac --release 21 -Xlint:all -Werror` входит в сборку.

## Порядок транзакций

Каждый опыт создаёт собственную in-memory БД и таблицу
`accounts(id INT PRIMARY KEY, balance INT NOT NULL)` с одной строкой `(1, 100)`.
Для dirty/non-repeatable read используется
`SELECT balance FROM accounts WHERE id = 1`.
Для phantom read оба чтения выполняют один и тот же запрос:

```sql
SELECT id, balance FROM accounts WHERE balance >= 100 ORDER BY id;
```

Runner полностью читает ResultSet и сравнивает число строк; изменение T2:
`INSERT INTO accounts VALUES (2, 150)`. Смена изоляции или новый BEGIN между
чтениями не используются. Начальная схема создаётся до двух рабочих транзакций.

Два потока владеют отдельными JDBC-соединениями с `autoCommit=false`.
CountDownLatch обеспечивает последовательность:

1. T1 выполняет первое чтение, затем разрешает изменение T2.
2. Для dirty read T2 меняет строку и ждёт второго чтения T1 перед откатом.
3. Для остальных случаев T2 сначала коммитит и только затем разрешает второе чтение.
4. Для dirty read T1 дополнительно проверяет исходное значение после ROLLBACK T2.

Вместо `sleep` используются ограниченные ожидания барьеров (15 секунд),
JDBC query timeout (15 секунд), lock timeout (5 секунд) и таймауты futures.
Неверное значение или сбой синхронизации завершает процесс с ненулевым кодом.
При исключении незавершённое соединение закрывается, рабочие потоки прерываются.
`PASS` пишется только после успешного завершения обеих транзакций.

## Журнал и свидетельства

В [evidence](evidence/) сохранены три успешных независимых запуска:

- [run-1.jsonl](evidence/run-1.jsonl) и [run-1.png](evidence/run-1.png);
- [run-2.jsonl](evidence/run-2.jsonl) и [run-2.png](evidence/run-2.png);
- [run-3.jsonl](evidence/run-3.jsonl) и [run-3.png](evidence/run-3.png).

Каждый PNG содержит все шесть опытов. Подписи показывают настоящие результаты;
ось X — измеренное время каждого события относительно начала опыта.
Длительность включает JDBC и запись/flush журнала, поэтому это иллюстрация
порядка операций, а не benchmark.

JSONL содержит `seq` (глобальный порядок), `case`, `isolation`, `tx`
(`T1`, `T2`, `LAB`), `event`, `value` и `elapsed_ms` (монотонное время
от открытия журнала). Для BEGIN/COMMIT/ROLLBACK `value` равно `null`;
для READ — прочитанному значению/числу строк, UPDATE/INSERT — balance,
PASS — проверенному второму чтению. Запись журнала синхронизирована между потоками.

Визуализатор проверяет схему, порядок, все шесть случаев, реальные значения
и взаимный порядок чтений, записи, коммита и отката. Неполный или противоречивый
журнал не превращается в диаграмму. Unit-тесты проверяют три свидетельства,
повреждённые журналы, нарушенный порядок и создание PNG. CI дополнительно
трижды запускает реальные JDBC-опыты и сохраняет новые JSONL/PNG как artifacts.

## Почему REPEATABLE_READ не показал phantom

[Официальная документация H2](https://h2database.com/html/advanced.html#transaction_isolation)
указывает, что phantom reads возможны при REPEATABLE_READ. Однако в исходниках
именно 2.5.252 (`h2-2.5.252-sources.jar` с Maven Central):

- `SessionLocal.startStatementWithinTransaction` сохраняет снимки индексов
  всех таблиц, от которых зависит запрос;
- `Transaction.markStatementEnd` сохраняет эти снимки при REPEATABLE_READ;
- `TransactionMap.CommittedIterator` использует сохранённый `getSnapshot()`.

Поэтому повторный SELECT этой таблицы видит прежний набор строк. Проверка
через `COUNT(*)` дала тот же результат `1 → 1`; отказ от агрегата его не изменил.
[Upstream TestTransaction.testIsolationLevels](https://github.com/h2database/h2database/blob/master/h2/src/test/org/h2/test/db/TestTransaction.java)
также ожидает отсутствие новых строк при REPEATABLE_READ после чтения таблицы.
Этот источник на `master` может меняться; основное свидетельство здесь —
три журнала с зафиксированной версией jar и проверкой версии через JDBC metadata.

При REPEATABLE_READ впервые прочитанная позже другая таблица может иметь
более новый снимок. Это отдельная аномалия согласованности между таблицами;
она не подменяет phantom read от повторения одного запроса в этом опыте.

SERIALIZABLE здесь демонстрирует отсутствие аномалии чтения. Это не доказательство
полной сериализуемости конкурентных записей: сама документация H2 отмечает,
что SERIALIZABLE пока не гарантирует такую эквивалентность для пишущих транзакций.
Для полного выполнения требования о phantom при REPEATABLE_READ нужна БД
с подходящей реализацией уровня изоляции и отдельный настоящий опыт.
