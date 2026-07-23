# Автоустановка Клодом — как развернуть toolkit по команде

Гайд для AI-агента: развернуть контур на машине/проекте самому, по команде «разверни bitrix-toolkit», без затыков.

## Одной командой
```bash
sh onboard/install.sh          # инструменты + хуки + скиллы + сборка + самотест
sh onboard/install.sh --no-tools   # если инструменты уже стоят
```

## Что делает onboard (по шагам)
1. **Инструменты** (macOS brew / иначе подсказки): PHP 8.2+, Composer, ast-grep. В целевом проекте (если есть
   `composer.json`) — dev-зависимости: PHPStan+deprecation-rules+strict, php-cs-fixer, php_codesniffer, rector, phpunit.
2. **Git-хуки** (`scripts/install_git_hooks.py`): commit-msg (чистые сообщения без атрибуции) + pre-commit (bitrix-guard N+1).
3. **Скиллы** → `~/.claude/skills/` (bitrix-dev/analyst/performance/admin-devops).
4. **Сборка** (`build.sh`): CLAUDE.md←@AGENTS.md, AGENTS.md, GEMINI.md, .mcp.json, .claude/skills, .claude/settings.json.
5. **Самотест**: `tests/test_bitrix_guard.py` (должно быть 4/4) + загрузка ast-grep-правил.

## Preflight (проверить перед установкой — грабли)
- **Не перезаписывать** существующий `.env`/`CLAUDE.md` проекта без спроса — onboard пишет toolkit-файлы, не проект.
- **composer.json проекта** — dev-зависимости ставятся в ПРОЕКТ, не в toolkit. Если CWD не проект — пропустится (норма).
- **ast-grep** может не поставиться на Linux без npm — тогда `npm i -g @ast-grep/cli`. Guard N+1 работает и без ast-grep.
- **bitrix-ci архивный** — если PHPStan не видит ядро, положи распакованное ядро своей версии в `scanDirectories` вручную.
- **Windows**: git-хуки через git-bash; `build.sh` — тоже через sh (git-bash из состава Git).

## После onboard — что настроить в ПРОЕКТЕ (не автоматизируется)
1. Скопировать `core/linters/{phpstan.neon.dist→phpstan.neon, phpcs.xml.dist, .php-cs-fixer.dist.php, rector.php}` в корень.
2. Заполнить `config/version-stack.toml` (PHP, версии модулей, legacy_required).
3. Положить ядро своей версии по `[bitrix].core_path`; `orm annotate` → `orm_annotations.php`.
4. MCP: `claude mcp add --transport http bitrix-docs https://mcp-dev.bitrix24.com/mcp`.
5. PhpStorm 2025.2+: Settings → Tools → MCP Server (мост для Claude Code).

## Проверка, что всё встало
```bash
python3 tests/test_bitrix_guard.py     # 4/4
sh build.sh && cat CLAUDE.md | head -1 # @AGENTS.md
git config --global --get core.hooksPath  # путь к хукам
```

## Принцип верификации
«Работает» — только с показанным выводом целевой системы. После установки прогони самотест и покажи вывод, не утверждай «готово» вслепую.
