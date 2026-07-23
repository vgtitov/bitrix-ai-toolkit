@AGENTS.md

# Claude Code — специфика (поверх общих правил AGENTS.md)

Общие правила разработки — в `AGENTS.md` (импортирован строкой выше). Ниже — только Claude-специфичное.

## Скиллы (авто-подхват по описанию задачи)
`.claude/skills/` — `bitrix-dev`, `bitrix-analyst`, `bitrix-performance`, `bitrix-admin-devops`. Формат SKILL.md
(переносим между агентами). Claude сам подгружает нужный по описанию.

## Хуки (детерминированные проверки)
`.claude/settings.json` — `PostToolUse` на `Edit|Write|MultiEdit`: после правки `*.php` авто-прогон
PHP-CS-Fixer + PHPStan (`--error-format=json`). Агент видит ошибки сразу, чинит без траты токенов на запуск.
Плюс git-хуки (`scripts/install_git_hooks.py`): commit-msg (чистые сообщения) + pre-commit (bitrix-guard N+1).

## MCP
`.mcp.json` — `bitrix-docs` (справка REST), `serena` (символьная навигация; ограничивай `--project`).
На рабочей станции добавь JetBrains MCP (PhpStorm 2025.2+: Settings → Tools → MCP Server) для диагностик/рефакторингов IDE.

## Поиск по коду
Встроенные Grep/Glob (ripgrep) — первичны для поиска по ядру. Serena — для символьной навигации (find_symbol/
find_references). ast-grep (`core/linters/ast-grep/`) — структурный поиск анти-паттернов.

## Правило генерации конфигов
Не правь этот файл руками для общих правил — правь `core/AGENTS.md` и пересобери `sh build.sh`. Здесь — только Claude-специфика.
