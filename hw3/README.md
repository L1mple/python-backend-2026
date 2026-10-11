# ДЗ 3: Docker + Prometheus + Grafana
## Запуск

```sh
docker compose up --build
```

- Сервис: http://localhost:8000/docs
- Метрики: http://localhost:8000/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin / admin)

## Что добавлено

- `Dockerfile` для сервиса
- `docker-compose.yml` (сервис + Prometheus + Grafana)
- Метрики через prometheus-fastapi-instrumentator и два кастомных счётчика
  (созданные товары и корзины)

