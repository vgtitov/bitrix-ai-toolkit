# AGENTS.md — правила разработки 1С-Битрикс с AI-агентом

Единый свод правил, **общий для всех AI-агентов** — не привязан к конкретному (по открытому стандарту [agents.md](https://agents.md/)).
Из этого файла генерируются конфиги под конкретные агенты (Claude Code, Cursor, Gemini CLI, Copilot, Cline, Codex…) —
см. `adapters/` и `build.sh`. Claude Code не читает AGENTS.md нативно → подключается через `@AGENTS.md` в `CLAUDE.md`.

Область: **1С-Битрикс: Управление сайтом (BUS)** — сайты и интернет-магазины на PHP. Не Битрикс24, не 1С:Предприятие.

---

## Правило №0: перед работой — синхронизация
`git pull` toolkit и репозитория проекта; `composer install` (свежий autoload и стабы). Не работать на устаревшем клоне.

## Версионный стек — НАСТРОЙ ПОД ПРОЕКТ
- **PHP:** таргет **8.2 / 8.3** (с 01.02.2026 обновления BUS недоступны на PHP < 8.2). Legacy 7.4/8.0 — вне поддержки,
  цель — апгрейд через Rector.
- **Редакция и версия BUS** (Старт/Стандарт/Малый бизнес/Бизнес/Энтерпрайз) + версии модулей ядра
  (`main`, `iblock`, `catalog`, `sale`, `highloadblock`) — API отличается между версиями.
- **Стандарт кода:** PSR-12 (у Битрикс нет своего codesniffer-ruleset; официально — PSR-1 + стиль PSR-2/PSR-12).

## Главное правило: спроси инструмент, не угадывай
Модель врёт в деталях API Битрикс (два ядра, много legacy, неполная `api_d7`). Источник истины — реальный код и справка:

**Официальная документация локально** (подтянуть: `sh scripts/fetch_official_docs.sh`) — `bitrix-tools/framework-docs`
(MIT) в `.ai/framework-docs/pages/`: `orm`, `security` (sql-injection, xss, csrf-ssrf, sanitizer, cipher…),
`performance` (caching, query-optimization, composite-site, clustering), `database/sql-tracker`, `advanced/{debug,logger,http-client}`.
**Ищи грепом по ней прежде, чем отвечать по памяти:**
```bash
rg -n "setPrivateIp|SSRF"        .ai/framework-docs/pages/security
rg -n "registerTag|TaggedCache"  .ai/framework-docs/pages/performance
```
Если утверждение не подтверждено ни кодом ядра, ни этой документацией — помечай **[проверить]**.

- **Перед написанием** — найди как уже сделано: поиск по `/local` и по ядру (Grep/ripgrep, символьно — Serena
  `find_symbol`). Сигнатуры классов ядра — по реальному коду в `vendor/bitrix-toolkit/bitrix-ci` или стабам
  `matiaspub/bxApiDocs`; справка — dev.1c-bitrix.ru. **Не по памяти.**
- **После правки** — прогнать **PHPStan** (`--error-format=json`) и **PHP-CS-Fixer** (детерминированно, хуком/скриптом).
  До 3 циклов автоисправления. Механизм без сверки помечать **[проверить]**, не «верно».
- Нет поведения ни в коде, ни в справке — так и сказать.

## Слои поиска — их может быть ТРИ, а не два
Стандартно: ядро Битрикс + `/local`. Но если в `config/version-stack.toml` есть `[[custom_layers]]` — в проекте
**свой фреймворк подрядчика/предыдущей команды** поверх Битрикс (нередко 30-40% функционала, свой namespace).
Тогда порядок поиска: **кастомный слой → ядро Битрикс → `/local`** (при `priority = "over-bitrix"`).
Документация Битрикс про их код ничего не знает — источник правды — их код (грепом/символьно).
Непроверенное помечай `[кастомный слой, проверить]`. Подробно — `core/skills/bitrix-dev/references/custom-framework.md`.

## Два ядра — различай явно
- **Старое ядро (процедурное):** `$APPLICATION`, `$USER`, `$DB`; `CIBlockElement::GetList`, `CModule`, `CFile`,
  `CCatalogProduct`. Живёт: на нём написана бо́льшая часть `sale`/`catalog`/`iblock`. Справка: dev.1c-bitrix.ru/api_help/
- **D7 (ООП, целевое):** `Bitrix\Main\*`, ORM (`*Table::getList()`, `Bitrix\Main\ORM\*`), сервис-локатор
  (`ServiceLocator`), события (`EventManager`), `Application`, `Data\Cache`/`TaggedCache`. Справка: dev.1c-bitrix.ru/api_d7/
  (неполна → исходники ядра + курс «Разработчик Bitrix Framework»).
- **Правило:** новый код — на D7 (`ElementTable::getList` вместо `CIBlockElement` где возможно); legacy-API изолировать
  за своими сервисами/репозиториями. Интероп со старым ядром неизбежен — часть API (заказы, скидки) только в `C*`-классах.

## Гейт: правки только в `/local`, ядро read-only
- **Не трогать `/bitrix/modules`** — перезаписывается при обновлении продукта, правки теряются и ломают систему.
- Кастомизация типового компонента — **копированием в `/local/components`**, не правкой ядра. Приоритет системы:
  `/local/*` → `/bitrix/*` (components, templates, modules, php_interface, activities).
- **Структуру инфоблоков/HL/свойств/прав — только миграциями** (`andreyryabin/sprint.migration`, живой; НЕ мёртвый
  arrilot). `php sprint.php migrate` после деплоя. Не руками в БД/админке без версионирования.
- События/обработчики — в `/local/php_interface/init.php` (`AddEventHandler` / `EventManager::addEventHandler`).
- Свои классы — PSR-4 (`\Local\...` → `local/classes` или `src/`), composer.json/vendor вне DOCUMENT_ROOT.
- `.gitignore`: ядро `/bitrix` и `upload/` не версионировать; в git — `/local` + composer + миграции.

## Производительность (кратко; глубоко — скилл `bitrix-performance`)
Битрикс тормозит предсказуемо. Обязательный минимум:
- **Кэшируй компоненты** (`CACHE_TIME`, `StartResultCache/EndResultCache`); произвольные данные — `Data\Cache`/
  `TaggedCache` со сбросом по тегам инфоблока. Не отдавай тяжёлые запросы без кэша.
- **Запросы:** явные `select`/`filter`, не выбирать лишнее; **никогда — запрос в цикле** (собирай `filter` по массиву ID).
- **Большие справочники/характеристики** — highload-блоки. Каталог на объёмах — фасетный индекс умного фильтра.
- **Композитный сайт (Composite)** для контентных страниц; OPcache + Redis/memcached как хранилище кэша.
Диагностика «почему медленно»: модуль perfmon → медленные страницы → запросы → кэш. Инструменты: Xhprof/xhgui, Blackfire,
slow query log, `EXPLAIN`.

## Безопасность (чек-лист ревью)
- **SQL-инъекции:** только ORM / `$DB->ForSql()`; никакой конкатенации ввода в запрос.
- **XSS:** вывод — `htmlspecialcharsbx()`, не голый echo пользовательских данных.
- **Path traversal:** нормализуй/проверяй пути в файловых операциях (`CFile`, `upload/`).
- **Права:** `$USER->CanDoOperation()` перед действием; не доверять `$_REQUEST`.
- **CSRF:** формы с `bitrix_sessid()`/`check_bitrix_sessid()`.
- Токены/ключи вебхуков — только в env, не в код/чат. Персональные данные клиентов в модель не передавать.

## Опциональность проверок — качество не зависит от режима
Проверки настраиваются (`config/checks.toml`, `config/local/checks.toml`, env `BITRIX_AI_CHECKS`):
- **`off`** — не запускать; **`warn`** (ДЕФОЛТ) — показать находки, НЕ блокировать; **`block`** — блокировать/чинить до конца.
- Дефолт мягкий осознанно: проверки не должны мешать работать. Строгий гейт — личный выбор на своём коде.
- Нет инструмента (ast-grep/PHPStan) → шаг тихо пропускается. Нет конфига → дефолты. **Ничего не падает.**

**Главное:** пиши качественный код ВСЕГДА, независимо от режима. Свод, который надо соблюдать проактивно —
`core/skills/bitrix-dev/references/quality-standards.md` (это то, что поймал бы линтер). Проверки лишь подтверждают.
Если ядро проекта правлено (`core_modified = true`) — сигнатуры по ФАКТИЧЕСКОМУ коду, пометка `[правлено ядро]`
(`core/skills/bitrix-dev/references/custom-core.md`).

## Инструменты качества (зашитая проверка)
- **PHPStan** + стабы ядра (`bitrix.stub`, `orm.stub`+`orm_annotations`, `scanDirectories` на модули ядра).
  Уровни: legacy — низкий (1), новый код в `/local` — 4+ (референс-конфиг: `spaceonfire/bitrix-tools`, Habr 961832).
- **PHP-CS-Fixer** (PSR-12) + опц. **PHP_CodeSniffer** (`PHPCSStandards/php_codesniffer` — актуальный форк).
- **Rector** — апгрейд PHP legacy→8.2/8.3 (`withPhpSets`, всегда `--dry-run` → apply).
- **PHPUnit** — слабое место рынка Битрикс = максимальная дельта AI. Тестируемость требует вынесения кода в PSR-4-классы `/local`.
- Прогон детерминированно: хуки агента (`PostToolUse`) + composer scripts (`cs-fix`, `phpstan`, `rector`) + CI (GitLab/GitHub).

## Скиллы toolkit (формат SKILL.md — переносимый между агентами)
- `bitrix-dev` — написание/ревью PHP: D7 ORM, компоненты, инфоблоки, события, кэш, безопасность, PSR-12.
- `bitrix-analyst` — анализ/архитектура: где что в ядре, старое vs D7, влияние доработки, ЧТЗ.
- `bitrix-performance` — производительность и highload: кэш-слои, оптимизация запросов, композит, диагностика «тормозит».
- `bitrix-admin-devops` — установка/обновление, публикация, деплой `/local`, миграции, окружение (bitrixdock/BitrixVM), CI/CD, бэкап.
- `bitrix-tester` — QA: какой уровень проверки (статика/юнит/стейджинг-смоук/браузер/мутационное тестирование)
  ДОСТАТОЧЕН для конкретного изменения; вердикт только по цитируемому выводу прогона, не по ощущению.
- `bitrix-dba` — DBA слоя СУБД (MySQL/MariaDB): тюнинг `my.cnf`, регламент обслуживания, блокировки/deadlock,
  бэкап и восстановление, репликация/веб-кластер — отдельно от оптимизации запросов (`bitrix-performance`).

## Что агент НЕ делает без человека
Изменения структуры БД вне миграций; правки в ядре `/bitrix`; деструктив с данными магазина; передачу персональных
данных клиентов в модель. Любую правку человек принимает после проверки (в т.ч. в PhpStorm через JetBrains MCP).
