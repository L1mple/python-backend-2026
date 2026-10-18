# HW3: Docker, Prometheus и Grafana

Мониторинг Shop API из `hw2/hw/shop_api` с помощью Prometheus и Grafana.
Задание: [lecture3/README.md](../lecture3/README.md).

## Запуск

Нужны запущенный Docker и Docker Compose. Из корня репозитория:

```sh
cd hw3
docker compose up --build -d
docker compose ps
```

| Сервис | Адрес |
| --- | --- |
| Swagger UI | http://localhost:8080/docs |
| Метрики API | http://localhost:8080/metrics |
| Prometheus targets | http://localhost:9090/targets |
| Grafana | http://localhost:3000 |

В Prometheus target `shop-api` должен иметь статус `UP`.
Начальные логин и пароль Grafana: `admin` / `admin`.

## Дашборды

Источник данных и дашборды создаются автоматически в папке Grafana `HW3`:

- **Shop API — Requests**: доступность API, частота запросов, HTTP-коды и доля ошибок.
- **Shop API — Latency**: среднее время ответа, p50/p95/p99 и задержки по маршрутам.

Для появления данных выполни запросы через Swagger UI (`Try it out` → `Execute`):
создай товар и корзину, добавь товар в корзину и запроси их содержимое.
Запрос несуществующего товара даст `404` для графика ошибок.
Повторяй запросы в течение минуты; Prometheus собирает метрики каждые 5 секунд.
Само открытие Swagger UI и чтение `/metrics` не учитываются как запросы к API.

В Grafana выбери период `Last 15 minutes` и обновление `5s`.
Скриншоты двух дашбордов сохрани в `screenshots/requests.png` и
`screenshots/latency.png` и приложи к PR.

## Остановка

Из папки `hw3`:

```sh
docker compose down
```

Данные Prometheus и Grafana сохраняются в томах Docker.
Товары и корзины хранятся в памяти и сбрасываются при перезапуске API.
