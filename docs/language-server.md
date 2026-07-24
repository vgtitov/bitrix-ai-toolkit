# Language Server для PHP/Битрикс — переиспользуем готовое (аналог BSL-LS)

Как для 1С мы оборачиваем **BSL Language Server** в MCP, для PHP/Битрикс переиспользуем готовые зрелые LS.
**Битрикс-специфичного LS не существует** (проверено) — «битриксовость» добавляется стабами ядра, а не отдельным сервером.

## Что переиспользовать
| Слой | Инструмент | Лицензия | Комментарий |
|---|---|---|---|
| **Навигация/типы/hover/rename** | **Intelephense** | проприетарный (базовое бесплатно) | Самый быстрый и полный; его же берут Anthropic `php-lsp` и Serena. Premium — по ключу. |
| — альтернатива (open-source) | **Phpactor** | MIT | Полностью открытый; навигация+рефакторинг; диагностику добирает PHPStan/Psalm. Бери, если нужен форк/вендоринг как у BSL. |
| **Диагностика/стандарты** (аналог ИТС) | **Psalm `--language-server`** | MIT | Единственный из статанализаторов с ВСТРОЕННЫМ LSP. Отдаёт диагностики как LS. |
| — или | **PHPStan** (CLI→JSON) | MIT | Нет встроенного LSP; проще дёргать `analyse --error-format=json` (уже в хуках). |
| **«Битриксовость»** | стабы ядра | — | `krotVidit/Bitrix24-Stub-Generator`, gist xTCry; либо реальное ядро в `vendor` (`bitrix-ci`). Подключается `intelephense.stubs`/`includePaths`. |

## Как обернуть в MCP (прямой аналог `bsl_ls_mcp`)
Generic-мост **isaacphi/mcp-language-server** превращает любой LS в MCP-инструменты (`definition`, `references`,
`rename_symbol`, `hover`, `diagnostics`) — ровно наш паттерн.

**Локально:**
```bash
go install github.com/isaacphi/mcp-language-server@latest
npm install -g intelephense
claude mcp add php-lsp -- mcp-language-server --workspace "$(pwd)" --lsp intelephense -- --stdio
# нюанс: для отдачи диагностик Intelephense иногда нужен --loglevel debug (issue #85)
```
Диагностику стандартов можно добавить ВТОРЫМ инстансом на Psalm:
```bash
claude mcp add php-diagnostics -- mcp-language-server --workspace "$(pwd)" --lsp "psalm --language-server"
```

## Три готовых пути (выбор под задачу)
1. **Проще всего для Claude Code** — нативный плагин `php-lsp@claude-plugins-official` (Intelephense под капотом) или
   `zircote/php-lsp` (Intelephense + php-cs-fixer + PHPStan сразу). Не MCP — нативный LSP-плагин.
2. **Переносимо на любой AI (наш паттерн)** — `isaacphi/mcp-language-server` → Intelephense/Phpactor/Psalm. **Опционален**
   (не в дефолтном профиле `core/mcp/servers.json`, чтобы не требовать установки go/intelephense у всех) — подключаешь
   командой `claude mcp add php-lsp -- mcp-language-server …` (см. выше), когда нужен LSP агенту.
3. **Готовое «всё в одном»** — **Serena** (уже в профиле): даёт и символьную навигацию, и `get_diagnostics_for_file`
   через Intelephense. Часто этого достаточно, отдельный LS-мост не нужен.

## Локально vs центральный Docker
- **Локально** — LSP по своей природе привязан к рабочему пространству разработчика (per-project), поэтому php-lsp/Serena
  запускаются локально у каждого. Это основной режим.
- **Центрально (Docker)** — в общий контейнер выносим то, что не привязано к рабочему месту: **справку** (bitrix-docs,
  уже hosted), **общий поиск по коду ядра** и **прогон проверок** (PHPStan/ast-grep как shared-сервис/CI). См. `docker/`.
- Правило: **локально работает всегда; центральный Docker — опционально ускоряет команду, но toolkit самодостаточен без него.**

## Чего НЕ существует (честно)
Отдельного Bitrix-aware language server нет. Связка **Intelephense/Phpactor (навигация) + PHPStan/Psalm (диагностика) +
стабы ядра** покрывает ту же роль, что BSL-LS для 1С.
