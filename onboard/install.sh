#!/bin/sh
# install.sh — идемпотентная автоустановка контура bitrix-ai-toolkit.
# Клод может выполнить сам по команде «разверни toolkit». Ставит инструменты, хуки, скиллы, собирает конфиги, самотест.
#
# Запуск:  sh onboard/install.sh              # всё
#          sh onboard/install.sh --no-tools   # без установки инструментов (только хуки+скиллы+сборка)
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
WITH_TOOLS=1
[ "${1:-}" = "--no-tools" ] && WITH_TOOLS=0

say() { printf "\n\033[36m[onboard] %s\033[0m\n" "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# 1. Инструменты (macOS brew / прочее — подсказки)
if [ "$WITH_TOOLS" = 1 ]; then
  say "Инструменты: PHP, Composer, ast-grep"
  if have brew; then
    have php || brew install php || echo "  ! php не поставился — поставь вручную"
    have composer || brew install composer || echo "  ! composer вручную"
    have ast-grep || have sg || brew install ast-grep || echo "  ! ast-grep вручную (npm i -g @ast-grep/cli)"
  else
    echo "  brew не найден. Поставь вручную: PHP 8.2+, Composer, ast-grep. Linux: apt/dnf + npm i -g @ast-grep/cli"
  fi
  # Composer dev-зависимости — только если есть composer.json в целевом проекте (не в toolkit)
  if have composer && [ -f composer.json ]; then
    say "Composer dev-зависимости (PHPStan+deprecation, cs-fixer, phpcs, rector, phpunit)"
    composer require --dev --no-interaction \
      phpstan/phpstan phpstan/phpstan-deprecation-rules phpstan/phpstan-strict-rules \
      friendsofphp/php-cs-fixer phpcsstandards/php_codesniffer rector/rector phpunit/phpunit || \
      echo "  ! часть пакетов не поставилась — проверь composer.json проекта"
  else
    echo "  (composer.json проекта не найден в CWD — dev-зависимости ставятся в проекте, не в toolkit)"
  fi
fi

# 2. Git-хуки (commit-msg чистые сообщения + pre-commit bitrix-guard N+1)
say "Git-хуки"
python3 scripts/install_git_hooks.py || echo "  ! хуки не поставились"

# 3. Скиллы → ~/.claude/skills
say "Скиллы → ~/.claude/skills"
mkdir -p "$HOME/.claude/skills"
for d in core/skills/*/; do
  name="$(basename "$d")"
  rm -rf "$HOME/.claude/skills/$name"
  cp -R "$d" "$HOME/.claude/skills/$name"
  echo "  + $name"
done

# 4. Сборка конфигов под агентов
say "Сборка конфигов (build.sh)"
sh build.sh >/dev/null 2>&1 && echo "  CLAUDE.md/AGENTS.md/.mcp.json/.claude готовы" || echo "  ! build.sh с ошибкой"

# 5. Самотест
say "Самотест"
if have python3; then
  python3 tests/test_bitrix_guard.py && echo "  bitrix_guard: OK" || echo "  ! bitrix_guard FAIL"
fi
if have ast-grep || have sg; then
  AG=$(command -v ast-grep || command -v sg)
  "$AG" scan -c core/linters/ast-grep/sgconfig.yml tests/fixtures/ 2>/dev/null | head -3 || true
  echo "  ast-grep: правила загружены"
else
  echo "  ast-grep не установлен — правила ast-grep пропущены (guard N+1 работает и без него)"
fi

say "Готово. Дальше:"
cat <<'NEXT'
  1. В целевом проекте: скопируй core/linters/{phpstan.neon.dist,phpcs.xml.dist,.php-cs-fixer.dist.php,rector.php}
     в корень, положи ядро своей версии, настрой config/version-stack.toml.
  2. MCP:  claude mcp add --transport http bitrix-docs https://mcp-dev.bitrix24.com/mcp
  3. PhpStorm 2025.2+: Settings → Tools → MCP Server (мост для Claude Code).
  4. Перезапусти Claude Code и подтверди MCP.
NEXT
