# Адаптеры под разные AI-агенты

Тонкие адаптеры поверх `core/` (единый источник истины). Claude Code — эталон, остальные — маппинг путей/ключей.
Генерация: `sh build.sh` (использует rulesync, если установлен; иначе минимальный фолбэк симлинками).

| Агент | Файл правил | MCP-конфиг (ключ) | Статус |
|---|---|---|---|
| **claude** | `CLAUDE.md` (`@AGENTS.md` + спец) | `.mcp.json` (`mcpServers`) | ✅ **работает из коробки** (эталон) |
| **codex** | `AGENTS.md` (читает нативно) | `~/.codex/config.toml` (TOML) | ✅ **работает** — `build.sh` кладёт `AGENTS.md` в корень |
| **gemini** | `GEMINI.md` → `AGENTS.md` | `.gemini/settings.json` (`mcpServers`) | ✅ **работает** — `build.sh` делает симлинк |
| **cursor** | `.cursor/rules/*.mdc` | `.cursor/mcp.json` (`mcpServers`) | ⚠️ **требует rulesync** (см. ниже) |
| **copilot** | `.github/copilot-instructions.md` | `.vscode/mcp.json` (**`servers`**) | ⚠️ **требует rulesync** |
| **cline** | `.clinerules/` | `cline_mcp_settings.json` | ⚠️ **требует rulesync** |
| **windsurf** | `.windsurf/rules/*.md` | `~/.codeium/windsurf/mcp_config.json` | ⚠️ **вручную** (rulesync покрывает слабо) |
| **aider** | `CONVENTIONS.md` + `.aider.conf.yml` (`read: AGENTS.md`) | — | ⚠️ **вручную** (одна строка в конфиге) |

## Честно о состоянии
**Из коробки `build.sh` собирает три:** Claude Code, Codex, Gemini CLI. Этого достаточно —
`AGENTS.md` в корне читают многие агенты нативно.

**Для Cursor / Copilot / Cline** нужен генератор `rulesync` (он не входит в toolkit и намеренно
не тянется из сети при сборке):
```bash
npm i -g rulesync && sh build.sh
```
Конфига `.rulesync/` в репозитории пока нет — его нужно создать под свой набор целей
(`rulesync init`). Это открытая задача.

**Windsurf и Aider** подключаются вручную — там буквально один файл:
```bash
# Windsurf
mkdir -p ~/.codeium/windsurf && cp core/mcp/servers.json ~/.codeium/windsurf/mcp_config.json
mkdir -p .windsurf/rules && cp core/AGENTS.md .windsurf/rules/bitrix.md
# Aider — в .aider.conf.yml:
#   read: AGENTS.md
```

Три оси переносимости: **AGENTS.md** (правила) + **SKILL.md** (навыки) + **MCP** (инструменты).
Claude Code НЕ читает AGENTS.md нативно → связка через `@AGENTS.md` в `CLAUDE.md`.
