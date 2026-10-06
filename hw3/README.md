# Домашнее задание №3

Shop API из второй домашней работы запускается вместе с Prometheus и Grafana.
Метрики FastAPI и магазина доступны в `/metrics`, Prometheus собирает их каждые
5 секунд, а Grafana автоматически подключает источник данных и два готовых
дашборда.

## Запуск

```bash
cd hw3
docker compose up --build -d
```

После запуска доступны:

- Shop API и Swagger: <http://localhost:8000/docs>
- метрики приложения: <http://localhost:8000/metrics>
- Prometheus: <http://localhost:9090>
- Grafana, HTTP-метрики: <http://localhost:3000/d/shop-api/shop-api-monitoring>
- Grafana, метрики магазина: <http://localhost:3000/d/shop-business/shop-business-metrics>

Для наполнения графиков данными:

```bash
python load_test.py --seconds 60
```

Остановка сервисов:

```bash
docker compose down
```

## Результат

### HTTP-метрики

![HTTP-метрики Shop API в Grafana](docs/grafana-dashboard.png)

### Метрики магазина

![Метрики магазина в Grafana](docs/grafana-business-dashboard.png)
