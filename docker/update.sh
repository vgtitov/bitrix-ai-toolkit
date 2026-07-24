#!/bin/sh
# update.sh — актуализация Docker-слоя и данных, которые устаревают.
#
# Что устаревает и как обновляется:
#   1. Образ проверок (версии PHP/PHPStan/CS-Fixer/Rector/ast-grep) → пересборка с --pull
#   2. Сам toolkit внутри образа (core/, scripts/, config/) → та же пересборка (COPY на этапе build)
#   3. Официальная документация Битрикс (.ai/framework-docs) → git pull, ЛОКАЛЬНО (в образ не зашита,
#      чтобы не устаревала вместе с ним; нужна агенту, а не контейнеру)
#
# Запуск:  sh docker/update.sh            # всё
#          sh docker/update.sh image      # только образ
#          sh docker/update.sh docs       # только документация
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
WHAT="${1:-all}"
case "$WHAT" in
  image|docs|all) ;;
  *) echo "неизвестный аргумент: $WHAT"; echo "usage: sh docker/update.sh [all|image|docs]"; exit 2 ;;
esac
say() { printf "\n\033[36m[update] %s\033[0m\n" "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

case "$WHAT" in
  image|all)
    if have docker; then
      say "Пересборка образа проверок (--pull: свежая база + свежие версии линтеров)"
      docker build --pull -t bitrix-ai-toolkit:checks -f docker/Dockerfile . \
        && echo "  ✓ bitrix-ai-toolkit:checks обновлён" \
        || echo "  ! сборка не удалась"
      say "Версии инструментов в новом образе"
      docker run --rm --entrypoint sh bitrix-ai-toolkit:checks -c \
        'php -v|head -1; phpstan --version; php-cs-fixer --version|head -1; phpcs --version|head -1; rector --version|head -1; ast-grep --version' \
        2>/dev/null || true
      say "Самотест обновлённого образа"
      docker run --rm bitrix-ai-toolkit:checks selftest 2>&1 | tail -3 || echo "  ! самотест не прошёл"
    else
      echo "  docker не установлен — пропуск"
    fi
    ;;
esac

case "$WHAT" in
  docs|all)
    say "Официальная документация Битрикс (локально, вне образа)"
    sh scripts/fetch_official_docs.sh docs 2>&1 | grep -E "обновляю|клонирую|→|!" || true
    ;;
esac

say "Готово"
cat <<'NEXT'
  Рекомендуемая периодичность:
    образ         — раз в месяц или когда нужен свежий PHPStan/Rector (docker/update.sh image)
    документация  — раз в неделю/перед крупной задачей   (docker/update.sh docs)

  В CI образ не обновляют «по расписанию» — там он собирается из Dockerfile на каждый прогон,
  поэтому достаточно держать Dockerfile актуальным.
NEXT
