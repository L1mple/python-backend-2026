# HW3 — Docker + Prometheus + Grafana для Shop API

Сервис из ДЗ-2 (`shop_api/`) упакован в Docker и покрыт мониторингом.

## Состав
- `Dockerfile` — образ сервиса (python:3.12-slim, uvicorn на 8080)
- `docker-compose.yml` — сервис `shop-api` + `prometheus` + `grafana` в одной сети
- `prometheus/prometheus.yml` — Prometheus опрашивает `shop-api:8080/metrics` раз в 10 с
- `grafana/` — provisioning: data source Prometheus и дашборд «Shop API» (RPS по ручкам, % ошибок, p95 латентность, память процесса) подхватываются при старте
- `shop_api/main.py` — добавлен `Instrumentator().instrument(app).expose(app)` → ручка `/metrics`
- `load.py` — скрипт нагрузки (товары, корзины, часть запросов с 404), чтобы на графиках было что смотреть

## Запуск
```bash
cd hw3
docker compose up --build
```
- Shop API: http://localhost:8080/docs, метрики: http://localhost:8080/metrics
- Prometheus: http://localhost:9090 (Status → Targets: `shop-api` должен быть UP)
- Grafana: http://localhost:3000 (admin / admin) → дашборд «Shop API» уже на месте: http://localhost:3000/d/shop-api

Нагрузка: `pip install requests && python load.py`

Скрины дашбордов — в комментарии к PR.
