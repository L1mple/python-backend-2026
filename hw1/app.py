import json
from http import HTTPStatus
from math import isfinite
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


def _response(status: HTTPStatus, result: Any = None) -> tuple[int, bytes]:
    body = b"" if result is None else json.dumps({"result": result}).encode("utf-8")
    return int(status), body


async def _read_body(receive: Callable[[], Awaitable[dict[str, Any]]]) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _parse_non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError("invalid integer") from None
    if number < 0:
        raise OverflowError("negative integer")
    return number


def _fibonacci(n: int) -> int:
    previous, current = 0, 1
    for _ in range(n):
        previous, current = current, previous + current
    return previous


def _mean(values: list[Any]) -> float:
    if not values:
        raise OverflowError("empty list")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise ValueError("values must be numbers")
    if any(isinstance(value, float) and not isfinite(value) for value in values):
        raise ValueError("values must be finite")
    return sum(values) / len(values)


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
    if scope.get("type") != "http":
        status, body = _response(HTTPStatus.UNPROCESSABLE_ENTITY)
    else:
        path = scope.get("path", "")
        method = scope.get("method", "")
        status = int(HTTPStatus.NOT_FOUND)
        body = b""

        known_path = (
            path in ("/factorial", "/mean", "/fibonacci")
            or path.startswith("/fibonacci/")
        )

        try:
            if not known_path:
                status = int(HTTPStatus.NOT_FOUND)
            elif method != "GET":
                status = int(HTTPStatus.UNPROCESSABLE_ENTITY)
            elif path.startswith("/fibonacci/"):
                raw_n = path.removeprefix("/fibonacci/")
                n = _parse_non_negative_int(raw_n)
                status, body = _response(HTTPStatus.OK, _fibonacci(n))
            elif path == "/factorial":
                query = parse_qs(
                    scope.get("query_string", b"").decode("ascii", errors="strict"),
                    keep_blank_values=True,
                )
                values = query.get("n", [])
                if len(values) != 1:
                    raise ValueError("n must be provided once")
                n = _parse_non_negative_int(values[0])
                result = 1
                for factor in range(2, n + 1):
                    result *= factor
                status, body = _response(HTTPStatus.OK, result)
            elif path == "/mean":
                raw_body = await _read_body(receive)
                if raw_body:
                    values = json.loads(raw_body)
                else:
                    query = parse_qs(
                        scope.get("query_string", b"").decode("ascii", errors="strict"),
                        keep_blank_values=True,
                    )
                    raw_values = query.get("numbers", [])
                    if len(raw_values) != 1:
                        raise ValueError("numbers must be provided once")
                    values = [float(item) for item in raw_values[0].split(",") if item.strip()]
                if not isinstance(values, list):
                    raise ValueError("numbers must be a JSON array")
                status, body = _response(HTTPStatus.OK, _mean(values))
            elif path == "/fibonacci":
                status = int(HTTPStatus.UNPROCESSABLE_ENTITY)
        except OverflowError:
            status = int(HTTPStatus.BAD_REQUEST)
        except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
            status = int(HTTPStatus.UNPROCESSABLE_ENTITY)

        if status == int(HTTPStatus.BAD_REQUEST):
            body = b""
        elif status == int(HTTPStatus.UNPROCESSABLE_ENTITY):
            body = b""

    headers = [(b"content-type", b"application/json; charset=utf-8")]
    if body:
        headers.append((b"content-length", str(len(body)).encode("ascii")))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
