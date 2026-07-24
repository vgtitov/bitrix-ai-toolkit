#!/bin/sh
# entrypoint контейнера проверок. Уважает опциональность (BITRIX_AI_CHECKS / config/checks.toml).
# Команды:
#   check     — прогнать все доступные проверки по /work (дефолт)
#   guard     — только детектор N+1
#   astgrep   — только структурные анти-паттерны
#   phpstan   — только статанализ (нужен phpstan.neon в проекте)
#   selftest  — самотест toolkit (тесты детектора)
#   sh        — интерактивная оболочка
set -eu
TK="${BITRIX_TOOLKIT_DIR:-/toolkit}"
CMD="${1:-check}"
shift 2>/dev/null || true

mode() { python3 "$TK/scripts/checks_config.py" "$1" 2>/dev/null || echo warn; }
say() { printf "\n\033[36m[checks] %s\033[0m\n" "$1"; }

targets="${*:-.}"
rc_total=0

run_guard() {
  m=$(mode n1_guard); [ "$m" = "off" ] && { echo "  guard: off (пропуск)"; return 0; }
  say "N+1 guard ($m)"
  files=$(find $targets -name '*.php' -not -path '*/vendor/*' -not -path '*/bitrix/*' 2>/dev/null | head -5000)
  [ -z "$files" ] && { echo "  нет .php"; return 0; }
  # shellcheck disable=SC2086
  if ! echo "$files" | xargs python3 "$TK/scripts/bitrix_guard.py"; then
    [ "$m" = "block" ] && rc_total=1 || echo "  (warn — не блокирует)"
  fi
}

run_astgrep() {
  m=$(mode ast_grep); [ "$m" = "off" ] && { echo "  ast-grep: off (пропуск)"; return 0; }
  command -v ast-grep >/dev/null 2>&1 || { echo "  ast-grep не установлен — пропуск"; return 0; }
  say "ast-grep анти-паттерны ($m)"
  ast-grep scan -c "$TK/core/linters/ast-grep/sgconfig.yml" $targets || {
    [ "$m" = "block" ] && rc_total=1 || echo "  (warn — не блокирует)"; }
}

run_phpstan() {
  m=$(mode phpstan); [ "$m" = "off" ] && { echo "  phpstan: off (пропуск)"; return 0; }
  command -v phpstan >/dev/null 2>&1 || { echo "  phpstan не установлен — пропуск"; return 0; }
  [ -f phpstan.neon ] || [ -f phpstan.neon.dist ] || { echo "  нет phpstan.neon в проекте — пропуск"; return 0; }
  say "PHPStan ($m)"
  phpstan analyse --no-progress --error-format=table || {
    [ "$m" = "block" ] && rc_total=1 || echo "  (warn — не блокирует)"; }
}

case "$CMD" in
  check)    run_guard; run_astgrep; run_phpstan ;;
  guard)    run_guard ;;
  astgrep)  run_astgrep ;;
  phpstan)  run_phpstan ;;
  selftest) python3 "$TK/tests/test_bitrix_guard.py" ;;
  sh|bash)  exec /bin/sh ;;
  *) echo "usage: check|guard|astgrep|phpstan|selftest|sh"; exit 2 ;;
esac

exit "$rc_total"
