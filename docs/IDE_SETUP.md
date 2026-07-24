# Настройка IDE и MCP — что агент делает сам, что руками

Инструкция построена так, чтобы **AI-агент выполнил максимум сам**, а человеку остались только шаги, до которых
агент физически не дотягивается (GUI-настройки, установка плагинов из Marketplace, лицензии).

---

## Шаг 0. Определить, какая IDE используется
Агент выполняет сам:
```bash
ls /Applications | grep -iE 'PhpStorm|Visual Studio Code|Cursor|Windsurf|Zed'   # macOS
command -v code cursor windsurf zed phpstorm 2>/dev/null                        # CLI-лаунчеры
ls ~/Library/Application\ Support/ | grep -iE 'Code|Cursor|JetBrains'           # macOS, конфиги
# Windows:  Get-ChildItem "$env:LOCALAPPDATA\Programs" | Select-String -Pattern 'Code|Cursor|JetBrains'
# Linux:    ls ~/.config | grep -iE 'Code|Cursor|JetBrains'
```
Дальше — раздел под найденную IDE. Если IDE не найдена — терминальный режим (раздел «Любой терминал») работает всегда.

---

## PhpStorm / IntelliJ (лидер среди PHP — 68%)

### ✅ Что агент делает сам
```bash
# 1. Проверить версию (MCP Server встроен с 2025.2)
ls -d /Applications/PhpStorm*.app 2>/dev/null
defaults read /Applications/PhpStorm.app/Contents/Info.plist CFBundleShortVersionString 2>/dev/null

# 2. Прописать проектные MCP-серверы (агент пишет файл сам)
#    .mcp.json уже генерируется build.sh — общий для Claude Code
sh build.sh

# 3. Проверить, что порт MCP-сервера IDE слушается (после включения в GUI)
lsof -iTCP -sTCP:LISTEN -n -P 2>/dev/null | grep -i java | head
```

### 🖐 Что нужно сделать руками (GUI, агент не дотянется)
**Включить встроенный MCP-сервер PhpStorm:**
1. Открыть PhpStorm → **Settings** (`⌘,` на macOS / `Ctrl+Alt+S` на Windows).
2. Слева: **Tools → MCP Server**.
3. Поставить галочку **Enable MCP Server**.
4. Нажать **Apply / OK**. IDE поднимет endpoint и покажет его адрес.
5. Если предложит зарегистрировать клиента — выбрать **Claude Code** (кнопка авто-регистрации).

**Плагин Bitrix (сильно облегчает жизнь):**
1. **Settings → Plugins → Marketplace** → искать «Bitrix» → **Install** → перезапустить IDE.

**Чтобы IDE видела ядро Битрикс (иначе автодополнение слепое):**
1. **Settings → PHP** → секция **Include Path** → `+` → указать путь к `bitrix/modules` проекта.
   *(Либо, если ядро подключено composer-пакетом — оно подхватится из `vendor/` само.)*
2. Там же **PHP → PHP language level** — выставить версию из `config/version-stack.toml`.

**Если версия PhpStorm < 2025.2** (встроенного MCP нет):
1. **Settings → Plugins → Marketplace** → «MCP Server» → Install.
2. Затем агент выполнит сам: `claude mcp add jetbrains -- npx -y @jetbrains/mcp-proxy`
3. Если нужны внешние подключения: **Settings → Build, Execution, Deployment → Debugger** →
   галочка **Can accept external connections**.

---

## VS Code (самый массовый — 76%)

### ✅ Что агент делает сам
```bash
# 1. Расширение Claude Code (если есть CLI `code`)
code --install-extension anthropic.claude-code 2>/dev/null || echo "поставь из Marketplace вручную"

# 2. Полезное для PHP
code --install-extension bmewburn.vscode-intelephense-client 2>/dev/null

# 3. Проектный MCP-конфиг — агент создаёт файл сам.
#    ВНИМАНИЕ: у VS Code корневой ключ "servers", а не "mcpServers" (в отличие от Claude/Cursor).
mkdir -p .vscode && cat > .vscode/mcp.json <<'JSON'
{
  "servers": {
    "bitrix-docs": { "type": "http", "url": "https://mcp-dev.bitrix24.com/mcp" }
  }
}
JSON

# 4. Указать Intelephense на ядро Битрикс (агент правит settings.json проекта)
mkdir -p .vscode && python3 - <<'PY'
import json, os
p = ".vscode/settings.json"
cfg = json.load(open(p)) if os.path.exists(p) else {}
cfg.setdefault("intelephense.environment.includePaths", [])
for path in ["bitrix/modules", "vendor/bitrix-toolkit/bitrix-ci"]:
    if path not in cfg["intelephense.environment.includePaths"]:
        cfg["intelephense.environment.includePaths"].append(path)
cfg["intelephense.environment.phpVersion"] = "8.3"   # из config/version-stack.toml
json.dump(cfg, open(p, "w"), indent=2, ensure_ascii=False)
print("обновлён", p)
PY
```

### 🖐 Что руками
1. Если нет CLI `code`: открыть VS Code → **⌘⇧P** → «Shell Command: Install 'code' command in PATH».
2. Если расширение не встало из CLI: **Extensions** (`⌘⇧X`) → искать «Claude Code» → **Install**.
3. Перезагрузить окно: **⌘⇧P** → «Developer: Reload Window».

---

## Cursor / Windsurf

### ✅ Агент делает сам
```bash
# Cursor — ключ "mcpServers" (как у Claude)
mkdir -p .cursor && cp core/mcp/servers.json .cursor/mcp.json

# Windsurf — глобальный конфиг
mkdir -p ~/.codeium/windsurf && cp core/mcp/servers.json ~/.codeium/windsurf/mcp_config.json

# Правила из общего ядра
sh build.sh          # раскладывает AGENTS.md; для Cursor — .cursor/rules через rulesync
```
### 🖐 Руками
- Cursor: **Settings → MCP** — убедиться, что серверы подхватились (зелёный статус).
- Windsurf: **Settings → Cascade → MCP Servers** — то же.

---

## Zed
Агент: `cp core/mcp/servers.json ~/.config/zed/mcp.json` (ключ `context_servers` — при необходимости
переименовать). Руками: **Settings → Assistant → внешние агенты (ACP)** — выбрать Claude Code.

---

## Любой терминал (vim/neovim/без IDE) — работает всегда
Ничего в редактор ставить не надо:
```bash
claude                                   # агент в терминале
claude mcp add --transport http bitrix-docs https://mcp-dev.bitrix24.com/mcp
claude mcp list                          # проверка
```

---

## MCP-серверы: что подключаем (агент выполняет сам)
```bash
# 1. Официальная справка REST Битрикс24 (hosted, без ключей)
claude mcp add --transport http bitrix-docs https://mcp-dev.bitrix24.com/mcp

# 2. Символьная навигация + диагностики по проекту
claude mcp add serena -- uvx --from git+https://github.com/oraios/serena \
  serena start-mcp-server --context ide-assistant --project "$(pwd)"

# 3. (опц.) Language Server агенту — go-to-def/hover/диагностики
npm install -g intelephense
go install github.com/isaacphi/mcp-language-server@latest
claude mcp add php-lsp -- mcp-language-server --workspace "$(pwd)" --lsp intelephense -- --stdio

# Проверка
claude mcp list          # или в сессии:  /mcp
```
> Ключ MCP-конфига различается: Claude/Cursor/Gemini — `mcpServers`; **VS Code — `servers`**; Codex — TOML
> (`~/.codex/config.toml`); Continue — массив. `build.sh` раскладывает основные варианты.

---

## Чек-лист «всё встало»
```bash
claude mcp list                                    # серверы connected
python3 tests/test_bitrix_guard.py                 # 4/4
sh build.sh && head -1 CLAUDE.md                   # @AGENTS.md
python3 scripts/checks_config.py n1_guard          # off|warn|block
ls .ai/framework-docs/pages >/dev/null && echo "официальная дока на месте"
```
В IDE: открыть любой PHP-файл проекта — автодополнение по `\Bitrix\Main\` должно работать. Не работает →
не подключено ядро (см. Include Path / includePaths выше).

---

## Если что-то не подключается
1. **MCP «connected», но инструментов нет** — перезапустить агента (MCP подхватывается на старте сессии).
2. **PhpStorm MCP не виден** — версия < 2025.2 (нужен плагин) либо IDE не запущена/проект не открыт.
3. **Intelephense не видит ядро** — не сгенерирован autoload: `composer dump-autoload -o`, и проверить includePaths.
4. **Serena долго индексирует** — ограничить область: `--project` на `/local`, а не на весь `/bitrix`.
5. **Проверки не запускаются** — посмотреть режим: `python3 scripts/checks_config.py n1_guard` (возможно `off`).
