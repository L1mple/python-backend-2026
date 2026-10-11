# Репозиторий для домашних заданий по курсу "Python Backend"

В этом репозитории будут размещены домашние задания по курсу "Python Backend".

## 🚀 Как начать работу

### 1. Форкните репозиторий
1. Перейдите на страницу репозитория GitHub
2. Нажмите кнопку "Fork" в правом верхнем углу
3. Выберите свой аккаунт GitHub для создания форка

### 2. Склонируйте свой форк
```bash
git clone https://github.com/ВАШ_USERNAME/python-backend-2026.git
cd python-backend-2026
```

### 3. Полезные ссылки курса

- [Репозиторий с примерами](https://github.com/L1mple/python-backend-2026) -
  вы уже тут
- [Лекции в
  pdf](https://drive.google.com/drive/folders/1A8rFJ7kNq9CwpWkELyjNvny550dUOMw_?usp=drive_link)
  (так же будут постепенно подгружаться)
- [Оценки и домашки](https://docs.google.com/spreadsheets/d/1PNxseoY3KyzFNavTBwNDoOSuVKc79Zt6U4LUr2zB53Y/edit?usp=sharing)
## ДЗ3: Docker и мониторинг магазина

Из корня репозитория (Docker Compose v2 и [uv](https://docs.astral.sh/uv/) установлены):

```bash
docker compose -p python-backend-hw3 up -d --build --wait
uv run --no-project --python 3.13 --with httpx scripts/load_shop.py --duration 120 --interval 0.1
```

Сервисы опубликованы только на localhost:

- Магазин: <http://127.0.0.1:8000/docs>, метрики: <http://127.0.0.1:8000/metrics>.
- Prometheus: <http://127.0.0.1:9090/targets>; цель `shop:8000` должна быть UP.
- Grafana: <http://127.0.0.1:3000>; логин `admin`, локальный пароль `local-homework`.
  До первого запуска можно задать `GRAFANA_ADMIN_PASSWORD`. Уже созданный volume сохраняет пароль.

В Grafana автоматически создаются [Shop API](http://127.0.0.1:3000/d/shop-api)
(доступность, RPS, классы HTTP-статусов, p95 времени ответа) и
[Shop process](http://127.0.0.1:3000/d/shop-process) (CPU, RAM, количество запросов).
Prometheus опрашивает сервис каждые 5 секунд; для графиков `rate` нужны минимум два опроса.
CPU и RAM экспортирует стандартный Linux process collector внутри контейнера.
`/metrics` исключён из счётчика HTTP-запросов, идентификаторы в путях нормализованы.

Нагрузчик создаёт один товар и одну корзину, затем читает каталог и корзину,
добавляет товар, меняет цену и проверяет ожидаемый 404. Максимум — 3600 секунд,
минимальный интервал — 0.01 секунды; сетевой timeout — 5 секунд.
Один цикл содержит шесть запросов. Таймер проверяется между циклами, поэтому
последний цикл может закончиться после указанного срока. Это демонстрация метрик,
а не бенчмарк производительности. Магазин хранит данные в PostgreSQL:
перезапуски приложения и БД сохраняют товары и корзины.

Проверки на обеих версиях Python:

```bash
PYTHONPATH=hw2/hw uv run --no-project --python 3.13 --with-requirements hw2/hw/requirements.txt pytest -q hw2/hw
PYTHONPATH=hw2/hw uv run --no-project --python 3.14 --with-requirements hw2/hw/requirements.txt pytest -q hw2/hw
```

Скриншоты реальных панелей под нагрузкой:

![Shop API](docs/screenshots/shop-api.png)
![Shop process](docs/screenshots/shop-process.png)
![Prometheus targets](docs/screenshots/prometheus-targets.png)

Остановка с сохранением данных Prometheus и Grafana:

```bash
docker compose -p python-backend-hw3 down
```

## ДЗ4: PostgreSQL и транзакции

Тот же Compose-проект запускает PostgreSQL 17 с healthcheck и volume
`postgres-data`. Команда запуска выше обновляет магазин и сохраняет volumes
Prometheus и Grafana. PostgreSQL доступен на `127.0.0.1:15432`, база и пользователь
`shop`, локальный пароль `local-homework`. Не используйте `down -v`, если нужны данные.

Хранилище использует SQLAlchemy 2 и отдельную транзакцию для каждой записи.
Таблицы товаров, корзин и позиций имеют внешние ключи, уникальную пару
`(cart_id, item_id)`, положительное количество и конечную неотрицательную цену.
Добавление товара выполняет атомарный `INSERT ... ON CONFLICT DO UPDATE`, поэтому
параллельные запросы не теряют увеличения количества. Ошибка после записи
откатывает транзакцию. Удаление остаётся мягким: позиции сохраняются, а удалённый
товар исключается из стоимости корзины. REST, WebSocket и метрики работают как раньше.

Для запуска магазина вне Compose используется `DATABASE_URL`; по умолчанию он
подключается к локальному PostgreSQL из этого Compose-проекта:

```bash
PYTHONPATH=hw2/hw uv run --no-project --python 3.13 --with-requirements hw2/hw/requirements.txt uvicorn shop_api.main:app
```

Обычные команды pytest выше автоматически используют временную SQLite,
если `DATABASE_URL` не задан. Явный URL сохраняется: тесты создают данные,
поэтому для PostgreSQL укажите отдельную тестовую БД, а не базу магазина.
Например, один раз создайте `shop_tests` и запускайте проверки на обеих версиях:

```bash
docker compose -p python-backend-hw3 exec -T postgres createdb -U shop shop_tests
DATABASE_URL=postgresql+psycopg://shop:local-homework@127.0.0.1:15432/shop_tests PYTHONPATH=hw2/hw uv run --no-project --python 3.13 --with-requirements hw2/hw/requirements.txt pytest -q hw2/hw
DATABASE_URL=postgresql+psycopg://shop:local-homework@127.0.0.1:15432/shop_tests PYTHONPATH=hw2/hw uv run --no-project --python 3.14 --with-requirements hw2/hw/requirements.txt pytest -q hw2/hw
```

Исходные HTTP-тесты работают и на PostgreSQL. Дополнительные проверки используют
собственные временные схемы: ограничения БД, rollback после upsert, повторное
подключение и 48 параллельных HTTP-добавлений. На SQLite последняя проверка
пропускается; workflow `HW4 PostgreSQL` запускает её на PostgreSQL 17.
