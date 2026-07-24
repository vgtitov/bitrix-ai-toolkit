# SETUP — полная настройка toolkit по шагам

Единый маршрут: от клонирования до работающего контура. Всё, кроме шага 1-3, **опционально** — toolkit работает
на безопасных дефолтах и не ломается, если что-то не настроено.

---

## Шаг 1. Установка (одна команда)
```bash
git clone https://github.com/vgtitov/bitrix-ai-toolkit && cd bitrix-ai-toolkit
sh onboard/install.sh              # инструменты + хуки + скиллы + конфиги + сборка + самотест
sh onboard/install.sh --no-tools   # если PHP/composer/ast-grep уже стоят
```
Что делает: ставит PHP/Composer/ast-grep (brew), git-хуки, копирует скиллы в `~/.claude/skills`, создаёт
`config/checks.toml` и `config/version-stack.toml` из образцов (существующие **не трогает**), собирает конфиги
агентов (`build.sh`), прогоняет самотест.

## Шаг 2. Линтер-конфиги в проект
```bash
cp core/linters/phpstan.neon.dist       <проект>/phpstan.neon
cp core/linters/phpcs.xml.dist          <проект>/phpcs.xml
cp core/linters/.php-cs-fixer.dist.php  <проект>/.php-cs-fixer.dist.php
cp core/linters/rector.php              <проект>/rector.php
```

## Шаг 3. Версионный стек (ключ к корректности)
`config/version-stack.toml`:
- `[php].version` — 8.2/8.3 (таргет Rector/PHPStan).
- `[bitrix].core_path` — путь к **реальному ядру проекта** → PHPStan `scanDirectories` → ловит «метода нет в этой версии».
- `[bitrix].core_modified = true` — если ядро правлено (см. `core/skills/bitrix-dev/references/custom-core.md`).
- `[conventions].legacy_required` — где D7-обёрток нет и legacy-API обязателен (чтобы линтер/агент не «исправлял»).

Сгенерировать аннотации ORM под свою версию:
```bash
php bitrix/modules/main/cli.php orm annotate     # → orm_annotations.php (в scanFiles phpstan.neon)
```

---

## Шаг 4. Режим проверок — как ведёт себя AI
Настройка: `config/checks.toml` (или `config/local/checks.toml`), либо env `BITRIX_AI_CHECKS`.
Приоритет: **env > config/local > config > дефолт(warn)**.

| Режим | Что делает проверка | Как ведёт себя AI | Кому |
|---|---|---|---|
| **`off`** | не запускается | пишет код по знаниям скилла (`quality-standards.md`), не гоняет линтеры | кто не хочет никаких инструментов |
| **`warn`** ⭐дефолт | запускается, показывает находки, **не блокирует** | **сообщает о проблемах** и предлагает фикс; коммит проходит | большинство — не мешает работать |
| **`block`** | запускается, **блокирует** при находках | **обязан сам починить** до завершения; pre-commit останавливает коммит | кто хочет строгий гейт на своём коде |

Точечно по проверкам (`phpstan`, `php_cs_fixer`, `ast_grep`, `n1_guard`) — секции `[checks.<имя>]`.
Ограничить своими путями — `[scope].paths` (не трогать чужой/легаси-код).

```bash
BITRIX_AI_CHECKS=off   # разовый глобальный выключатель
BITRIX_AI_CHECKS=block # разовый строгий прогон
python3 scripts/checks_config.py n1_guard   # какой режим действует сейчас
```

**Важно:** качество кода **не зависит** от режима. Стандарты зашиты в скилл `bitrix-dev`
(`references/quality-standards.md`) — AI пишет корректно даже при `off`; проверки лишь подтверждают.

---

## Шаг 5 (опц.). Language Server агенту — навигация и диагностики
Битрикс-специфичного LS нет; переиспользуем готовые. Подробно — `docs/language-server.md`.
```bash
npm install -g intelephense
go install github.com/isaacphi/mcp-language-server@latest
claude mcp add php-lsp -- mcp-language-server --workspace "$(pwd)" --lsp intelephense -- --stdio
```
Альтернатива без установки: **Serena** (уже в `.mcp.json`) даёт символьную навигацию и диагностики.
Для Claude Code проще всего — плагин `php-lsp@claude-plugins-official`.

## Шаг 6 (опц.). Проверки в Docker — локально и централизованно
Не хочешь ставить PHP/линтеры локально или нужна **единая версия у команды и в CI**:
```bash
docker compose -f docker/docker-compose.yml run --rm checks            # весь проект
docker compose -f docker/docker-compose.yml run --rm checks check local/
BITRIX_AI_CHECKS=block docker compose -f docker/docker-compose.yml run --rm checks
```
Локальный путь всегда работает без Docker — контейнер только ускоряет/унифицирует.

## Шаг 7 (опц.). Интеграции Jira / Confluence
Креды в `config/local/.env` (не в git). Подробно — `docs/integrations.md`.
```bash
python3 scripts/atlassian.py jira issue PROJ-123 --comments
python3 scripts/atlassian.py conf search "критерии приёмки"
```
Нет кред → интеграция просто не используется.

## Шаг 8 (опц.). Настройки компании отдельным репозиторием
`config/local/` — слой компании (в `.gitignore`): режимы проверок, версии, конвенции, креды.
Можно вести приватным репо и подключать клоном/симлинком — `docs/LOCALIZATION.md`.
**Без этого слоя всё работает на дефолтах.**

## Шаг 9 (опц.). IDE
PhpStorm 2025.2+: `Settings → Tools → MCP Server` — агент получает инспекции, рефакторинги, навигацию IDE.
VS Code — расширение Claude Code. Cursor/Windsurf/Zed — нативно. Никто не меняет редактор.

---

## Проверка, что всё встало
```bash
python3 tests/test_bitrix_guard.py                 # 4/4
sh build.sh && head -1 CLAUDE.md                   # @AGENTS.md
python3 scripts/checks_config.py n1_guard          # off|warn|block
git config --global --get core.hooksPath           # путь к git-хукам
```

## Если что-то не установлено
Toolkit спроектирован на **graceful degradation**: нет ast-grep → его правила пропускаются (guard N+1 работает);
нет PHPStan → шаг пропускается; нет конфигов → дефолты; нет `config/local` → generic-поведение.
**Ничего не падает и не блокирует работу.**
