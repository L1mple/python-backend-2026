CI в `.github/workflows/hw5-tests.yml`: Postgres как service container, затем `pytest`.

## Локальный запуск

```bash
cd hw5
pip install -r requirements.txt
pytest
```

Чтобы запустить в Postgres:

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg2://shop:shop@localhost:7432/shop
pytest
```
