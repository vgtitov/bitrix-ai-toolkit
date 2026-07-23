# Тесты toolkit
<!-- DISCIPLINE_ALLOW_TEST_EDIT: документация тестов -->

Функциональные тесты проверочного слоя. Только stdlib (работают в onboard-самотесте без зависимостей).

## Что покрыто
| Тест | Что проверяет | Прогон |
|---|---|---|
| `test_bitrix_guard.py` | детектор N+1 «запрос в цикле» (`scripts/bitrix_guard.py`): ловит плохое, не ложится на хорошее, exit-коды | `python3 tests/test_bitrix_guard.py` |
| ast-grep правила | `core/linters/ast-grep/rules/*.yml` на фикстурах (SQL-инъекция, старое API, N+1, кэш) | `ast-grep scan -c core/linters/ast-grep/sgconfig.yml tests/fixtures/` |

## Фикстуры
- `tests/fixtures/n1_bad.php` — анти-паттерны, которые ДОЛЖНЫ ловиться.
- `tests/fixtures/n1_good.php` — корректный код, ложных срабатываний быть не должно.

## Запуск всех
```bash
python3 tests/test_bitrix_guard.py         # exit 0 = все прошли
# при установленном pytest:
pytest tests/
```

## Ожидаемый вывод (эталон)
```
  PASS test_bad_detected
  PASS test_good_clean
  PASS test_string_literal_not_flagged
  PASS test_exit_code
  4/4 прошли
```

## Принцип
Тесты — на РЕАЛЬНОМ выводе продукта (guard печатает файл:строку). «Зелёное» без показанного вывода не считается.
Правка тестов под код заблокирована дисциплиной (анти-reward-hacking); менять продукт под тест.
