# Воспроизводимая среда проверок Битрикс-кода: PHP 8.3 + линтеры + ast-grep + toolkit.
# Локально:      docker build -t bitrix-ai-toolkit:checks -f docker/Dockerfile .
#                docker run --rm -v "$PWD":/work -w /work bitrix-ai-toolkit:checks check
# Централизованно: docker/docker-compose.yml (общий сервис проверок для команды / CI)
#
# Смысл: не обязательно ставить PHP/линтеры локально — можно гонять проверки в контейнере.
# Toolkit при этом работает и без Docker (локальный путь — основной).
#
# База — Debian (glibc), НЕ Alpine: у @ast-grep/cli нет нативного бинарника под musl
# (проверено сборкой: "Failed to locate @ast-grep/cli native binary" на alpine).
FROM php:8.3-cli

RUN apt-get update && apt-get install -y --no-install-recommends \
        git unzip libzip-dev python3 curl ca-certificates gnupg \
    && docker-php-ext-install zip \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer \
    && rm -rf /var/lib/apt/lists/*

# ast-grep — структурные анти-паттерны.
# ВАЖНО: префикс npm переводим на /usr/local. По умолчанию (nodesource) он /usr, а в Debian уже есть
# /usr/bin/sg (симлинк на newgrp из shadow) → npm падает с EEXIST при создании своего симлинка `sg`.
# Проверено сборкой; в /usr/local/bin коллизии нет и системная утилита не затирается.
# Шаг НЕ блокирующий: не встал → контейнер всё равно рабочий, entrypoint пропустит ast-grep.
RUN npm config set prefix /usr/local \
    && npm install -g @ast-grep/cli \
    || echo "[warn] ast-grep не установлен — проверки ast-grep будут пропущены"

# jscpd — поиск копипасты (живая замена заброшенному phpcpd). Тоже неблокирующий шаг.
RUN npm install -g jscpd || echo "[warn] jscpd не установлен — проверка копипасты будет пропущена"

# Линтеры глобально, чтобы не зависеть от composer.json проекта
RUN composer global require --no-interaction --no-progress \
        phpstan/phpstan phpstan/phpstan-deprecation-rules phpstan/phpstan-strict-rules phpmd/phpmd \
        friendsofphp/php-cs-fixer phpcsstandards/php_codesniffer rector/rector \
    && composer clear-cache
ENV PATH="/root/.composer/vendor/bin:${PATH}"

# Сам toolkit (правила, ast-grep-правила, guard, конфиги, тесты)
COPY core/ /toolkit/core/
COPY scripts/ /toolkit/scripts/
COPY config/ /toolkit/config/
COPY tests/ /toolkit/tests/
ENV BITRIX_TOOLKIT_DIR=/toolkit

COPY docker/entrypoint.sh /usr/local/bin/entrypoint
RUN chmod +x /usr/local/bin/entrypoint

WORKDIR /work
ENTRYPOINT ["entrypoint"]
CMD ["check"]
