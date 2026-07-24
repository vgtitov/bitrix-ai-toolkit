# Docker-слой — воспроизводимая среда проверок

**Опционален.** Локальный путь (`onboard/install.sh`) работает без Docker. Контейнер нужен, когда:
- не хочешь ставить PHP/линтеры локально;
- нужна **единая версия инструментов** у всех разработчиков и в CI;
- проверки гоняются на общем сервере/раннере.

## Быстрый старт
```bash
docker build -t bitrix-ai-toolkit:checks -f docker/Dockerfile .

# весь проект (из корня проекта Битрикс)
docker run --rm -v "$PWD":/work -w /work bitrix-ai-toolkit:checks check
# или через compose
docker compose -f docker/docker-compose.yml run --rm checks
```

## Команды контейнера
| Команда | Что делает |
|---|---|
| `check` (по умолчанию) | все доступные проверки: N+1 guard → ast-grep → PHPStan |
| `guard` | только детектор N+1 (запрос в цикле) |
| `astgrep` | только структурные анти-паттерны |
| `phpstan` | только статанализ (нужен `phpstan.neon` в проекте) |
| `selftest` | самотест toolkit (тесты детектора) |
| `sh` | интерактивная оболочка внутри образа |

## Режимы проверок работают и в контейнере
```bash
docker run --rm -e BITRIX_AI_CHECKS=block -v "$PWD":/work -w /work bitrix-ai-toolkit:checks guard  # exit 1 при находках
docker run --rm -e BITRIX_AI_CHECKS=warn  ...   # покажет, не заблокирует (дефолт)
docker run --rm -e BITRIX_AI_CHECKS=off   ...   # пропустит
```
Свой конфиг: смонтируй `config/checks.toml` в `/toolkit/config/checks.toml` (см. compose).

## Что в образе
PHP 8.3 · Composer · **PHPStan** (+deprecation, +strict) · **PHP-CS-Fixer** · **PHP_CodeSniffer** · **Rector** ·
**ast-grep** · сам toolkit (`core/`, `scripts/`, `config/`, `tests/`).
Проверено сборкой: PHP 8.3.32, PHPStan 2.2.5, CS-Fixer 3.95, PHPCS 4.0.1, Rector 2.5.7, ast-grep 0.45.0.

## Актуализация (что устаревает)
```bash
sh docker/update.sh          # образ (--pull) + документация + самотест
sh docker/update.sh image    # только образ
sh docker/update.sh docs     # только официальная документация Битрикс
```
- **Образ** — версии линтеров фиксируются на момент сборки → пересобирать раз в месяц или по нужде.
- **Официальная документация** (`.ai/framework-docs`) — **не в образе намеренно**: она нужна AI-агенту (локально),
  а не контейнеру проверок, и обновляется отдельно, чтобы не устаревать вместе с образом.

## Грабли (проверено на практике)
1. **Alpine не подходит** — у `@ast-grep/cli` нет нативного бинарника под musl. База — Debian (`php:8.3-cli`).
2. **`npm prefix`** — в Debian уже есть `/usr/bin/sg` (из `shadow`), а ast-grep ставит свой симлинк `sg` → `EEXIST`.
   Решение: `npm config set prefix /usr/local` (системная утилита не затирается).
3. **Монтирование в Colima** — по умолчанию проброшен `$HOME` и несколько путей; каталог вне `$HOME`
   (например `/tmp/...`) в контейнере будет **пустым**. В Docker Desktop `/tmp` шарится по умолчанию.
   Если `/work` пуст — проверь настройки file sharing своего рантайма.
4. Размер образа ~1.2 ГБ — это нормально для среды с PHP + пятью анализаторами.

## Рантайм: Docker Desktop или Colima
Образ стандартный — работает в обоих. **Colima** (Apache-2.0, CLI-only) предпочтителен там, где важна лицензионная
чистота: у Docker Desktop платная лицензия для крупных компаний. Установка Colima:
`brew install colima docker docker-compose && colima start --cpu 4 --memory 6`.
