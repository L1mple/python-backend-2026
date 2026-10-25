## ДЗ 4

[![Coverage Status](https://coveralls.io/repos/github/xomnrt/python-backend-2026/badge.svg?branch=hw4)](https://coveralls.io/github/xomnrt/python-backend-2026?branch=hw4)
[![HW4 Tests](https://github.com/xomnrt/python-backend-2026/actions/workflows/hw4-tests.yml/badge.svg?branch=hw4)](https://github.com/xomnrt/python-backend-2026/actions/workflows/hw4-tests.yml?query=branch%3Ahw4)

За каждый пункт - 1 балл

Внедрить во вторую домашку хранение данных в БД, для этого надо:

1. Добавить БД в docket-compose.yml (если БД - это отдельный сервис, если хотите использовать sqlite, то можно скипнуть этот шаг)
2. Переписать код на взаимодействие с вашей БД (если вы еще этого не сделали, если вы уже написали код с БД, подзравляю, вам остался только 3 пункт)
3. В свободной форме, напишите скрипты, которые просимулируют разные "проблемы" которые могут возникнуть в транзакциях (dirty read, not-repeatable read, serialize) и настраивая уровне изоляции покажите, что они действительно решаются (через SQLAlchemy например), то есть:
   показать dirty read при read uncommited
   показать что нет dirty read при read commited
   показать non-repeatable read при read commited
   показать что нет non-repeatable read при repeatable read
   показать phantom reads при repeatable read
   показать что нет phantom reads при serializable
   \*Тут зависит от того какую БД вы выбрали, разные БД могут поддерживать разные уровни изоляции

# ДЗ 5

1. Добиться 95% покрытия тестами вашей второй домашки - 1 балл

2. Настроить автозапуск этих тестов в CI, если вы подключали сторонюю БД, то можно посмотреть вот [сюда](https://dev.to/kashifsoofi/integration-test-postgres-using-github-actions-3lln), чтобы поддержать тесты с ней в CI. По итогу у вас должен получится зеленый пайплайн - оценивается в еще 2 балла.

## Запуск

Сначала запустите PostgreSQL из корня репозитория:

```bash
docker compose -f hw4/docker-compose.yml up -d postgres
```

Затем запустите тесты:

```bash
DATABASE_URL=postgresql://user:password@localhost:5433/master \
hw4/venv/bin/python -m pytest -v \
    --cov=hw4.lib \
    --cov-report=term-missing \
    --cov-fail-under=95 \
    hw4/tests
```
