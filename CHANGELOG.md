# Changelog

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/). Версии — [SemVer](https://semver.org/lang/ru/).

## [Unreleased]

### Added
- Скиллы `bitrix-tester` (QA: лестница проверки статика→юнит→стейджинг-смоук→браузер→мутационное
  тестирование, вердикт только по цитируемому выводу прогона) и `bitrix-dba` (DBA слоя СУБД
  MySQL/MariaDB: тюнинг `my.cnf`, регламент, блокировки/deadlock, бэкап/восстановление, репликация —
  отдельно от `bitrix-performance`, который отвечает за запросы/кэш на стороне приложения).
- Ядро `core/` (общее для всех AI-агентов): `AGENTS.md` (правила: два ядра, `/local`-гейт, «спроси инструмент»,
  версии, безопасность, качество), скиллы `bitrix-dev` / `bitrix-analyst` / `bitrix-performance` (+references) /
  `bitrix-admin-devops`.
- Зашитые проверки: `phpstan.neon.dist` (+`phpstan-deprecation-rules`, совместимость по версии ядра через
  `scanDirectories`), ast-grep правила (N+1, SQL-инъекция, старое API, отключённый кэш, XSS),
  детектор N+1 `scripts/bitrix_guard.py`, `phpcs`/`php-cs-fixer`/`rector`.
- Мульти-агентность: `adapters/` + `build.sh`. Из коробки собираются Claude Code, Codex, Gemini CLI;
  Cursor/Copilot/Cline — через внешний rulesync; Windsurf/Aider — вручную (см. `adapters/README.md`).
  Оси переносимости: AGENTS.md + SKILL.md + MCP.
- Git-хуки: `commit-msg` (чистые сообщения) + `pre-commit` (bitrix-guard N+1); `scripts/install_git_hooks.py`.
- Автоустановка `onboard/install.sh` (инструменты + хуки + скиллы + сборка + самотест).
- Тесты: `tests/test_bitrix_guard.py` + фикстуры.
- Документация: `docs/version-compatibility.md`, `AI_INSTALL_GUIDE.md`, `ACCESS_SETUP.md`, `ПЛАН_РЕАЛИЗАЦИИ.md`, `demo/`.
- OSS-обвязка: `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY`, шаблоны Issue/PR, CI (GitHub Actions), MIT `LICENSE`.
- `scripts/init_project.py` — генерация `phpstan.neon` под реальный проект (ядро, кастомные слои, свой код).
- `scripts/posttool_lint.py` — PostToolUse-хук: линтеры по изменённому файлу, находки возвращаются агенту.
- `scripts/changed_files.py` — профиль «грязный легаси»: проверки только по изменённым файлам.
- `.rulesync/` — источник для генерации конфигов Cursor/Copilot/Cline, наполняется из `core/AGENTS.md`.
- `core/linters/infection.json5` — мутационное тестирование (MSI) там, где тесты уже есть.

### Fixed
Первое внешнее adversarial-ревью нашло 38 дефектов. Критичные закрыты:
- PostToolUse-хук не работал вообще (`$CLAUDE_FILE_PATHS` не существует — хуки получают JSON на stdin);
- в публичном репозитории лежали реальные идентификаторы задач/страниц;
- установщик хуков перехватывал `core.hooksPath` на всей машине, отключая husky/pre-commit в чужих репо;
- `config/local/` не игнорировался — настройки компании утекли бы в форк;
- `docker-compose` монтировал родительский каталог toolkit вместо проекта;
- `fetch_official_docs.sh` умирал на первой неудаче клона (`set -e`);
- детектор N+1 был слеп к `foreach: … endforeach` и к heredoc с непарными скобками (пропускал реальные находки);
- `onboard` никогда не ставил линтеры; `serena` не стартовала; `build.sh` тянул npm-пакет из сети при каждой сборке.

[Unreleased]: https://github.com/vgtitov/bitrix-ai-toolkit
