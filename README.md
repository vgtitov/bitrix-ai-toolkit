# bitrix-ai-toolkit — AI-first разработка 1С-Битрикс (мульти-агентный контур)

[![License: MIT](https://img.shields.io/badge/License-MIT-00B9BF.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![AGENTS.md](https://img.shields.io/badge/AGENTS.md-ready-blue.svg)](AGENTS.md)
[![PHP 8.2+](https://img.shields.io/badge/PHP-8.2%2B-777BB4.svg)](https://www.php.net/)
[![Bitrix](https://img.shields.io/badge/1С--Битрикс-BUS-orange.svg)](https://dev.1c-bitrix.ru/)

Переиспользуемый набор **правил + скиллов + зашитых проверок + MCP-обвязки + документации окружения** для
AI-ассистированной разработки на **1С-Битрикс: Управление сайтом** (PHP). **Не привязан к конкретному AI**: ядро
общее, агент подключается адаптером (из коробки — Claude Code, Codex, Gemini CLI; остальные — см. `adapters/README.md`). Не привязан к конкретной организации — адаптируется под любой проект/редакцию. Принцип: **AI не
угадывает Битрикс, а работает по РЕАЛЬНОМУ коду ядра и справке, по стандартам, доводит код до production-ready.**

> **Claude Code — первая (эталонная) реализация.** Остальные агенты подключаются минимальной адаптацией из общего
> ядра (`core/`) — см. `adapters/`. Три оси переносимости: **AGENTS.md** (правила) + **SKILL.md** (навыки) + **MCP**
> (инструменты).

> Подходит и для **индивидуальной работы**, и для **команды/компании**: настройки проекта и организации выносятся в
> отдельный слой (`config/local/`, см. `docs/LOCALIZATION.md`), ядро остаётся обезличенным. Конвенции наполняются
> по реальному коду ядра, а не по памяти.

## Идея
У Битрикс два поколения ядра (процедурное + D7), много legacy, фрагментированная документация и **нет официальных
IDE-стабов и публичного репо ядра**. Поэтому рычаг — не «облачные индексы публичных либ», а: (1) реальный код ядра в
`vendor/` (`bitrix-ci`) + стабы (`bxApiDocs`), чтобы агент/PHPStan/PhpStorm видели классы; (2) локальный поиск по
коду (Grep/Serena/ast-grep); (3) детерминированные хуки на линтеры; (4) `CLAUDE.md` как карта окружения. Готового
MCP «под разработку сайта на Битрикс» на рынке нет — это и есть ниша этого toolkit.

## Состав
```
bitrix-ai-toolkit/
├── core/                     # ЕДИНЫЙ ИСТОЧНИК ИСТИНЫ (общий для всех AI-агентов)
│   ├── AGENTS.md             # правила (2 ядра, /local-гейт, «спроси инструмент», версии, безопасность, качество)
│   ├── skills/               # SKILL.md: bitrix-dev · bitrix-analyst · bitrix-performance (+refs) · bitrix-admin-devops
│   ├── linters/              # phpstan.neon.dist (+совместимость по версии) · ast-grep/rules · phpcs · cs-fixer · rector
│   └── mcp/servers.json      # MCP-профиль: bitrix-docs (REST), serena (навигация)
├── adapters/                 # тонкие адаптеры под агентов
│   ├── claude/               #   эталон: CLAUDE.md (@AGENTS.md), settings.json (хуки)
│   └── README.md             #   codex/gemini (фолбэк) · cursor/copilot/cline/windsurf/aider (rulesync/ручные)
├── build.sh                  # генерация конфигов из core/ (rulesync + фолбэк): CLAUDE.md, AGENTS.md, .mcp.json, .claude/
├── config/                   # локализация: version-stack.toml (версии PHP/ядра/модулей, legacy_required)
├── scripts/                  # bitrix_guard.py (детектор N+1) · install_git_hooks.py · git-hooks/ (commit-msg, pre-commit)
├── onboard/install.sh        # идемпотентная автоустановка: инструменты + хуки + скиллы + сборка + самотест
├── tests/                    # функциональные тесты (test_bitrix_guard.py + фикстуры)
├── demo/                     # SETUP.md (развернуть демо за вечер)
└── docs/                     # version-compatibility · AI_INSTALL_GUIDE · ACCESS_SETUP · ПЛАН_РЕАЛИЗАЦИИ
```
Сгенерированные из `core/` файлы (`CLAUDE.md`, `AGENTS.md`, `.mcp.json`, `.claude/`) закоммичены, чтобы репо работал
сразу после клонирования. Правь `core/` → пересобирай `sh build.sh` (не редактируй сгенерированное вручную).

## Ключевые принципы (методология)
- **Спроси инструмент, не угадывай** — сигнатуры/поведение только по коду ядра (`bitrix-ci`/Grep/Serena) и справке
  (dev.1c-bitrix.ru), не по памяти. После правки — PHPStan + PHP-CS-Fixer (детерминированно, хуком).
- **Два ядра** — различай процедурное (`$APPLICATION`, `CIBlockElement`) и D7 (`Bitrix\Main\*`, ORM). Новый код — D7.
- **Гейт `/local`-only** — ядро `/bitrix/modules` read-only (перезаписывается при обновлении). Правки — только `/local`.
- **Структура — миграциями** — инфоблоки/HL/свойства/права через `sprint.migration`, не руками в БД.
- **Reuse-first + производительность + безопасность** — готовое в ядре/marketplace вместо велосипедов; кэш
  компонентов и `Bitrix\Main\Data\Cache`; защита от SQL-инъекций (ORM/`$DB->ForSql`), XSS (`htmlspecialcharsbx`),
  path traversal, проверка прав.

## Три канала интеграции с AI-агентом (Claude Code — первая реализация)
1. **Hooks** (`.claude/settings.json`, `PostToolUse`) — прогон phpstan/php-cs-fixer после Edit/Write. Основной канал.
2. **LSP-плагин** (`php-lsp`/Intelephense или Phpactor) — навигация/диагностики. Нужен `composer dump-autoload -o`.
3. **MCP** — `bitrix24/mcp-rest-doc` (справка REST), Serena (символьная навигация), JetBrains MCP (диагностики IDE).

## Поддерживаемые агенты
**Из коробки `build.sh` собирает три:** **Claude Code** (эталон: `CLAUDE.md` + скиллы + хуки + MCP),
**Codex** и **Gemini CLI** (через `AGENTS.md` — его многие агенты читают нативно).
**Cursor, Copilot, Cline** — через генератор `rulesync` (`npm i -g rulesync`, в toolkit не входит).
**Windsurf, Aider** — вручную, буквально один файл. Подробно и честно: `adapters/README.md`.
Общий слой (правила, знания, проверки, MCP-профиль) — один на всех.

## Стек инструментов (бесплатные/опенсорс)
Статанализ — `phpstan/phpstan` (`--error-format=json`); стиль — `PHP-CS-Fixer` + `PHPCSStandards/php_codesniffer`;
рефакторинг — `rectorphp/rector`; тесты — `phpunit`/`pest`; навигация — Grep/ripgrep + `oraios/serena` + `ast-grep`;
ядро в vendor — `bitrix-toolkit/bitrix-ci`; стабы — `matiaspub/bxApiDocs`; миграции — `andreyryabin/sprint.migration`;
референс-конфиг PHPStan — `spaceonfire/bitrix-tools`. Версии проверяй на месте.

## Установка
```bash
git clone https://github.com/vgtitov/bitrix-ai-toolkit && cd bitrix-ai-toolkit
sh onboard/install.sh            # инструменты + хуки + скиллы + сборка конфигов + самотест
```
`install.sh` ставит линтеры, git-хуки, копирует скиллы в `~/.claude/skills`, собирает `CLAUDE.md`/`AGENTS.md`/`.mcp.json`.
Дальше — перезапустить агента, подтвердить MCP. Подробно: `docs/AI_INSTALL_GUIDE.md`, доступы — `docs/ACCESS_SETUP.md`.

## Демо
См. `demo/SETUP.md` — развернуть демо за вечер (без полного Битрикса) + сценарий на 5–7 минут.

## Как участвовать
PR и issue приветствуются — от людей и от AI-агентов. Как внести вклад — `CONTRIBUTING.md`; уязвимости — `SECURITY.md`.

## Происхождение и лицензия
Самостоятельный продукт по AI-разработке Битрикс, по образцу `bsl-ai-toolkit`. Обезличен — никаких внутренних
данных организаций. Лицензия — **MIT** (см. `LICENSE`). Товарные знаки «1С-Битрикс» принадлежат правообладателям;
проект независим и не аффилирован с 1С-Битрикс.
