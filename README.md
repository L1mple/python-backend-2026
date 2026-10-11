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
(доступность, RPS, HTTP-статусы, p50 и p90–p99, операции магазина,
значения/количество и недоступные позиции наблюдаемых корзин) и
[Shop process](http://127.0.0.1:3000/d/shop-process) (CPU, RAM, UP/все инстансы, датацентры,
запросы и задержки по инстансам). Фильтры `Datacenter` и `Instance` применяются
к обеим панелям. В локальном Compose один реальный target с меткой `datacenter=local`.
Prometheus опрашивает сервис каждые 5 секунд; для графиков `rate` нужны минимум два опроса.
CPU и RAM экспортирует стандартный Linux process collector внутри контейнера.
CPU — доля одного логического ядра, RAM — RSS процесса в байтах; это не загрузка хоста.
Квантили приблизительные, рассчитаны из histogram buckets, включая интервалы менее 1 мс.
Таймеры отдельных операций включают чтение/расчёт корзины, мутации, фильтрацию и записи;
ошибки тоже измеряются. Метки содержат только фиксированные стадии и исходы без ID.
Метрики корзин — распределения прочитанных ответов, а не выручка или снимок всех корзин.
Счётчики созданий/удалений показывают операции с момента запуска процесса.
`/metrics` исключён из счётчика HTTP-запросов, идентификаторы в путях нормализованы.

Нагрузчик создаёт один товар и одну корзину, затем читает каталог и корзину,
добавляет товар, меняет цену, удаляет и восстанавливает товар; проверяет
недоступные позиции и ожидаемые 404. Максимум — 3600 секунд,
минимальный интервал — 0.01 секунды; сетевой timeout — 5 секунд.
Один цикл содержит одиннадцать запросов. Таймер проверяется между циклами, поэтому
последний цикл может закончиться после указанного срока. Это демонстрация метрик,
а не бенчмарк производительности. Магазин хранит данные в памяти: перезапуск их удаляет.

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
