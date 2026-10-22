import json
import math
import re
from http import HTTPStatus
from statistics import mean
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


class HTTPError(Exception):
    def __init__(self, status: HTTPStatus, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def get_fibonacci(n: int) -> dict[str, int]:
    if n < 0:
        raise HTTPError(HTTPStatus.BAD_REQUEST, "n must be non-negative")

    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b

    return {"result": b}


def get_factorial(n: int) -> dict[str, int]:
    if n < 0:
        raise HTTPError(HTTPStatus.BAD_REQUEST, "n must be non-negative")

    return {"result": math.factorial(n)}


def get_mean(data: list[int | float]) -> dict[str, int | float]:
    if not isinstance(data, list) or any(
        type(value) not in (int, float)
        or (isinstance(value, float) and not math.isfinite(value))
        for value in data
    ):
        raise HTTPError(
            HTTPStatus.UNPROCESSABLE_ENTITY, "Expected an array of finite numbers"
        )
    if not data:
        raise HTTPError(HTTPStatus.BAD_REQUEST, "The array must not be empty")
    try:
        result = mean(data)
    except OverflowError:
        raise HTTPError(HTTPStatus.BAD_REQUEST, "The mean is too large") from None

    return {"result": result}


def _parse_integer(value: str) -> int:
    try:
        if re.fullmatch(r"[+-]?[0-9]+", value) is None:
            raise ValueError
        return int(value)
    except ValueError:
        raise HTTPError(
            HTTPStatus.UNPROCESSABLE_ENTITY, "Expected an integer n"
        ) from None


async def _read_json(receive: Receive) -> Any:
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            raise ConnectionError("Client disconnected")
        body.extend(message.get("body", b""))
        if not message.get("more_body", False):
            break

    try:
        return json.loads(body)
    except (ValueError, RecursionError):
        raise HTTPError(
            HTTPStatus.UNPROCESSABLE_ENTITY, "Expected valid JSON"
        ) from None


async def _send_json(
    send: Send, status: HTTPStatus, data: dict[str, Any]
) -> None:
    try:
        body = json.dumps(data, allow_nan=False).encode("utf-8")
    except ValueError:
        status = HTTPStatus.BAD_REQUEST
        body = json.dumps({"detail": "Result is too large to encode as JSON"}).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if status == HTTPStatus.METHOD_NOT_ALLOWED:
        headers.append((b"allow", b"GET"))

    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


async def _handle_lifespan(receive: Receive, send: Send) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


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
        await _handle_lifespan(receive, send)
        return
    if scope["type"] != "http":
        return

    path = scope["path"]
    parts = path.split("/")
    is_fibonacci = len(parts) == 3 and parts[1] == "fibonacci" and bool(parts[2])

    try:
        if path not in ("/factorial", "/mean") and not is_fibonacci:
            raise HTTPError(HTTPStatus.NOT_FOUND, "Not found")
        if scope["method"] != "GET":
            raise HTTPError(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed")

        if is_fibonacci:
            result = get_fibonacci(_parse_integer(parts[2]))
        elif path == "/factorial":
            query = parse_qs(
                scope.get("query_string", b"").decode("ascii"), keep_blank_values=True
            )
            values = query.get("n", [])
            if len(values) != 1:
                raise HTTPError(
                    HTTPStatus.UNPROCESSABLE_ENTITY, "Expected one parameter n"
                )
            result = get_factorial(_parse_integer(values[0]))
        else:
            result = get_mean(await _read_json(receive))
    except HTTPError as error:
        status, result = error.status, {"detail": error.detail}
    except UnicodeDecodeError:
        status = HTTPStatus.UNPROCESSABLE_ENTITY
        result = {"detail": "Invalid query encoding"}
    except ConnectionError:
        return
    else:
        status = HTTPStatus.OK

    await _send_json(send, status, result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
