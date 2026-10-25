# ДЗ 5 Тестирование Shop API

В этой папке лежит Shop API из второй домашки и полный набор тестов для него.

Что сделано:

- сохранены и запускаются 39 исходных тестов преподавателя;
- добавлены 49 тестов товаров, корзин, фильтров, пагинации, валидации и ошибок;
- отдельно протестирована работа WebSocket-комнат;
- считается покрытие строк и ветвлений всего пакета `shop_api`;
- минимальный допустимый порог покрытия — 95%;
- GitHub Actions запускает тесты на Python 3.12 и 3.13 и сохраняет XML-отчёт.

## Локальный запуск

Из корня репозитория:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r hw5/requirements.txt
cd hw5
python -m pytest ../hw2/hw/test_homework2.py tests --cov=shop_api --cov-config=.coveragerc --cov-report=term-missing
```

На Windows вместо `source .venv/bin/activate` используется:

```powershell
.venv\Scripts\Activate.ps1
```

Всего запускается 88 тестов. Если хотя бы один тест или порог покрытия не
пройдены, команда и CI завершаются с ошибкой.
