# Changelog

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/). Версии — [SemVer](https://semver.org/lang/ru/).

## [Unreleased]

### Added
- Ядро `core/` (общее для всех AI-агентов): `AGENTS.md` (правила: два ядра, `/local`-гейт, «спроси инструмент»,
  версии, безопасность, качество), скиллы `bitrix-dev` / `bitrix-analyst` / `bitrix-performance` (+6 references) /
  `bitrix-admin-devops`.
- Зашитые проверки: `phpstan.neon.dist` (+`phpstan-deprecation-rules`, совместимость по версии ядра через
  `scanDirectories`), ast-grep правила (N+1, SQL-инъекция, старое API, отключённый кэш, XSS),
  детектор N+1 `scripts/bitrix_guard.py`, `phpcs`/`php-cs-fixer`/`rector`.
- Мульти-агентность: `adapters/` (claude — эталон; codex/gemini — фолбэк; cursor/copilot/cline/windsurf/aider —
  rulesync/ручные) + `build.sh`. Оси переносимости: AGENTS.md + SKILL.md + MCP.
- Git-хуки: `commit-msg` (чистые сообщения) + `pre-commit` (bitrix-guard N+1); `scripts/install_git_hooks.py`.
- Автоустановка `onboard/install.sh` (инструменты + хуки + скиллы + сборка + самотест).
- Тесты: `tests/test_bitrix_guard.py` + фикстуры.
- Документация: `docs/version-compatibility.md`, `AI_INSTALL_GUIDE.md`, `ACCESS_SETUP.md`, `ПЛАН_РЕАЛИЗАЦИИ.md`, `demo/`.
- OSS-обвязка: `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY`, шаблоны Issue/PR, CI (GitHub Actions), MIT `LICENSE`.

[Unreleased]: https://github.com/vgtitov/bitrix-ai-toolkit
