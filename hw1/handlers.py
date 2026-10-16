from http import HTTPStatus
import json
from typing import Any, TypedDict

from logic import fibonacci, factorial, mean


class Response(TypedDict):
    status: HTTPStatus
    headers: list[list[bytes]]
    body: bytes


def build_error_response(status: HTTPStatus, message: str) -> Response:
    """
    Строит словарь с информацией об ошибке.

    Args:
        status: HTTP статус код ошибки
        message: Сообщение об ошибке

    Returns:
        Словарь с информацией об ошибке
    """
    return {
        "status": status,
        "headers": [[b"content-type", b"text/plain"]],
        "body": message.encode(),
    }


def build_success_response(value: Any) -> Response:
    """
    Строит словарь с информацией об успешном ответе.

    Args:
        value: Значение, которое будет возвращено в теле ответа

    Returns:
        Словарь с информацией об успешном ответе
    """
    return {
        "status": HTTPStatus.OK,
        "headers": [[b"content-type", b"text/plain"]],
        "body": json.dumps({"result": value}).encode(),
    }


def validate_request(scope: dict[str, Any]) -> Response | None:
    """
    Проверяет тип и метод запроса.

    Args:
        scope: Словарь с информацией о запросе

    Raises:
        NotImplementedError: Если тип запроса не поддерживается
        ValueError: Если метод запроса не поддерживается
    """
    if scope["type"] != "http":
        raise NotImplementedError(f"Unsupported scope type: {scope['type']}")
    if scope["method"] != "GET":
        return build_error_response(
            HTTPStatus.NOT_FOUND,
            f"Endpoint not found for method: {scope['method']}",
        )
    return None


def handle_request(scope: dict[str, Any]) -> Response:
    """
    Обрабатывает запрос и возвращает словарь с результатами обработки.

    Args:
        scope: Словарь с информацией о запросе

    Returns:
        Словарь с результатами обработки запроса
    """

    error = validate_request(scope)
    if error:
        return error

    match scope["path"]:
        case str(path) if path.startswith("/fibonacci/"):
            return handle_fibonacci(scope)
        case "/factorial":
            return handle_factorial(scope)
        case "/mean":
            return handle_mean(scope)
        case _:
            return build_error_response(HTTPStatus.NOT_FOUND, "Path not found")


def handle_fibonacci(scope: dict[str, Any]) -> Response:
    """
    Обрабатывает запрос на вычисление n-го числа Фибоначчи.

    Args:
        scope: Словарь с информацией о запросе
    """
    path = scope["path"]
    try:
        number = int(path.removeprefix("/fibonacci/"))
    except ValueError:
        return build_error_response(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"Invalid number in path: {path.removeprefix('/fibonacci/')}",
        )

    if number < 0:
        return build_error_response(
            HTTPStatus.BAD_REQUEST, "'n' must be a non-negative integer"
        )

    return build_success_response(fibonacci(number))


def parse_query_string(query_string: str) -> dict[str, str]:
    """
    Разбирает строку запроса и возвращает словарь с параметрами.

    Args:
        query_string: Строка запроса

    Returns:
        Словарь с параметрами запроса
    """
    params = {}
    for param in query_string.split("&"):
        if "=" in param:
            key, value = param.split("=", 1)
            params[key] = value
    return params


def handle_factorial(scope: dict[str, Any]) -> Response:
    """
    Обрабатывает запрос на вычисление факториала числа n.

    Args:
        scope: Словарь с информацией о запросе
    """
    query = scope.get("query_string", b"").decode()
    params = parse_query_string(query)

    if "n" not in params:
        return build_error_response(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Missing 'n' parameter in query string",
        )

    try:
        number = int(params["n"])
    except ValueError:
        return build_error_response(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"Invalid 'n' parameter: {params['n']}",
        )

    if number < 0:
        return build_error_response(
            HTTPStatus.BAD_REQUEST, "'n' must be a non-negative integer"
        )

    return build_success_response(factorial(number))


def handle_mean(scope: dict[str, Any]) -> Response:
    """
    Обрабатывает запрос на вычисление среднего арифметического списка чисел.

    Args:
        scope: Словарь с информацией о запросе
    """
    query = scope.get("query_string", b"").decode()
    params = parse_query_string(query)

    if "numbers" not in params or not params["numbers"]:
        return build_error_response(
            HTTPStatus.BAD_REQUEST,
            "Missing 'numbers' parameter in query string",
        )
    try:
        numbers = [float(x) for x in params["numbers"].split(",")]
    except ValueError:
        return build_error_response(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"Invalid 'numbers' parameter: {params['numbers']}",
        )

    return build_success_response(mean(numbers))
