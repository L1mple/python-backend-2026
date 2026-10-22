# Домашнее задание 3: Docker, Prometheus и Grafana

## Как устроено решение

В Docker запускаются три контейнера: `shop` (API интернет-магазина из ДЗ2), `prometheus` (сбор метрик), `grafana` (графики). 

- `monitored_app.py` подключает Prometheus Instrumentator к объекту `app` из `shop_api/main.py` и открывает `/metrics`.
- `Dockerfile` собирает образ API.
- `docker-compose.yml` запускает три сервиса вместе.
- `prometheus.yml` задаёт опрос `shop:8000/metrics` каждые 10 секунд.
- `grafana/provisioning` автоматически подключает Prometheus и импортирует 2 дашборда.

## Запуск на Windows 

Установить и запустить Docker Desktop. Из корня репозитория `python-backend-2026`:

```powershell
docker compose -f hw3/docker-compose.yml up --build -d
docker compose -f hw3/docker-compose.yml ps
```

Проверить:

- API и Swagger: http://localhost:8000/docs
- Экспорт метрик: http://localhost:8000/metrics
- Prometheus Targets: http://localhost:9090/targets — `shop` должен быть `UP`.
- Grafana: http://localhost:3000 (логин и пароль `admin` / `admin` для локальной учебной среды).

В Grafana открыть **Dashboards → HW3** (Пароль admin, пользователь admin). Должны появиться два готовых дашборда: `HW3 — Shop API — Requests` и `HW3 — Shop API — Latency`. 

## Заполнение графиков

В отдельном PowerShell **из корня репозитория** запустить:

```powershell
python hw3/generate_traffic.py
```

Подождать 20–30 секунд для нескольких циклов сбора метрик. 

## Графики Grafana

### 1. Shop API — Requests

<img width="1280" height="433" alt="image" src="https://github.com/user-attachments/assets/a0e6d22e-c79f-4100-862a-22f7b461d1af" />

Дашборд отображает статистику HTTP-запросов к сервису интернет-магазина.

| Метрика | Описание |
|---|---|
| Requests / second by endpoint | Количество запросов в секунду к эндпоинтам `/cart`, `/item`, `/item/{id}` |
| Requests / second by status | Количество запросов в секунду по группам HTTP-статусов (2xx, 4xx) |
| Service up (1 = yes) | Доступность сервиса для Prometheus: 1 — доступен, 0 — недоступен |
| Total HTTP requests | Общее количество HTTP-запросов, зарегистрированных метриками |


### 2. Shop API — Latency

<img width="1280" height="353" alt="image" src="https://github.com/user-attachments/assets/49132a64-bc9f-4f0d-b435-4974a0df69b4" />

Дашборд предназначен для мониторинга производительности API и анализа времени обработки HTTP-запросов.

| Метрика | Описание |
|---|---|
| p95 response time by endpoint | 95-й перцентиль времени ответа для каждого эндпоинта |
| Average response time by endpoint | Среднее время обработки запросов по каждому эндпоинту |
| Overall p95 response time | Общий 95-й перцентиль времени ответа сервиса |
| 4xx requests / second | Количество запросов с клиентскими ошибками (4xx) в секунду |



