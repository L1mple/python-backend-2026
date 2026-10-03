# Репозиторий для домашних заданий по курсу "Python Backend"

В этом репозитории будут размещены домашние задания по курсу "Python Backend".

## Локальная разработка

Для управления Python и зависимостями используется
[uv](https://docs.astral.sh/uv/). Установка окружения и Git-хуков:

```bash
make install
```

Основные команды:

```bash
make test      # запустить тесты домашних заданий
make lint      # проверить форматирование, стиль и типы
make format    # автоматически отформатировать код
make run-hw1   # запустить ASGI-приложение первой домашней работы
```

Настройки проекта находятся в `pyproject.toml`. Команда `make test` автоматически
запускает тесты из каталогов домашних заданий вида `hw*/test_*.py`.

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
