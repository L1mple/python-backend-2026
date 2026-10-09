import json
import math
import re
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


async def _send_json(send: Send, status: HTTPStatus, data: Any) -> None:
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    await send(
        {
            "type": "http.response.start",
            "status": int(status),
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _read_body(receive: Receive) -> bytes:
    """Считывает все части тела запроса, переданные ASGI-сервером."""
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        if message["type"] != "http.request":
            continue
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _validation_error(location: list[Any], message: str, error_type: str) -> dict[str, Any]:
    return {"detail": [{"loc": location, "msg": message, "type": error_type}]}


def _parse_integer(value: str) -> int:
    value = value.strip()
    if not re.fullmatch(r"[+-]?\d+(?:\.0+)?", value):
        raise ValueError("not an integer")
    return int(value.split(".", 1)[0])


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    """
    Args:
        scope: Словарь с информацией о запросе
        receive: Корутина для получения сообщений от клиента
        send: Корутина для отправки сообщений клиенту
    """

    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if scope["type"] != "http":
        return

    method = scope.get("method", "")
    path = scope.get("path", "")

    if method != "GET":
        await _send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Не найдено"})
        return

    # Первый запрос
    if path == "/factorial":
        query = parse_qs(
            scope.get("query_string", b"").decode("utf-8", errors="replace"),
            keep_blank_values=True,
        )
        values = query.get("n")
        if not values:
            error = _validation_error(["query", "n"], "Обязательное поле", "missing")
            await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, error)
            return
        try:
            n = _parse_integer(values[-1])
        except (TypeError, ValueError):
            error = _validation_error(
                ["query", "n"], "Введенное значение должно быть целым числом", "int_parsing"
            )
            await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, error)
            return
        if n < 0:
            await _send_json(
                send,
                HTTPStatus.BAD_REQUEST,
                {"detail": "Неверное значение n, оно не может быть отрицательным"},
            )
            return
        await _send_json(send, HTTPStatus.OK, {"result": math.factorial(n)})
        return

    # Второй запрос
    fibonacci_match = re.fullmatch(r"/fibonacci/([^/]+)", path)
    if fibonacci_match:
        raw_n = fibonacci_match.group(1)
        try:
            n = _parse_integer(raw_n)
        except ValueError:
            error = _validation_error(
                ["path", "n"], "Введенное значение должно быть целым числом", "int_parsing"
            )
            await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, error)
            return
        if n < 0:
            await _send_json(
                send,
                HTTPStatus.BAD_REQUEST,
                {"detail": "Неверное значение n, оно не может быть отрицательным"},
            )
            return
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        await _send_json(send, HTTPStatus.OK, {"result": b})
        return

    # Третий запрос
    if path == "/mean":
        body = await _read_body(receive)
        if body:
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                error = _validation_error(["body"], "Неверный формат JSON", "json_invalid")
                await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, error)
                return
        else:
            query = parse_qs(
                scope.get("query_string", b"").decode("utf-8", errors="replace"),
                keep_blank_values=True,
            )
            values = query.get("numbers")
            if not values:
                error = _validation_error(["body"], "Неверный формат JSON", "json_invalid")
                await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, error)
                return
            data = values[-1].split(",")

        if not isinstance(data, list):
            error = _validation_error(
                ["body"], "Входные данные должны представлять собой корректный список чисел", "list_type"
            )
            await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, error)
            return
        if not data:
            await _send_json(
                send,
                HTTPStatus.BAD_REQUEST,
                {"detail": "Недопустимое значение для body: должен быть непустой массив чисел с плавающей запятой"},
            )
            return
        try:

            numbers = [float(value) for value in data]
        except (TypeError, ValueError, OverflowError):
            error = _validation_error(
                ["body"], "Входные данные должны представлять собой корректный список чисел", "float_type"
            )
            await _send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, error)
            return
        await _send_json(send, HTTPStatus.OK, {"result": sum(numbers) / len(numbers)})
        return

    await _send_json(send, HTTPStatus.NOT_FOUND, {"detail": "Не найден"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
