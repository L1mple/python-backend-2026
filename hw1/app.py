from typing import Any, Awaitable, Callable
import json
import math
import sys
from urllib.parse import parse_qs

sys.set_int_max_str_digits(0)


async def send_json(send, status: int, payload: dict[str, Any]) -> None:
    """Отправляет клиенту JSON-ответ с заданным HTTP-статусом (UTF-8, без экранирования кириллицы)."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def handle_lifespan(receive, send) -> None:
    """Обрабатывает события жизненного цикла сервера: подтверждает startup и shutdown."""
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def read_body(receive) -> bytes:
    """Читает тело запроса целиком, собирая его из всех входящих чанков."""
    body = b""
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    return body


def factorial(n: int) -> int:
    """Возвращает факториал неотрицательного целого числа n."""
    return math.factorial(n)


def fibonacci(n: int) -> int:
    """Возвращает n-е число Фибоначчи итеративным способом."""
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


async def handle_factorial(scope, send) -> None:
    """Обработчик GET /factorial?n=...: 422 при отсутствии или нечисловом n, 400 при n < 0, иначе 200."""
    query = parse_qs(scope["query_string"].decode(), keep_blank_values=True)
    values = query.get("n")
    if not values:
        await send_json(send, 422, {"error": "Параметр n обязателен"})
        return
    try:
        n = int(values[0])
    except ValueError:
        await send_json(send, 422, {"error": "n должно быть целым числом"})
        return
    if n < 0:
        await send_json(send, 400, {"error": "n должно быть неотрицательным"})
        return
    await send_json(send, 200, {"result": factorial(n)})


async def handle_fibonacci(raw: str, send) -> None:
    """Обработчик GET /fibonacci/{n}: 422 при нечисловом n, 400 при n < 0, иначе 200."""
    try:
        n = int(raw)
    except ValueError:
        await send_json(send, 422, {"error": "n должно быть целым числом"})
        return
    if n < 0:
        await send_json(send, 400, {"error": "n должно быть неотрицательным"})
        return
    await send_json(send, 200, {"result": fibonacci(n)})


async def handle_mean(receive, send) -> None:
    """Обработчик GET /mean: 422 при пустом теле, невалидном JSON или нечисловых элементах, 400 при пустом списке, иначе 200."""
    body = await read_body(receive)
    if not body.strip():
        await send_json(send, 422, {"error": "Тело запроса обязательно"})
        return
    try:
        data = json.loads(body)
    except ValueError:
        await send_json(send, 422, {"error": "Некорректный JSON"})
        return
    if not isinstance(data, list):
        await send_json(send, 422, {"error": "Тело запроса должно быть списком"})
        return
    for item in data:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            await send_json(
                send, 422, {"error": "Список должен содержать только числа"}
            )
            return
        if isinstance(item, float) and not math.isfinite(item):
            await send_json(
                send, 422, {"error": "Список должен содержать только конечные числа"}
            )
            return
    if not data:
        await send_json(send, 400, {"error": "Список не должен быть пустым"})
        return
    await send_json(send, 200, {"result": sum(data) / len(data)})


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    if scope["type"] == "lifespan":
        await handle_lifespan(receive, send)
        return
    if scope["type"] != "http":
        return

    method = scope["method"]
    parts = scope["path"].split("/")

    if method == "GET" and len(parts) == 2 and parts[1] == "factorial":
        await handle_factorial(scope, send)
    elif method == "GET" and len(parts) == 3 and parts[1] == "fibonacci":
        await handle_fibonacci(parts[2], send)
    elif method == "GET" and len(parts) == 2 and parts[1] == "mean":
        await handle_mean(receive, send)
    else:
        await send_json(send, 404, {"error": "Не найдено"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
