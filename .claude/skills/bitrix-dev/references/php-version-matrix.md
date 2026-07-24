# Версионная осведомлённость PHP — что можно писать под таргет проекта

**Правило:** целевая версия — из `config/version-stack.toml` → `[php].version`. **Синтаксис новее таргета не предлагать
вообще**, даже «на будущее» и даже упоминанием «в 8.4 было бы короче» — это шум. Хочется 8.4-фичу → пиши её 8.2-эквивалент.

Минимум для BUS — **8.2** (с 01.02.2026 обновления продукта недоступны ниже). Практический дефолт 2026 — **8.3**.

## Фича → минимальная версия

| Фича | Мин. | Таргет 8.2/8.3 |
|---|---|---|
| `match`, constructor property promotion, named arguments, nullsafe `?->`, attributes, union types, `throw` как выражение, `static` как возврат | 8.0 | ✅ |
| **Enums** (pure + backed), **`readonly` свойства**, first-class callable `strlen(...)`, `never`, `new` в инициализаторах, intersection `A&B`, `final const`, `array_is_list()` | 8.1 | ✅ |
| **`readonly` классы**, DNF-типы `(A&B)|null`, `null`/`false`/`true` как типы, константы в трейтах, **`#[\SensitiveParameter]`** | 8.2 | ✅ |
| Типизированные константы класса `const string X`, `#[\Override]`, динамический fetch константы, `json_validate()` | 8.3 | ⚠️ только если таргет 8.3 |
| **Property hooks**, **асимметричная видимость** `public private(set)`, `#[\Deprecated]`, lazy objects, `array_find/any/all` | 8.4 | ❌ **не предлагать** |
| Пайп `\|>`, `#[\NoDiscard]`, `clone with`, `array_first/last` | 8.5 | ❌ |
| Fibers | 8.1 | ⚠️ почти не нужны (нет async-стека) |

`#[\SensitiveParameter]` (8.2) — **обязательно** для параметров с токенами/паролями: маскирует значение в стектрейсе.

## Депрекейшены, о которые спотыкается легаси Битрикс
- **8.1:** неявное лоссовое `float → int`; передача `null` в non-nullable параметр встроенной функции (массово горит в старых компонентах).
- **8.2:** `${var}`-интерполяция, `utf8_encode/decode`, динамические свойства (ядро их использует — свои классы держать чистыми).
- **8.4:** **неявно nullable параметры** — `function f(int $x = null)` deprecated → `?int $x = null`. Самый массовый warning при апгрейде; чинится Rector `ExplicitNullableParamTypeRector`.
- **8.4:** `E_STRICT`, `E_USER_ERROR` в `trigger_error()`.

## `declare(strict_types=1)` — важная битрикс-оговорка
Действует **на вызовы из этого файла**, не на весь стек.
- ✅ **Всегда** в своих PSR-4 классах (`/local/classes`, `/local/modules/*/lib`): домен, сервисы, репозитории, контроллеры.
- ⚠️ **Осторожно** в `component.php`, `template.php`, `result_modifier.php`, `init.php`: туда всё приходит строками
  (`$arParams['IBLOCK_ID']`, `$_REQUEST`), а ядро местами принимает «строку вместо int» → `TypeError` из ядра.
- **Практика:** строгость в классах; компонент — тонкая прослойка, которая **явно кастует** `(int)$arParams['IBLOCK_ID']`
  перед передачей в типизированный сервис.

Источники: php.net/releases/8.3, /8.4, /8.5, migration guides.
