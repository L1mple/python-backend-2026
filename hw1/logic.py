def fibonacci(n: int) -> int:
    """Вычисляет n-ое число Фибоначчи."""
    numbers = [0, 1]
    for i in range(2, n + 1):
        numbers.append(numbers[i - 1] + numbers[i - 2])
    return numbers[n]


def factorial(n: int) -> int:
    """Вычисляет факториал числа n."""
    if n == 0:
        return 1
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result

def mean(numbers: list[float]) -> float:
    """Вычисляет среднее арифметическое списка чисел."""
    return sum(numbers) / len(numbers)