# Адаптеры под разные AI-агенты

Тонкие адаптеры поверх `core/` (единый источник истины). Claude Code — эталон, остальные — маппинг путей/ключей.
Генерация: `sh build.sh` (использует rulesync, если установлен; иначе минимальный фолбэк симлинками).

| Агент | Файл правил | MCP-конфиг (ключ) | Статус |
|---|---|---|---|
| **claude** | `CLAUDE.md` (`@AGENTS.md` + спец) | `.mcp.json` (`mcpServers`) | ✅ эталон (полный) |
| **codex** | `AGENTS.md` (нативно) | `~/.codex/config.toml` (TOML) | ✅ фолбэк (AGENTS.md) |
| **gemini** | `GEMINI.md` → AGENTS.md | `.gemini/settings.json` (`mcpServers`) | ✅ фолбэк (симлинк) |
| **cursor** | `.cursor/rules/*.mdc` | `.cursor/mcp.json` (`mcpServers`) | ⚙️ через rulesync |
| **copilot** | `.github/copilot-instructions.md` | `.vscode/mcp.json` (**`servers`**) | ⚙️ через rulesync |
| **cline** | `.clinerules/` | `cline_mcp_settings.json` | ⚙️ через rulesync |
| **windsurf** | `.windsurf/rules/*.md` | `~/.codeium/windsurf/mcp_config.json` | ⚙️ ручной адаптер |
| **aider** | `CONVENTIONS.md` + `.aider.conf.yml` (`read: AGENTS.md`) | — | ⚙️ ручной адаптер |

Три оси переносимости: **AGENTS.md** (правила) + **SKILL.md** (навыки) + **MCP** (инструменты).
Claude Code НЕ читает AGENTS.md нативно → связка через `@AGENTS.md` в `CLAUDE.md`.
