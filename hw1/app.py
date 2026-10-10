import json
import math
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


class RequestError(Exception):
    def __init__(
        self,
        status: HTTPStatus,
    ) -> None:
        super().__init__(status.phrase)
        self.status = status


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
        await _answer_lifespan_events(
            receive=receive,
            send=send,
        )
        return
    if scope["type"] != "http":
        return

    try:
        calculation_result = await _calculate_result_for_request(
            scope=scope,
            receive=receive,
        )
    except RequestError as request_error:
        await _send_json_response(
            send=send,
            status=request_error.status,
            response_body={"detail": request_error.status.phrase},
        )
        return

    await _send_json_response(
        send=send,
        status=HTTPStatus.OK,
        response_body={"result": calculation_result},
    )


async def _answer_lifespan_events(
    receive: Receive,
    send: Send,
) -> None:
    while True:
        lifespan_message = await receive()
        if lifespan_message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif lifespan_message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def _calculate_result_for_request(
    scope: Scope,
    receive: Receive,
) -> int | float:
    request_path = scope["path"]
    if scope["method"] != "GET":
        raise RequestError(status=HTTPStatus.NOT_FOUND)

    if request_path == "/factorial":
        raw_factorial_argument = _get_first_query_parameter_value(
            scope=scope,
            parameter_name="n",
        )
        factorial_argument = _parse_non_negative_integer(raw_value=raw_factorial_argument)
        return math.factorial(factorial_argument)

    if request_path.startswith("/fibonacci/"):
        raw_fibonacci_index = request_path.removeprefix("/fibonacci/")
        if "/" in raw_fibonacci_index:
            raise RequestError(status=HTTPStatus.NOT_FOUND)
        fibonacci_index = _parse_non_negative_integer(raw_value=raw_fibonacci_index)
        return _calculate_fibonacci_number(fibonacci_index=fibonacci_index)

    if request_path == "/mean":
        raw_request_body = await _read_whole_request_body(receive=receive)
        numbers_to_average = _parse_non_empty_list_of_numbers(raw_request_body=raw_request_body)
        return sum(numbers_to_average) / len(numbers_to_average)

    raise RequestError(status=HTTPStatus.NOT_FOUND)


def _get_first_query_parameter_value(
    scope: Scope,
    parameter_name: str,
) -> str | None:
    query_parameters = parse_qs(
        scope["query_string"].decode(),
        keep_blank_values=True,
    )
    values_of_parameter = query_parameters.get(parameter_name)
    return values_of_parameter[0] if values_of_parameter else None


def _parse_non_negative_integer(
    raw_value: str | None,
) -> int:
    if raw_value is None:
        raise RequestError(status=HTTPStatus.UNPROCESSABLE_ENTITY)
    try:
        parsed_integer = int(raw_value)
    except ValueError as parsing_error:
        raise RequestError(status=HTTPStatus.UNPROCESSABLE_ENTITY) from parsing_error
    if parsed_integer < 0:
        raise RequestError(status=HTTPStatus.BAD_REQUEST)
    return parsed_integer


def _calculate_fibonacci_number(
    fibonacci_index: int,
) -> int:
    previous_number, current_number = 0, 1
    for _ in range(fibonacci_index):
        previous_number, current_number = current_number, previous_number + current_number
    return previous_number


async def _read_whole_request_body(
    receive: Receive,
) -> bytes:
    collected_body = b""
    while True:
        request_message = await receive()
        if request_message["type"] != "http.request":
            return collected_body
        collected_body += request_message.get("body", b"")
        if not request_message.get("more_body", False):
            return collected_body


def _parse_non_empty_list_of_numbers(
    raw_request_body: bytes,
) -> list[int | float]:
    try:
        parsed_body = json.loads(raw_request_body)
    except ValueError as parsing_error:
        raise RequestError(status=HTTPStatus.UNPROCESSABLE_ENTITY) from parsing_error
    if not isinstance(parsed_body, list):
        raise RequestError(status=HTTPStatus.UNPROCESSABLE_ENTITY)
    if not parsed_body:
        raise RequestError(status=HTTPStatus.BAD_REQUEST)
    for list_element in parsed_body:
        element_is_number = isinstance(list_element, int | float) and not isinstance(list_element, bool)
        element_is_nan_or_infinity = isinstance(list_element, float) and not math.isfinite(list_element)
        if not element_is_number or element_is_nan_or_infinity:
            raise RequestError(status=HTTPStatus.UNPROCESSABLE_ENTITY)
    return parsed_body


async def _send_json_response(
    send: Send,
    status: HTTPStatus,
    response_body: dict[str, Any],
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status.value,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": json.dumps(response_body).encode(),
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:application",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
