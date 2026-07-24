#!/bin/sh
# install.sh — идемпотентная автоустановка контура bitrix-ai-toolkit.
# AI-агент может выполнить сам по команде «разверни toolkit». Ставит инструменты, хуки, скиллы, собирает конфиги, самотест.
#
# Запуск:  sh onboard/install.sh              # всё
#          sh onboard/install.sh --no-tools   # без установки инструментов (только хуки+скиллы+сборка)
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INVOKED_FROM="$(pwd)"   # откуда запустили — там может быть проект
prev_arg=""
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
  # Composer dev-зависимости ставятся В ПРОЕКТ, а не в toolkit.
  # ВАЖНО: скрипт делает cd в корень toolkit, где composer.json нет и не будет, —
  # поэтому путь к проекту берём из аргумента или из каталога, откуда скрипт запущен.
  #   sh onboard/install.sh --project /путь/к/проекту
  #   (или просто запусти из корня проекта: sh <toolkit>/onboard/install.sh)
  PROJECT_DIR="$INVOKED_FROM"
  for a in "$@"; do
    case "$prev_arg" in --project) PROJECT_DIR="$a" ;; esac
    prev_arg="$a"
  done
  if have composer && [ -f "$PROJECT_DIR/composer.json" ]; then
    cd "$PROJECT_DIR" || true
    say "Composer dev-зависимости (PHPStan+deprecation, cs-fixer, phpcs, rector, phpunit)"
    composer require --dev --no-interaction \
      phpstan/phpstan phpstan/phpstan-deprecation-rules phpstan/phpstan-strict-rules \
      friendsofphp/php-cs-fixer phpcsstandards/php_codesniffer rector/rector phpunit/phpunit || \
      echo "  ! часть пакетов не поставилась — проверь composer.json проекта"
    cd "$ROOT" || true
  else
    echo "  (composer.json проекта не найден в $PROJECT_DIR — линтеры ставятся В ПРОЕКТ:"
    echo "     запусти из корня проекта или укажи: sh onboard/install.sh --project /путь)"
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

# 4. Конфиги (опциональность проверок + версионный стек) — не перетираем существующие
say "Конфиги"
for pair in "checks.example.toml:checks.toml" "version-stack.example.toml:version-stack.toml"; do
  src="config/${pair%%:*}"; dst="config/${pair##*:}"
  if [ -f "$dst" ]; then
    echo "  = $dst уже есть — не трогаю"
  elif [ -f "$src" ]; then
    cp "$src" "$dst" && echo "  + $dst (из образца; настрой под себя)"
  fi
done
mkdir -p config/local && echo "  = config/local/ — слой компании (в .gitignore, см. docs/LOCALIZATION.md)"
echo "  режим проверок сейчас: $(python3 scripts/checks_config.py default 2>/dev/null || echo warn)  (off|warn|block)"

# 5. Сборка конфигов под агентов
say "Сборка конфигов (build.sh)"
sh build.sh >/dev/null 2>&1 && echo "  CLAUDE.md/AGENTS.md/.mcp.json/.claude готовы" || echo "  ! build.sh с ошибкой"

# 6. Самотест
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

say "Готово. Дальше (подробно — docs/SETUP.md):"
cat <<'NEXT'
  ОБЯЗАТЕЛЬНО в целевом проекте:
  1. config/version-stack.toml — опиши СВОЙ проект:
       [php].version                — 8.2/8.3
       [bitrix].core_path           — путь к РЕАЛЬНОМУ ядру (его видит PHPStan → ловит «метода нет в версии»)
       [bitrix].core_modified=true  — если ядро ПРАВЛЕНО (references/custom-core.md)
       [[custom_layers]]            — если есть СВОЙ ФРЕЙМВОРК/namespace подрядчика поверх Битрикс
                                      (references/custom-framework.md; поиск идёт в ТРЁХ слоях)
  2. Сгенерируй конфиг под реальный проект (НЕ копируй образец руками — он ссылается на пути,
     которых у тебя может не быть, и PHPStan упадёт до анализа):
       cd <корень проекта> && python3 <toolkit>/scripts/init_project.py --dry-run   # посмотреть
       cd <корень проекта> && python3 <toolkit>/scripts/init_project.py             # записать phpstan.neon
     Скрипт сам находит ядро, кастомные слои и свой код; включает только существующие пути.
     Остальные конфиги копируются как есть: core/linters/{phpcs.xml.dist, .php-cs-fixer.dist.php, rector.php}
  3. composer require --dev phpstan/extension-installer phpstan/phpstan \
        phpstan/phpstan-deprecation-rules phpstan/phpstan-strict-rules
     (extension-installer подключает расширения САМ — вручную includes не прописывать)
  4. Справка: claude mcp add --transport http bitrix-docs https://mcp-dev.bitrix24.com/mcp

  РЕЖИМ ПРОВЕРОК (config/checks.toml или env BITRIX_AI_CHECKS):
     off   — не проверять (AI пишет по знаниям скилла quality-standards.md)
     warn  — ДЕФОЛТ: показать проблемы, НЕ блокировать (AI сообщает и предлагает фикс)
     block — строгий гейт: AI обязан починить до завершения; pre-commit останавливает коммит

  СИЛЬНО РЕКОМЕНДУЕТСЯ (агент отвечает по первоисточнику, а не по памяти):
  0. sh scripts/fetch_official_docs.sh      # официальная дока Битрикс (MIT) в .ai/framework-docs
                                            # затем: rg -n "TaggedCache" .ai/framework-docs/pages/performance

  ОПЦИОНАЛЬНО:
  3b. Доп. проверки (все опциональны, ставятся в проект):
     composer require --dev deptrac/deptrac                       # контроль слоёв (домен не знает Битрикс)
     composer require --dev phpstan/extension-installer spaze/phpstan-disallowed-calls
     composer require --dev roave/security-advisories:dev-latest  # уязвимые версии не установятся
     composer audit --locked                                      # встроено в Composer 2.4+
     конфиги: core/linters/{deptrac.yaml, disallowed-calls.neon}
  4. Language Server агенту (навигация+диагностики): docs/language-server.md
     npm i -g intelephense && claude mcp add php-lsp -- mcp-language-server --workspace "$PWD" --lsp intelephense -- --stdio
  5. Проверки в Docker (без локальной установки PHP): docker/ — docker compose -f docker/docker-compose.yml run --rm checks
  6. Интеграции Jira/Confluence (креды в config/local/.env): docs/integrations.md
  7. Настройки компании отдельным репо: docs/LOCALIZATION.md (config/local/)
  8. PhpStorm 2025.2+: Settings → Tools → MCP Server (мост IDE для агента).
  9. Перезапусти агента и подтверди MCP.
NEXT
