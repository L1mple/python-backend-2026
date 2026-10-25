# Transaction isolation

Set `MSSQL_SA_PASSWORD`, then start the stack from the repository root:

```bash
docker compose -f hw3/docker-compose.yml up -d --build
docker compose -f hw3/docker-compose.yml exec shop-api python hw4/transactions.py
```

The script prints:

```json
{
  "dirty_read_read_uncommitted": 20,
  "dirty_read_read_committed": 10,
  "non_repeatable_read_committed": [10, 20],
  "non_repeatable_repeatable_read": [10, 10],
  "phantom_repeatable_read": [1, 2],
  "phantom_serializable": [1, 1]
}
```
