# bitrix-ai-toolkit — AI-first разработка 1С-Битрикс (мульти-агентный контур)

[![CI](https://github.com/vgtitov/bitrix-ai-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/vgtitov/bitrix-ai-toolkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-00B9BF.svg)](LICENSE)
[![PHP 8.2+](https://img.shields.io/badge/PHP-8.2%2B-777BB4.svg)](https://www.php.net/)

*AI agent toolkit for 1C-Bitrix (PHP) development. MIT. Documentation is in Russian.*

Переиспользуемый набор **правил + скиллов + зашитых проверок + MCP-обвязки + документации окружения** для
AI-ассистированной разработки на **1С-Битрикс: Управление сайтом** (PHP). **Не привязан к конкретному AI**: ядро
общее, агент подключается адаптером (из коробки — Claude Code, Codex, Gemini CLI; остальные — см. `adapters/README.md`). Не привязан к конкретной организации — адаптируется под любой проект/редакцию. Принцип: **AI не
угадывает Битрикс, а работает по РЕАЛЬНОМУ коду ядра и справке, по стандартам, доводит код до production-ready.**

## Быстрый старт
```bash
git clone https://github.com/vgtitov/bitrix-ai-toolkit && cd bitrix-ai-toolkit
sh onboard/install.sh            # инструменты + хуки + скиллы + сборка конфигов + самотест
```
`install.sh` ставит линтеры, git-хуки, копирует скиллы в `~/.claude/skills`, собирает `CLAUDE.md`/`AGENTS.md`/`.mcp.json`.
Дальше — перезапустить агента, подтвердить MCP. Подробно: `docs/AI_INSTALL_GUIDE.md`, доступы — `docs/ACCESS_SETUP.md`.

После обновления toolkit повторно выполни `sh onboard/install.sh --no-tools`.
Это применяет изменения hooks, skills и сгенерированных provider-конфигов;
одного `git pull` недостаточно. Если менялись MCP/skills/settings, перезапусти
тот агент, которым пользуешься.

> **Claude Code — первая (эталонная) реализация.** Остальные агенты подключаются минимальной адаптацией из общего
> ядра (`core/`) — см. `adapters/`. Три оси переносимости: **AGENTS.md** (правила) + **SKILL.md** (навыки) + **MCP**
> (инструменты).

> Подходит и для **индивидуальной работы**, и для **команды/компании**: настройки проекта и организации выносятся в
> отдельный слой (`config/local/`, см. `docs/LOCALIZATION.md`), ядро остаётся обезличенным. Конвенции наполняются
> по реальному коду ядра, а не по памяти.

## Ponytail и правило «сначала проверь, что уже есть»

- **[Ponytail](https://github.com/DietrichGebert/ponytail)** (MIT, автор Dietrich Gebert) — плагин для Claude Code и
  Codex: перед написанием кода агент проходит лестницу «нужно ли это вообще → есть ли уже готовое → минимум кода».
  Ставится установщиком вместе с остальными компонентами, на пользователя (действует во всех его проектах).
- **Правило** в `core/AGENTS.md` (блок `check-existing-first`): та же лестница под Битрикс: ядро и D7 API → модули проекта и `/local` → компоненты, события, агенты → одна строка → минимум. Для аналитика:
  есть ли уже типовое решение или существующий отчёт, прежде чем ставить задачу на новое.
- **Ponytail касается только кода, при любой роли.** Постановки, требования, паспорта задач, ТЗ, схемы, протоколы,
  тест-кейсы и обязательные комментарии не сокращаются: их полноту задаёт стандарт команды. Это сказано в правиле
  и в скиллах аналитика и тестировщика. Валидацию, права и защиту данных правило не упрощает.

Режим по роли `--role developer|analyst` (или `BITRIX_ROLE`): `developer` (по умолчанию) → `lite`, `analyst` → `off`.
```bash
sh onboard/install.sh                         # Ponytail ставится вместе с остальным (роль developer)
sh onboard/install.sh --role analyst          # аналитик: Ponytail выключен по умолчанию
sh onboard/install.sh --ponytail-mode full    # режим явно (одиночная работа)
sh onboard/install.sh --no-ponytail           # без плагина
sh onboard/install.sh --project /путь         # куда дописать правило (иначе каталог запуска с composer.json)
```
Обновление — тот же `install.sh --no-tools`, Ponytail ставится и там (кроме тех, кто выключил его руками).

Повторный запуск безопасен: плагин ставится штатными `claude plugin` / `codex plugin`, чужие настройки не
трогаются. Режим пишется в `~/.config/ponytail/config.json`, только если его там ещё нет; сменить потом —
`/ponytail default <режим>` в агенте. После установки в Codex один раз открой `/hooks` и разреши два хука Ponytail;
для хуков нужен `node`.

Выключить насовсем (установщик и обновление уважают): `claude plugin disable ponytail@ponytail`; в Codex —
`enabled = false` в `[plugins."ponytail@ponytail"]` файла `~/.codex/config.toml`; или `/ponytail default off`.
`uninstall`/`remove` не годятся: следующее обновление поставит плагин снова. На время сессии — `stop ponytail`.

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
├── scripts/                  # init_project.py (конфиг под проект) · posttool_lint.py (хук линтеров)
│                             #   bitrix_guard.py (N+1) · changed_files.py (только изменённое)
│                             #   checks_config.py (режимы) · install_git_hooks.py · git-hooks/
│                             #   fetch_official_docs.sh (офиц. дока) · atlassian.py (Jira/Confluence)
├── onboard/install.sh        # идемпотентная автоустановка: инструменты + хуки + скиллы + сборка + самотест
├── tests/                    # функциональные тесты (test_bitrix_guard.py + фикстуры)
├── demo/                     # SETUP.md (развернуть демо за вечер)
└── docs/                     # version-compatibility · AI_INSTALL_GUIDE · ACCESS_SETUP ·
                              # CONTEXT_AND_KNOWLEDGE (где хранить контекст) · ПЛАН_РЕАЛИЗАЦИИ
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
**Cursor, Copilot, Cline** — `npm i -g rulesync && sh build.sh` (конфиг `.rulesync/` уже в репозитории,
наполняется из ядра автоматически).
**Windsurf, Aider** — вручную, буквально один файл. Подробно и честно: `adapters/README.md`.
Общий слой (правила, знания, проверки, MCP-профиль) — один на всех.

## Стек инструментов (бесплатные/опенсорс)
Статанализ — `phpstan/phpstan` (`--error-format=json`); стиль — `PHP-CS-Fixer` + `PHPCSStandards/php_codesniffer`;
рефакторинг — `rectorphp/rector`; тесты — `phpunit`/`pest`; навигация — Grep/ripgrep + `oraios/serena` + `ast-grep`;
ядро в vendor — `bitrix-toolkit/bitrix-ci`; стабы — `matiaspub/bxApiDocs`; миграции — `andreyryabin/sprint.migration`;
референс-конфиг PHPStan — `spaceonfire/bitrix-tools`. Версии проверяй на месте.

## Демо
См. `demo/SETUP.md` — развернуть демо за вечер (без полного Битрикса) + сценарий на 5–7 минут.

## Как участвовать
PR и issue приветствуются — от людей и от AI-агентов. Как внести вклад — `CONTRIBUTING.md`; уязвимости — `SECURITY.md`.

## Происхождение и лицензия
Самостоятельный продукт по AI-разработке Битрикс, по образцу `bsl-ai-toolkit`. Обезличен — никаких внутренних
данных организаций. Лицензия — **MIT** (см. `LICENSE`; оговорки — `NOTICE.md`). Товарные знаки «1С-Битрикс» принадлежат правообладателям;
проект независим и не аффилирован с 1С-Битрикс.
