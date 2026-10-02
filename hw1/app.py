import math
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs
import json

def fibonacci(n: int) -> int:
    if n <= 0:
        return 0
    elif n == 1:
        return 1

    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

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

    async def send_status_code(code: int, headers: list[tuple[bytes, bytes]] | None = None):
        await send({
            'type': 'http.response.start',
            'status': code,
            'headers': headers if headers else [],
        })

    async def return_status_code(code: int, headers: list[tuple[bytes, bytes]] | None = None):
        await send_status_code(code, headers)
        await send({
            'type': 'http.response.body',
            'body': b'',
        })

    async def return_body(obj: dict[str, Any]):
        result = json.dumps(obj)
        await send_status_code(200, headers=[(b'content-type', b'application/json')])
        await send({
            'type': 'http.response.body',
            'body': result.encode()
        })

    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                return await send({'type': 'lifespan.shutdown.complete'})

    if scope['type'] != 'http':
        return

    if scope['method'] != 'GET':
        return await return_status_code(404)

    if scope['path'] == '/factorial': # n=5
        query = parse_qs(scope['query_string'].decode())
        if not (len(query) == 1 and len(query.get('n', [])) == 1):
            return await return_status_code(422)

        try:
            n = int(query['n'][0])
        except ValueError:
            return await return_status_code(422)
        if n < 0:
            return await return_status_code(400)

        return await return_body({'result': math.factorial(n)})

    if scope['path'].startswith('/fibonacci'): #/fibonacci/10
        path_split = scope['path'].split('/')
        try:
            number = int(path_split[2])
        except (IndexError, ValueError):
            return await return_status_code(422)

        if number < 0:
            return await return_status_code(400)

        return await return_body({'result': fibonacci(number)})

    if scope['path'] == '/mean':
        query = parse_qs(scope['query_string'].decode()) #/mean?numbers=1,2,3 a ничто
        if not (len(query) == 1 and len(query.get('numbers', [])) == 1):
            return await return_status_code(422)

        numbers_str = query['numbers'][0]
        values_from_numbers = numbers_str.split(',')
        try:
            numbers = [float(value) for value in values_from_numbers]
        except ValueError:
            return await return_status_code(400)
        if len(numbers) == 0:
            return await return_status_code(400)

        mean = sum(numbers) / len(numbers)
        return await return_body({'result': mean})

    return await return_status_code(404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host="0.0.0.0", port=8000, reload=True)
