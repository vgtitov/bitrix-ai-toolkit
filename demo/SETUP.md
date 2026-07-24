# Демо Claude Code на PHP/Битрикс — развёртывание за вечер

**Формат демо:** записанный прогон терминала (GIF/видео) или живой запуск — на выбор.

**Главный принцип:** для показа «Claude Code читает / правит / линтит / объясняет код» **запущенный сайт Битрикс не нужен.** Нужен: код Битрикса (open-source репо) + линтеры (PHPStan/phpcs/php-cs-fixer) + официальная документация через MCP. Это быстро, честно и стабильно в кадре.

> ⚠️ Полный Битрикс (VMBitrix / bitrixdock / BitrixSetup) на Apple Silicon (ARM) — плохая ставка под дедлайн: образы собраны под amd64, стартуют через QEMU медленно и периодически падают. Это отдельная сессия, не под завтра.

---

## Шаг 1. PHP-среда (нативно, ARM, ~15–20 мин)

```bash
brew install php composer          # PHP 8.3 arm64 + Composer
php -v                             # проверка

cd /path/to/demo-project
composer require --dev phpstan/phpstan \
                       friendsofphp/php-cs-fixer \
                       squizlabs/php_codesniffer   # phpcs + phpcbf
vendor/bin/phpstan --version && vendor/bin/php-cs-fixer --version && vendor/bin/phpcs --version
```

`phpstan.neon` в корне:
```neon
parameters:
    level: 5
    paths:
        - src
    # excludePaths: ['*/bitrix/*']   # ядро Битрикс не анализируем
```

## Шаг 2. Кодовая база для демо (open-source Битрикс, ~15 мин)

| Репозиторий | ⭐ | Роль в демо |
|---|---|---|
| `regiomedia/bitrix-project` | 242 | **Основная база** — composer готов, PHPStan заводится сразу |
| `Mediahero/bitrix-clear-upload` | 97 | **Крупный план бага/уязвимости** — файловые операции → естественный path-traversal кейс |
| `bitrix-expert/bbc` | 101 | «Правим компонент по стандарту» |
| `notamedia/console-jedi` | 88 | «Объясни архитектуру» |
| каталог: `awesomebitrix/awesome-bitrix` | 300 | Слайд «где брать ещё» |

```bash
git clone https://github.com/regiomedia/bitrix-project.git
git clone https://github.com/Mediahero/bitrix-clear-upload.git
```
В один файл заранее заложить баг + уязвимость (path traversal / SQL-конкатенация / незакрытый ресурс).

## Шаг 3. Официальный Bitrix MCP (документация REST, ~5 мин)

```bash
claude mcp add --transport http bitrix https://mcp-dev.bitrix24.com/mcp
# в сессии:  /mcp   → убедиться, что сервер connected
```
Официальный вендорский сервер (Streamable HTTP, без авторизации). Инструкция: https://apidocs.bitrix24.com/ai-tools/mcp.html
> Это документация по **REST API Битрикс24**, не по PHP-ядру. Для «найди метод/параметр в доке» подходит идеально; для ядра `bitrix/modules` — объяснение по локальным исходникам.

## Шаг 4. Запись прогона (~20–30 мин)

```bash
brew install asciinema agg
asciinema rec demo.cast            # выход: Ctrl-D
agg --font-size 20 --speed 1.5 demo.cast demo.gif
```
Живой кадр со спиннером — `Shift-Cmd-5` (запись области → `.mov`). Конвертация `.mov`→GIF/mp4 — ffmpeg (уже стоит).

## Готовый визуал для слайдов (заставки)
- Официальная demo.gif: https://github.com/anthropics/claude-code/raw/main/demo.gif
- Продукт: https://claude.com/product/claude-code · Доки: https://code.claude.com/docs/en/overview
