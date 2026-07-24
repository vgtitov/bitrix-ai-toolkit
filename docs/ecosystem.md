# Карта экосистемы: что живо, что мертво

**Зачем:** AI-агент, ища решение, находит в Google и на GitHub популярные, но **заброшенные** пакеты и предлагает их.
Этот файл — прививка. Проверено на 07.2026.

## ✅ Официальный AI-контур Битрикс (`github.com/bitrix-tools`) — в awesome-списках ОТСУТСТВУЕТ
| Репозиторий | Лицензия | Что даёт |
|---|---|---|
| **framework-docs** | **MIT** | Официальная документация Bitrix Framework в Markdown. **Подтягивается `scripts/fetch_official_docs.sh`** → агент грепает первоисточник |
| **best-practice** | ⚠️ **без лицензии** | Официальные правила для AI-агентов (AGENTS.md + скиллы). Смотреть можно, **копировать в свой репозиторий нельзя**. Ставится: `npx skills add bitrix-tools/best-practice` |
| **marketplace-security-skills** | **MIT** | Скиллы + Python-сканер безопасности модулей (attack surface, ActionFilter, `check_bitrix_sessid`, CP1251, журнал находок) |
| **env-docker** | — | Официальные контейнеры для Битрикс |
| **b24-rest-docs** | — | Исходник REST-справки (её отдаёт наш MCP `bitrix-docs`) |

Плюс **`bxmaximum/bitrix_ai_challenge`** — готовый бенчмарк AI-моделей на реальной Битрикс-задаче (модуль «Избранное»:
REST + ORM + шифрованные cookie + миграция при логине + тегированный кэш + компонент), 10 критериев × 10 баллов.
Можно измерять пользу toolkit: прогон с контуром и без.

## ✅ Живое и рекомендуемое
| Пакет | Роль |
|---|---|
| `andreyryabin/sprint.migration` | миграции **структуры** — стандарт де-факто |
| `INTERVOLGA/intervolga.migrato` | миграции **данных** сущностей между окружениями (дополняет sprint.migration) |
| `bitrixdock/bitrixdock`, `bitrix-tools/env-docker` | локальные окружения |
| `saundefined/bitrix-idea` | плагин PhpStorm для навигации по ядру (человеку рядом с агентом) |
| `deptrac/deptrac`, `phparkitect/arkitect`, `phpat/phpat` | контроль слоёв (то, чего PHPStan не ловит) |
| `spaze/phpstan-disallowed-calls` | декларативный запрет вызовов (лучший ROI) |
| `roave/security-advisories` + `composer audit` | безопасность зависимостей |
| `phpmd/phpmd`, `jscpd`, `shipmonk/composer-dependency-analyser`, `infection/infection`, `nunomaduro/phpinsights`, `bmitch/churn-php` | качество: сложность, копипаста, зависимости, мутации, аудит, «что рефакторить первым» |
| `brick/money` | **деньги** (штатного в Битрикс нет; float даёт расхождения копеек) |
| `halaxa/json-machine` | потоковый разбор гигабайтных выгрузок 1С без OOM |
| `webpractik/bitrixoa` | OpenAPI/Swagger из Bitrix-контроллеров |

## ❌ Мёртвое — НЕ предлагать и не тащить
| Пакет | Состояние | Чем заменить |
|---|---|---|
| `arrilot/bitrix-models`, `arrilot/bitrix-migrations` | архив (2021/2022) | D7 ORM; `sprint.migration` |
| `bitrix-expert/bbc`, `/tools`, `/monolog-adapter` | 2017–2019 | штатное ядро |
| `notamedia/console-jedi` | 2022 | свои cli-команды |
| `worksolutions/bitrix-module-migrations` | помечен DEPRECATED | `sprint.migration` |
| `studiofact/*`, `DigitalWand/admin_helper` | 2017–2018 / полуживой | — |
| `mesilov/bitrix24-php-sdk` | abandoned на Packagist | `bitrix24/b24phpsdk` (это для B24, не для BUS) |
| `sebastianbergmann/phpcpd` | архив (2023) | **jscpd** |
| `fabpot/local-php-security-checker` | архив | **`composer audit`** (встроен в Composer 2.4+) |
| `awesomebitrix/awesome-bitrix` как источник | заморожен (04.2023), 80% — курсы и конференции 2013–2017 | этот файл |

## ⚖️ Штатное ядро vs сторонняя библиотека
Официальная линия — **framework-native first**. Сторонний пакет там, где есть штатное, ломает согласованность
(события, права, кэш, обмен с 1С) и противоречит best practices вендора.

| Задача | Штатное | Стороннее — когда |
|---|---|---|
| Логи | `Diag\Logger` (PSR-3) | Monolog — за `LoggerInterface`, ради Sentry/ELK |
| HTTP | `Main\Web\HttpClient` (**`setPrivateIp(false)` против SSRF** — подтверждено в `pages/security/csrf-ssrf.md`) | Guzzle — если требует SDK; изолировать в интеграционном слое |
| Дата | `Main\Type\Date`/`DateTime` | Carbon — сложные календарные расчёты в своём домене |
| Валидация | `Main\Validation` | — |
| Ошибки | `Main\Error`/`Result` | — |
| DI | `ServiceLocator` (PSR-11) | внешний контейнер при >40-50 сервисов, скомпилированный |
| XSS/санитайз/шифр | `htmlspecialcharsbx`, `Text\HtmlFilter`, `Sanitizer`, `Security\Cipher` | — |
| **Деньги** | ⚠️ нет | копейки как int или `brick/money` |

## Не нужно (дублирует наше или ядро)
`GrumPHP`/`CaptainHook` (у нас свой `install_git_hooks.py`) · `Respect/Validation`, `PHP-DI`, `league/container` ·
`AntiXSS`/`HTMLPurifier`/`halite`/`defuse` · Laravel-специфика (Pint, larastan, Enlightn) · `phpDocumentor`
(агент читает код).
