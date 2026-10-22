# Репозиторий для домашних заданий по курсу "Python Backend"

В этом репозитории будут размещены домашние задания по курсу "Python Backend".

## Третья домашняя работа

Ветка `codex/hw3-monitoring` создана от `codex/hw2-submission`.
Shop API из ДЗ №2 запускается вместе с Prometheus и Grafana:

```bash
make up-hw3    # собрать образ и запустить три сервиса
make demo-hw3  # отправлять запросы 3 минуты для наполнения графиков
make down-hw3  # остановить контейнеры, сохранив данные мониторинга
```

API: <http://127.0.0.1:8000/docs>, Prometheus: <http://127.0.0.1:9090>,
Grafana: <http://127.0.0.1:3000>. Два дашборда загружаются автоматически.
Подробности и скриншоты — в [описании ДЗ №3](hw3/README.md).

## Вторая домашняя работа

Ветка `codex/hw2-submission` содержит решение
[`hw2/hw`](hw2/hw/README.md): REST/RPC API магазина и дополнительный
WebSocket-чат с отдельными комнатами. В этой ветке первая домашняя работа
сохранена в исходном виде из репозитория курса.

Для разработки используется [uv](https://docs.astral.sh/uv/) и зависимости
из `uv.lock`. Команды выполняются из корня репозитория:

```bash
make install   # установить зависимости и Git-хуки
make run-hw2   # запустить Shop API и WebSocket-чат
make test      # исходные и дополнительные тесты HW2
make lint      # форматирование, стиль и типы решения HW2
```

После запуска документация API доступна на <http://127.0.0.1:8000/docs>.
GitHub Actions проверяет решение HW2 на Python 3.13 и 3.14.
Для сдачи создаётся PR из `Mikhail-Osintsev:codex/hw2-submission` в
`L1mple/python-backend-2026:main` с упоминанием дополнительного задания WebSocket.

## 🚀 Как начать работу

### 1. Форкните репозиторий
1. Перейдите на страницу репозитория GitHub
2. Нажмите кнопку "Fork" в правом верхнем углу
3. Выберите свой аккаунт GitHub для создания форка

### 2. Склонируйте свой форк
```bash
git clone https://github.com/ВАШ_USERNAME/python-backend-2026.git
cd python-backend-2026
```

### 3. Полезные ссылки курса

- [Репозиторий с примерами](https://github.com/L1mple/python-backend-2026) -
  вы уже тут
- [Лекции в
  pdf](https://drive.google.com/drive/folders/1A8rFJ7kNq9CwpWkELyjNvny550dUOMw_?usp=drive_link)
  (так же будут постепенно подгружаться)
- [Оценки и домашки](https://docs.google.com/spreadsheets/d/1PNxseoY3KyzFNavTBwNDoOSuVKc79Zt6U4LUr2zB53Y/edit?usp=sharing)
