import json
import math
import re
from http import HTTPStatus
from statistics import mean
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

import uvicorn


class RequestError(ValueError):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status


def parse_index(value: str) -> int:
    if re.fullmatch(r"[+-]?[0-9]+", value.strip()) is None:
        raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, "n must be an integer")
    try:
        index = int(value)
    except ValueError as error:
        raise RequestError(HTTPStatus.BAD_REQUEST, "n is too large") from error
    if index < 0:
        raise RequestError(HTTPStatus.BAD_REQUEST, "n must be non-negative")
    return index


def query_parameter(scope: dict[str, Any], name: str) -> str:
    try:
        query = parse_qs(
            scope.get("query_string", b"").decode("utf-8"),
            keep_blank_values=True,
            errors="strict",
        )
    except UnicodeError as error:
        raise RequestError(
            HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid query encoding"
        ) from error
    values = query.get(name, [])
    if len(values) != 1:
        raise RequestError(
            HTTPStatus.UNPROCESSABLE_ENTITY, f"Expected one {name} parameter"
        )
    return values[0]


def fibonacci(index: int) -> int:
    current, following = 0, 1
    for _ in range(index):
        current, following = following, current + following
    return current


async def read_body(receive: Callable[[], Awaitable[dict[str, Any]]]) -> bytes:
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            raise ConnectionError("Client disconnected")
        body.extend(message.get("body", b""))
        if not message.get("more_body", False):
            return bytes(body)


def calculate_mean(body: bytes) -> float:
    try:
        numbers = json.loads(body)
    except (ValueError, UnicodeError) as error:
        raise RequestError(
            HTTPStatus.UNPROCESSABLE_ENTITY, "Expected an array of numbers"
        ) from error
    if not isinstance(numbers, list) or any(
        type(number) not in (int, float) for number in numbers
    ):
        raise RequestError(
            HTTPStatus.UNPROCESSABLE_ENTITY, "Expected an array of numbers"
        )
    if not numbers:
        raise RequestError(HTTPStatus.BAD_REQUEST, "The array must not be empty")
    if any(
        isinstance(number, float) and not math.isfinite(number) for number in numbers
    ):
        raise RequestError(HTTPStatus.BAD_REQUEST, "Numbers must be finite")
    try:
        return float(mean(numbers))
    except OverflowError as error:
        raise RequestError(HTTPStatus.BAD_REQUEST, "The mean is too large") from error


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if scope["type"] != "http":
        raise ValueError("Only HTTP and lifespan scopes are supported")

    path = scope["path"]
    is_fibonacci = path.startswith("/fibonacci/") and path.count("/") == 2
    try:
        if path not in ("/factorial", "/mean") and not is_fibonacci:
            raise RequestError(HTTPStatus.NOT_FOUND, "Endpoint not found")
        if scope["method"] != "GET":
            raise RequestError(
                HTTPStatus.UNPROCESSABLE_ENTITY, "Expected a GET request"
            )

        if path == "/factorial":
            result = math.factorial(parse_index(query_parameter(scope, "n")))
        elif is_fibonacci:
            result = fibonacci(parse_index(path.removeprefix("/fibonacci/")))
        else:
            result = calculate_mean(await read_body(receive))

        try:
            body = json.dumps({"result": result}, allow_nan=False).encode("utf-8")
        except (ValueError, OverflowError) as error:
            raise RequestError(
                HTTPStatus.BAD_REQUEST, "The result is too large"
            ) from error
        status = HTTPStatus.OK
    except ConnectionError:
        return
    except RequestError as error:
        status = error.status
        body = json.dumps({"error": str(error)}).encode("utf-8")

    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b"" if scope["method"] == "HEAD" else body,
        }
    )


if __name__ == "__main__":
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
