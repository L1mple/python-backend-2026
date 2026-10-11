import json
import math
import statistics
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs


class MathApplication:
    """ASGI API for factorial, Fibonacci numbers and arithmetic mean."""

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            while True:
                message = await receive()
                if message['type'] == 'lifespan.startup':
                    await send({'type': 'lifespan.startup.complete'})
                elif message['type'] == 'lifespan.shutdown':
                    await send({'type': 'lifespan.shutdown.complete'})
                    return
        if scope['type'] != 'http':
            return
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if not message.get('more_body', False):
                break
        try:
            status, payload = self.calculate(scope, body)
            encoded = json.dumps(payload, allow_nan=False).encode()
        except (ValueError, TypeError, OverflowError):
            status = 422
            encoded = b'{"error": "Invalid parameters"}'
        await send({
            'type': 'http.response.start',
            'status': status,
            'headers': [(b'content-type', b'application/json')],
        })
        await send({'type': 'http.response.body', 'body': encoded})

    def calculate(self, scope, body):
        path = scope['path']
        if path not in ('/factorial', '/mean', '/fibonacci') and not path.startswith('/fibonacci/'):
            return 404, {'error': 'Not found'}
        if scope['method'] != 'GET':
            return 422, {'error': 'Unsupported method'}
        query = parse_qs(scope.get('query_string', b'').decode(), keep_blank_values=True)
        if path == '/mean':
            if body:
                numbers = json.loads(body)
            else:
                values = query.get('numbers', [])
                if len(values) != 1:
                    raise ValueError
                numbers = [float(value) for value in values[0].split(',')]
            if not isinstance(numbers, list) or any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in numbers
            ):
                raise ValueError
            if not numbers:
                return 400, {'error': 'Numbers must not be empty'}
            return 200, {'result': statistics.mean(numbers)}
        if path == '/factorial':
            values = query.get('n', [])
            if len(values) != 1:
                raise ValueError
            n = int(values[0])
        else:
            n = int(path.removeprefix('/fibonacci/'))
        if n < 0:
            return 400, {'error': 'Number must be nonnegative'}
        if path == '/factorial':
            result = math.factorial(n)
        else:
            result, following = 0, 1
            for _ in range(n):
                result, following = following, result + following
        return 200, {'result': result}


_app = MathApplication()


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    await _app(scope, receive, send)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run('app:application', host='0.0.0.0', port=8000, reload=True)
