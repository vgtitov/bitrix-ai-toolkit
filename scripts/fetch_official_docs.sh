#!/bin/sh
# fetch_official_docs.sh — подтянуть ОФИЦИАЛЬНЫЕ источники Битрикс локально,
# чтобы агент искал по первоисточнику (grep), а не «по памяти».
#
# Запуск:  sh scripts/fetch_official_docs.sh          # всё
#          sh scripts/fetch_official_docs.sh docs     # только документация фреймворка
#
# Кладётся в .ai/ (в .gitignore) — это внешние репозитории, не часть toolkit.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/.ai"
WHAT="${1:-all}"
mkdir -p "$DEST"

say() { printf "\n\033[36m[docs] %s\033[0m\n" "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }
have git || { echo "нужен git"; exit 1; }

clone_or_pull() { # url dir name
  url="$1"; dir="$DEST/$2"; name="$3"
  if [ -d "$dir/.git" ]; then
    say "$name — обновляю"; git -C "$dir" pull --ff-only -q 2>/dev/null || echo "  (не удалось обновить, оставляю как есть)"
  else
    say "$name — клонирую"; git clone --depth 1 -q "$url" "$dir" || echo "  ! не удалось склонировать $url"
  fi
  [ -d "$dir" ] && echo "  → $dir"
}

case "$WHAT" in
  docs|all)
    # ОФИЦИАЛЬНАЯ документация Bitrix Framework в Markdown (MIT). ~38 МБ.
    # Внутри: pages/orm, pages/security (sql-injection, xss, csrf-ssrf, sanitizer, cipher…),
    #         pages/performance (caching, query-optimization, composite-site, clustering),
    #         pages/database/sql-tracker, pages/advanced/{debug,logger}
    clone_or_pull https://github.com/bitrix-tools/framework-docs framework-docs "Документация Bitrix Framework (MIT)"
    ;;
esac

case "$WHAT" in
  security|all)
    # Официальные скиллы + детерминированный сканер безопасности модулей (MIT)
    clone_or_pull https://github.com/bitrix-tools/marketplace-security-skills bx-security "Security-скиллы Битрикс (MIT)"
    ;;
esac

case "$WHAT" in
  rest|all)
    # Исходник REST-справки (то же, что отдаёт MCP bitrix-docs) — для офлайн-поиска
    clone_or_pull https://github.com/bitrix-tools/b24-rest-docs b24-rest-docs "REST-справка Битрикс24"
    ;;
esac

say "Готово. Как использовать:"
cat <<'NEXT'
  Агент ищет по первоисточнику вместо догадок, например:
    rg -n "registerTag|TaggedCache"  .ai/framework-docs/pages/performance
    rg -n "setPrivateIp|SSRF"        .ai/framework-docs/pages/security
    rg -n "LoggerFactory"            .ai/framework-docs/pages/advanced
    rg -n "ORM|DataManager"          .ai/framework-docs/pages/orm

  ⚠️ Официальные правила для AI-агентов (bitrix-tools/best-practice) — БЕЗ ЛИЦЕНЗИИ:
     смотреть можно, копировать в свой репозиторий нельзя. Ставится отдельно:
       npx skills add bitrix-tools/best-practice
NEXT
