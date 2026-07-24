# Воспроизводимая среда проверок Битрикс-кода: PHP 8.3 + линтеры + ast-grep + toolkit.
# Локально:      docker build -t bitrix-ai-toolkit:checks -f docker/Dockerfile .
#                docker run --rm -v "$PWD":/work -w /work bitrix-ai-toolkit:checks check
# Центрально:    docker/docker-compose.yml (общий сервис проверок для команды / CI)
#
# Смысл: разработчику НЕ обязательно ставить PHP/линтеры локально — можно гонять проверки в контейнере.
# Toolkit при этом работает и без Docker (локальный путь — основной).
FROM php:8.3-cli-alpine

RUN apk add --no-cache git bash python3 nodejs npm unzip libzip-dev \
    && docker-php-ext-install zip \
    && curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer \
    && npm install -g @ast-grep/cli \
    && rm -rf /var/cache/apk/*

# Линтеры — глобально, чтобы не зависеть от composer.json проекта
RUN composer global require --no-interaction \
        phpstan/phpstan phpstan/phpstan-deprecation-rules phpstan/phpstan-strict-rules \
        friendsofphp/php-cs-fixer phpcsstandards/php_codesniffer rector/rector \
    && ln -s /root/.composer/vendor/bin/* /usr/local/bin/ 2>/dev/null || true
ENV PATH="/root/.composer/vendor/bin:${PATH}"

# Сам toolkit (правила, ast-grep-правила, guard, конфиги)
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
