# Адаптеры под разные AI-агенты

Тонкие адаптеры поверх `core/` (единый источник истины). Claude Code — эталон, остальные — маппинг путей/ключей.
Генерация: `sh build.sh` (использует rulesync, если установлен; иначе минимальный фолбэк симлинками).

| Агент | Файл правил | MCP-конфиг (ключ) | Статус |
|---|---|---|---|
| **claude** | `CLAUDE.md` (`@AGENTS.md` + спец) | `.mcp.json` (`mcpServers`) | ✅ **работает из коробки** (эталон) |
| **codex** | `AGENTS.md` (читает нативно) | `~/.codex/config.toml` (TOML) | ✅ **работает** — `build.sh` кладёт `AGENTS.md` в корень |
| **gemini** | `GEMINI.md` → `AGENTS.md` | `.gemini/settings.json` (`mcpServers`) | ✅ **работает** — `build.sh` делает симлинк |
| **cursor** | `.cursor/rules/*.mdc` | `.cursor/mcp.json` (`mcpServers`) | ✅ **работает** (нужен rulesync, см. ниже) |
| **copilot** | `.github/copilot-instructions.md` | `.vscode/mcp.json` (**`servers`**) | ✅ **работает** (нужен rulesync) |
| **cline** | `.clinerules/` | `cline_mcp_settings.json` | ✅ **работает** (нужен rulesync) |
| **windsurf** | `.windsurf/rules/*.md` | `~/.codeium/windsurf/mcp_config.json` | ⚠️ **вручную** (rulesync покрывает слабо) |
| **aider** | `CONVENTIONS.md` + `.aider.conf.yml` (`read: AGENTS.md`) | — | ⚠️ **вручную** (одна строка в конфиге) |

## Честно о состоянии
**Из коробки `build.sh` собирает три:** Claude Code, Codex, Gemini CLI. Этого достаточно —
`AGENTS.md` в корне читают многие агенты нативно.

**Для Cursor / Copilot / Cline** нужен генератор `rulesync` (не входит в toolkit и намеренно
не тянется из сети при сборке — это был бы скрытый supply-chain-шаг):
```bash
npm i -g rulesync && sh build.sh
```
Конфиг `.rulesync/` в репозитории **есть и наполняется автоматически** из `core/AGENTS.md` при каждой
сборке — править его руками не нужно. Проверено на rulesync 14.2: генерируются
`.cursor/rules/bitrix.mdc` и `.github/copilot-instructions.md`.

> ⚠️ `build.sh` намеренно НЕ передаёт rulesync цели `claudecode/geminicli/codexcli`: он затирает наш
> `CLAUDE.md`, инлайня правила вместо связки `@AGENTS.md`. Эти три агента собирает сам `build.sh`.

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


## Почему `core/skills/` и `.claude/skills/` дублируются

Файлы совпадают побайтно, и это **осознанно**, а не недосмотр:

- `core/skills/` — **источник истины**, его правят;
- `.claude/skills/` — **сгенерированная копия**, чтобы репозиторий работал сразу после `git clone`,
  без обязательного прогона `build.sh`.

Почему не симлинки: они требуют Developer Mode или прав администратора на Windows, а Windows —
целевая платформа (значительная часть Битрикс-разработчиков). Копия работает везде.

Риск расхождения закрыт в CI: шаг «Сгенерированное соответствует core/» делает `git diff --exit-code`
и падает, если кто-то поправил сгенерированное вместо источника.

**Правило:** правишь `core/` → `sh build.sh` → коммитишь обе версии.
