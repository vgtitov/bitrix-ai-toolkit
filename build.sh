#!/bin/sh
# build.sh — сгенерировать конфиги под разные AI-агенты из ЕДИНОГО ИСТОЧНИКА core/.
# Три оси переносимости: AGENTS.md (правила) + SKILL.md (навыки) + MCP (инструменты).
#
# Стратегия: если установлен rulesync — используем его как движок (20+ агентов). Иначе — минимальный
# фолбэк симлинками/копиями, которого достаточно для Claude Code + AGENTS.md-совместимых (Codex/Cursor/Gemini).
#
# Запуск:  sh build.sh            # собрать всё
#          sh build.sh claude     # только Claude Code
set -eu
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
TARGET="${1:-all}"

link_or_copy() { # src dst  — симлинк, на Windows/без симлинков — копия
  src="$1"; dst="$2"
  mkdir -p "$(dirname "$dst")"
  rm -f "$dst"
  ln -s "$src" "$dst" 2>/dev/null || cp -f "$ROOT/$src" "$dst"
}

build_claude() {
  echo "[claude] CLAUDE.md (@AGENTS.md) + .claude/skills + .claude/settings.json + .mcp.json"
  # AGENTS.md в корне — канон для AGENTS.md-нативных агентов (Codex/Cursor/Gemini/Jules...)
  cp -f core/AGENTS.md AGENTS.md
  # CLAUDE.md импортирует AGENTS.md (Claude Code не читает AGENTS.md нативно) + claude-специфика
  cp -f adapters/claude/CLAUDE.md CLAUDE.md
  # Скиллы
  rm -rf .claude/skills && mkdir -p .claude/skills
  cp -R core/skills/. .claude/skills/
  # Хуки (PostToolUse линтеры)
  mkdir -p .claude
  cp -f adapters/claude/settings.json .claude/settings.json
  # MCP-профиль (ключ mcpServers — как есть)
  cp -f core/mcp/servers.json .mcp.json
}

build_gemini()  { echo "[gemini] GEMINI.md → AGENTS.md";  cp -f core/AGENTS.md AGENTS.md; link_or_copy core/AGENTS.md GEMINI.md; }
build_codex()   { echo "[codex] AGENTS.md (канон, читается нативно)"; cp -f core/AGENTS.md AGENTS.md; }

# Наполнить .rulesync/ из core/ — чтобы rulesync генерил АКТУАЛЬНЫЕ правила, а не заглушку.
sync_rulesync_source() {
  [ -d .rulesync/rules ] || return 0
  # frontmatter сохраняем, тело заменяем содержимым core/AGENTS.md
  {
    sed -n '1,/^---$/p' .rulesync/rules/bitrix.md | head -20
    echo ""
    echo "<!-- ГЕНЕРИРУЕТСЯ из core/AGENTS.md командой build.sh. Правь ИСТОЧНИК, не этот файл. -->"
    echo ""
    cat core/AGENTS.md
  } > .rulesync/rules/bitrix.md.tmp && mv .rulesync/rules/bitrix.md.tmp .rulesync/rules/bitrix.md
  cp -f core/mcp/servers.json .rulesync/.mcp.json 2>/dev/null || true
  echo "[rulesync] источник .rulesync/ обновлён из core/"
}

build_rulesync() {
  sync_rulesync_source
  # ТОЛЬКО если rulesync реально установлен. Раньше здесь был фолбэк на `npx -y rulesync`,
  # который при каждой сборке (в т.ч. в CI) тянул и исполнял сторонний npm-пакет из сети —
  # неожиданная сетевая зависимость и supply-chain-шаг в инструменте, который сам учит гигиене зависимостей.
  if command -v rulesync >/dev/null 2>&1; then
    echo "[rulesync] генерация под Cursor/Copilot/Cline/Windsurf/… (правила+MCP)"
    RS="rulesync"
        # ТОЛЬКО те агенты, которых build.sh не собирает сам.
    # claudecode/geminicli/codexcli НЕ передаём: rulesync затирает наш CLAUDE.md
    # (инлайнит правила вместо связки @AGENTS.md) — проверено, это регрессия.
    $RS generate --targets cursor,copilot,cline 2>/dev/null \
      || echo "[rulesync] пропущено (нет конфига .rulesync/ или сети) — фолбэк уже собран"
  else
    echo "[rulesync] не установлен — собраны Claude/Gemini/Codex (этого достаточно для работы)."
    echo "           Для Cursor/Copilot/Cline/Windsurf: npm i -g rulesync && sh build.sh"
  fi
}

case "$TARGET" in
  claude) build_claude ;;
  gemini) build_gemini ;;
  codex)  build_codex ;;
  all)    build_claude; build_gemini; build_codex; build_rulesync ;;
  *) echo "usage: sh build.sh [all|claude|gemini|codex]"; exit 1 ;;
esac
echo "[ok] build: $TARGET"
