# ДЗ 5: 95% покрытие тестами + CI

## 1. Покрытие тестами

`test_homework2.py` (39 тестов из задания) почти не затрагивал 404-ветки
"объект вообще не существует" (в отличие от "объект удалён") и совсем не
трогал WebSocket-чат. Чтобы дотянуть покрытие `shop_api` до 95%, не меняя
оригинальный файл задания, рядом добавлен
[hw2/hw/test_coverage_extra.py](../hw2/hw/test_coverage_extra.py):

- `GET/PUT/PATCH/DELETE /item/{id}` и `POST /cart/{cart_id}/add/{item_id}`
  с заведомо несуществующим id - 404-ветки, которых не было в исходных
  тестах.
- `GET /cart/{id}` с несуществующим id - аналогично для корзины.
- WebSocket-чат (`/chat/{chat_name}`): рассылка сообщения остальным
  участникам комнаты (но не себе), изоляция разных комнат друг от друга,
  и очистка комнаты после того, как все из неё вышли.

Порог покрытия и сама проверка настроены в
[hw2/hw/pytest.ini](../hw2/hw/pytest.ini) (`--cov=shop_api
--cov-fail-under=95`) - обычный `pytest` в `hw2/hw` теперь всегда печатает
отчёт о покрытии и падает, если оно ниже 95%.

Прогнать локально (нужен поднятый MySQL, см. [hw4/README.md](../hw4/README.md)):

```powershell
cd hw2\hw
$env:DATABASE_URL = "mysql+pymysql://shop:shop@localhost:3307/shop_api"
python -m pytest
```

## 2. CI

[.github/workflows/hw2-tests.yml](../.github/workflows/hw2-tests.yml)
обновлён: добавлен сервис-контейнер `mysql` (т.к. с hw4 `shop_api` ходит
в БД), и команда прогона тестов теперь просто `pytest` - она же проверяет
и 95%-порог покрытия через `pytest.ini`. Workflow запускается
автоматически на каждый push/PR, затрагивающий `hw2/hw/**`.
