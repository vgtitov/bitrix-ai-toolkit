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

# Список .php для проверки. Уважает профиль «грязный легаси» ([scope].changed_only):
# только изменённые файлы, если это git-репозиторий; иначе — обход scope.
php_files() {
  if [ -d .git ] && python3 "$TK/scripts/changed_files.py" --ext php 2>/dev/null | head -1 | grep -q .; then
    python3 "$TK/scripts/changed_files.py" --ext php 2>/dev/null
  elif [ -d .git ] && python3 "$TK/scripts/changed_files.py" --ext php >/dev/null 2>&1; then
    :   # git есть, изменений нет → ничего не проверяем (легаси не трогаем)
  else
    find $targets -name '*.php' -not -path '*/vendor/*' -not -path '*/bitrix/*' 2>/dev/null | head -5000
  fi
}

run_guard() {
  m=$(mode n1_guard); [ "$m" = "off" ] && { echo "  guard: off (пропуск)"; return 0; }
  say "N+1 guard ($m)"
  files=$(php_files)
  [ -z "$files" ] && { echo "  нет изменённых .php (профиль «только изменённое») — пропуск"; return 0; }
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

run_phpmd() {
  m=$(mode phpmd); [ "$m" = "off" ] && { echo "  phpmd: off (пропуск)"; return 0; }
  command -v phpmd >/dev/null 2>&1 || { echo "  phpmd не установлен — пропуск"; return 0; }
  say "PHPMD: сложность и размер ($m)"
  phpmd $targets text "$TK/core/linters/phpmd.xml" || {
    [ "$m" = "block" ] && rc_total=1 || echo "  (warn — не блокирует)"; }
}

run_jscpd() {
  m=$(mode jscpd); [ "$m" = "off" ] && { echo "  jscpd: off (пропуск)"; return 0; }
  command -v jscpd >/dev/null 2>&1 || { echo "  jscpd не установлен — пропуск"; return 0; }
  say "jscpd: копипаста ($m)"
  jscpd -c "$TK/core/linters/jscpd.json" $targets || {
    [ "$m" = "block" ] && rc_total=1 || echo "  (warn — не блокирует)"; }
}

case "$CMD" in
  check)    run_guard; run_astgrep; run_phpstan ;;
  full)     run_guard; run_astgrep; run_phpstan; run_phpmd; run_jscpd ;;
  guard)    run_guard ;;
  astgrep)  run_astgrep ;;
  phpstan)  run_phpstan ;;
  phpmd)    run_phpmd ;;
  jscpd)    run_jscpd ;;
  selftest) python3 "$TK/tests/test_bitrix_guard.py" ;;
  sh|bash)  exec /bin/sh ;;
  *) echo "usage: check|full|guard|astgrep|phpstan|phpmd|jscpd|selftest|sh"; exit 2 ;;
esac

exit "$rc_total"
