## 1. Собрать и запустить

Из корня репозитория:

```powershell
docker compose -f hw3/docker-compose.yml up --build -d
```

## 2. Проверка приложения

| Адрес | Что должно быть |
| --- | --- |
| http://localhost:8080/docs | Swagger |
| http://localhost:8080/metrics | Метрики |
| http://localhost:9090/targets | Target |
| http://localhost:3000 | Grafana |

## 3. Трафик

Скачать зависимости и запустить трафик

```powershell
python -m pip install -r hw3/requirements.txt
python hw3/load.py --duration 180 --workers 4
```

## 4. Остановить контейнеры

```powershell
docker compose -f hw3/docker-compose.yml down
```