import json
import math
import re
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

# Создали корутину
async def application(
    # Scope (описание запроса) - обычный python-словарь, схема: dict[тип_ключей, тип_значений]
    # Any - значения могут иметь любой тип. Например, у "path" значение строковое, а у "query_string" - байты
    scope: dict[str, Any],
    # Receive - функция получения событий
    # Callable - объект, который можно вызвать как функцию (в данном случае вызвали без аргументов)
    # Awaitable - вызов возвращает объект, который поддерживает await (в данном случае после ожидания получим словарь)
    receive: Callable[[], Awaitable[dict[str, Any]]],
    # Send - функция отправки событий
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """
    -> None означает, что после завершения application
    возвращает None, а не полезный результат вызывающему коду.

    async-функция может возвращать число, строку, словарь и другие
    значения. Наличие async само по себе не требует возвращать None.

    Awaitable[None] у send описывает результат ожидания send(...),
    а -> None у application — результат самой application.

    application вызывает send(), но у каждой функции свой результат:
    возвращаемое значение send() не становится автоматически
    результатом application().

    По соглашению ASGI application передаёт HTTP-ответ через send(),
    а сама завершается с None.
    """
    # lifespan — это жизненный цикл приложения: его запуск и остановка
    if scope["type"] == "lifespan":

        while True:
            event = await receive()
            
            # lifespan.startup — «Подготовь приложение к работе». Подтверждаем готовность и продолжаем ждать события
            if event["type"] == "lifespan.startup":

                await send({
                    "type": "lifespan.startup.complete",
                })
            # lifespan.shutdown — «Заверши работу приложения». Подтверждаем завершение и выходим через return
            elif event["type"] == "lifespan.shutdown":
                await send({
                    "type": "lifespan.shutdown.complete",
                })
                return
    
    # Добавляю обработку случая, если в 'type' не лежит http --> сразу заканчиваем выполнение функции
    if scope["type"] != "http":
        # В данном случае return - выход из функции
        return
    
    # Начинаем факториал
    # Проверяем, к какой ручке обратился клиент: обрабатываем запрос, только если метод - GET, а путь - /factorial.
    if scope["method"] == "GET" and scope["path"] == "/factorial":
        print("Запрос на факториал")
        # Допустим, что клиент отправил запрос: /factorial?n=5
        # Берём query-строку из scope (scope — словарь, а "query_string" — ключ)
        # Например, по этому ключу получили значение: b"n=5" (буква b перед кавычками означает, что это объект типа bytes — байты)
        raw_query = scope["query_string"]  
        # Преобразуем байты в текст
        # .decode() — метод, который преобразует байты в строку. "utf-8" указывает кодировку, по правилам которой нужно прочитать байты
        # Результат: "n=5"
        query_text = raw_query.decode("utf-8")
        # Метод parse_qs разбирает query-строку и возвращает словарь: {"n": ["5"]}
        # Теперь через query мы можем обращаться к результату разбора: query["n"] --> # ["5"] — список; query["n"][0] --> # "5" — первый элемент списка, строка
        query = parse_qs(query_text) 
        
        try:
            # Вытаскиваем наше значение n
            n = int(query["n"][0])

        except (KeyError, ValueError):
            # KeyError - в query отсутствует ключ "n"
            # ValueError - значение невозможно преобразовать в целое число
            # Подготавливаем описание ошибки: словарь → JSON-строка → байты
            error_1 = json.dumps({"detail": "n must be an integer"}).encode("utf-8")

            # Начинаем HTTP-ответ: статус 422
            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            # Отправляем подготовленное описание ошибки
            await send({
                "type": "http.response.body",
                "body": error_1,
            })

            # Завершаем обработку запроса: вычислять факториал дальше нельзя
            return
        
        if n < 0:
            error_2 = json.dumps({"detail": "n must be non-negative"}).encode("utf-8")
            
            await send({
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            await send({
                "type": "http.response.body",
                "body": error_2,
            })
            return
        
        # Передаем наше значение n, считаем факториал
        result = math.factorial(n)
        # Response_data — Python-словарь с результатом (так как клиент на вход должен получить JSON)
        response_data = {"result": result}
        # Метод json.dumps(response_data) — превращает словарь в строку JSON
        # .encode("utf-8") — превращает строку в байты (обратная операция .decode())
        # Зачем? ASGI требует, чтобы поле body содержало байты. Uvicorn затем передаст их клиенту по сети
        body = json.dumps(response_data).encode("utf-8")

        # Теперь отправляем наш подготовленный ответ
        # Первая часть ответа: статус и заголовки (по лекции)
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                # Content-type: application/json сообщает клиенту формат содержимого (у нас body - это JSON!)
                # В лекции было b"content-type", b"text/plain", так как "body": b"Hello, world!"
                (b"content-type", b"application/json"),
            ],
        })

        # Отправляем тело ответа (по лекции, у нас тоже 1 часть)
        await send({
            "type": "http.response.body",
            "body": body,
        })
        return

    """
    Начинаем Фибоначчи

    Проверяем, что метод запроса — GET,
    а путь начинается с "/fibonacci/".

    startswith() — метод строк, который возвращает True или False.
    Вызываем его у реального пути запроса: scope["path"].

    Примеры:
    "/fibonacci/10".startswith("/fibonacci/") → True
    "/fibonacci/25".startswith("/fibonacci/") → True
    "/factorial".startswith("/fibonacci/")    → False

    На этом шаге выбираем обработчик по началу пути.
    Число в конце пока не проверяем:
    "/fibonacci/abc" тоже даст True.
    """
    if scope["method"] == "GET" and scope["path"].startswith("/fibonacci/"):
        # Получаем путь из словаря scope и сохраняем в переменную path (так удобнее)
        path = scope["path"]
        
        """
        Извлекаем из пути всё, что находится после "/fibonacci/".

        Например, путь "/fibonacci/50" состоит из:
        "/fibonacci/" — постоянного префикса;
        "50" — параметра, который передал клиент.

        len("/fibonacci/") возвращает 11 — длину префикса.
        Индексы начинаются с нуля: префикс занимает позиции 0–10.
        Значение параметра начинается с индекса 11.

        Срез path[11:] берёт символы с индекса 11 до конца строки.
        Число 11 — ПОЗИЦИЯ начала среза, а не получаемое значение.

        Поэтому:
        "/fibonacci/10"[11:]   → "10"
        "/fibonacci/50"[11:]   → "50"
        "/fibonacci/7"[11:]    → "7"
        "/fibonacci/123"[11:]  → "123"

        Пропускаем первые 11 символов и берём весь остаток.
        Результат пока строка: "50", а не число 50.
        """
        n_text = path[len("/fibonacci/"):]

        # Пробуем преобразовать параметр пути в целое число
        try:
            n = int(n_text)

        except ValueError:
            body = json.dumps({"detail": "n must be an integer"}).encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [(b"content-type", b"application/json")],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        # Проверяем отрицательное число.
        if n < 0:
            body = json.dumps({"detail": "n must be non-negative"}).encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": 400,
                "headers": [(b"content-type", b"application/json")],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        # Вычисление по образцу из лекции
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b

        # На слайде в результат передаётся b
        body = json.dumps({"result": b}).encode("utf-8")

        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        })

        await send({
            "type": "http.response.body",
            "body": body,
        })
        return

    """
    Начинаем mean

    Клиент отправляет список чисел в JSON-теле запроса.
    Например:
        метод: GET
        путь: /mean
        тело: [10, 20, 30]

    Через scope узнаём метод и путь запроса:
        scope["method"] → "GET"
        scope["path"]   → "/mean"

    Само тело запроса в scope не содержится.
    Чтобы получить его данные, вызываем переданную сервером
    функцию receive() и ожидаем результат через await:

        event = await receive()

    В event получаем словарь — очередное событие.
    Например:

        {
            "type": "http.request",
            "body": b"[10, 20, 30]",
            "more_body": False,
        }

    "type" описывает вид события: http.request — данные запроса.
    "body" содержит полученную часть тела в байтах.
    "more_body" сообщает, будут ли дополнительные части тела.

    Одного вызова receive() не всегда достаточно:
    тело может приходить несколькими частями.
    При more_body = True нужно продолжить получение,
    при more_body = False всё тело уже получено.

    Полученные байты затем разберём как JSON,
    получим Python-список и вычислим среднее арифметическое.
    """
    if scope["method"] == "GET" and scope["path"] == "/mean":
        # Нужно сохранять полученные части тела запроса, чтобы потом соединить их
        # chunks = [] — создаём пустой список для частей тела (пока тут будут фрагменты байтов, а не список чисел для вычисления среднего)
        # event.get("body", b"") - достаём из события значение "body" (если ключа нет, получаем пустые байты b"")
        chunks = []

        while True:
            # Получаем очередное событие
            event = await receive()
            # Если клиент отключился, то завершаем всю application
            if event["type"] == "http.disconnect":
                return
            # Заполняем массив 
            chunks.append(event.get("body", b""))
            # Если дополнительных частей больше не будет - выходим из цикла
            if not event.get("more_body", False):
                break
        
        # Cоединяем байтовые фрагменты: [b"[10,", b"20,30]"]  →  b"[10,20,30]"
        raw_body = b"".join(chunks)
        """
        json.loads() — разбирает текст JSON в Python-объект
        Механика следующая:
        байты b"[10,20,30]" → decode("utf-8") → строка "[10,20,30]" → json.loads(...) → Python-список [10, 20, 30]
        """
        try:
            data = json.loads(raw_body.decode("utf-8"))

        except (json.JSONDecodeError, UnicodeDecodeError):
            body = json.dumps({"detail": "Body must contain valid JSON"}).encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [(b"content-type", b"application/json")],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        if not isinstance(data, list):
            body = json.dumps({"detail": "Body must be a JSON array"}).encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [(b"content-type", b"application/json")],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })
            return
        
        if not data:
            body = json.dumps({"detail": "Array must not be empty"}).encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": 400,
                "headers": [(b"content-type", b"application/json")],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })
            return
        
        try:
            numbers = []
            # Перебираем элементы списка data
            # float(item) — преобразуем этот элемент в число с плавающей точкой
            # Полученные числа собираются в новый список numbers
            for item in data:
                numbers.append(float(item))

        except (TypeError, ValueError, OverflowError):
            body = json.dumps({"detail": "Array must contain numbers",}).encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": 422,
                "headers": [(b"content-type", b"application/json")],
            })

            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        # Считаем среднее
        result = sum(numbers) / len(numbers)
        body = json.dumps({"result": result}).encode("utf-8")

        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        })

        await send({
            "type": "http.response.body",
            "body": body,
        })

        return

    # Обрабатываем ошибку 404 (неизвестные пути)
    # {"detail": "Not found"} - cловарь с 'ошибкой', его превратили в строку и перевели в байты
    error = json.dumps({"detail": "Not found"}).encode("utf-8")

    await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [
                (b"content-type", b"application/json"),
            ],
        })
    
    await send({
            "type": "http.response.body",
            "body": error,
        })
    return


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:application", host = "0.0.0.0", port = 8000, reload = True)
