# ДЗ 3: Docker + Prometheus + Grafana

Контейнеризация сервиса из [hw2](../hw2/hw) (`shop_api`) и мониторинг через
Prometheus и Grafana, по аналогии с [lecture3](../lecture3).

## Запуск

```bash
cd hw3
docker compose up --build
```

Поднимутся три контейнера:

- `local` - сервис `shop_api` на http://localhost:8080 (метрики на `/metrics`)
- `prometheus` - http://localhost:9090
- `grafana` - http://localhost:3000 (логин/пароль по умолчанию `admin`/`admin`)

## Генерация трафика

Дашборды в Grafana пустые, пока через сервис не прошло ни одного запроса.
Перед тем как снимать скриншот, сгенерируйте немного трафика:

```bash
python traffic.py
```

## Настройка Grafana

1. Зайти на http://localhost:3000 (`admin`/`admin`)
2. Connections -> Data sources -> Add data source -> Prometheus
   URL: `http://prometheus:9090` -> Save & test
3. Создать дашборд с парой панелей, например:
   - Request rate: `rate(http_requests_total[1m])`
   - Request latency (p95): `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
4. Сделать скриншот и приложить к PR
