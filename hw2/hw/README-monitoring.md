# Docker + Prometheus + Grafana для Shop API

Конфигурация находится в `hw2/hw`, по аналогии с примером `lecture3`.

## Запуск

Откройте терминал в `hw2/hw` и выполните:

```bash
docker compose up --build -d
docker compose ps
```

- API и Swagger: http://localhost:8000/docs
- Метрики: http://localhost:8000/metrics
- Prometheus Targets: http://localhost:9090/targets (цель `shop-api` должна быть `UP`)
- Grafana: http://localhost:3000 (`admin` / `admin`, только для локальной разработки)
- Grafana → Dashboards → Shop API → Shop API HTTP Monitoring.

Сгенерируйте трафик из PowerShell:

```powershell
1..30 | ForEach-Object { Invoke-RestMethod http://localhost:8000/item }
```

Prometheus опрашивает приложение каждые 10 секунд, поэтому графики могут появиться с небольшой задержкой. Метрики HTTP доступны после обращения к API.

## Остановка

```bash
docker compose down
```

`docker compose down -v` дополнительно удалит накопленные метрики и данные Grafana.

## Тесты домашки

```bash
python -m pytest test_homework2.py -v
```

## Примечание

Shop API хранит данные в памяти процесса, поэтому товары/корзины сбрасываются при перезапуске контейнера. Это существующее поведение второй домашки, не требующее отдельной базы данных для данного задания.
