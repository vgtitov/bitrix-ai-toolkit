#!/usr/bin/env python3
"""PostToolUse-хук: прогнать линтеры по изменённому PHP-файлу и вернуть находки агенту.

Как это работает (формат Claude Code): хук получает JSON на STDIN, путь к файлу — в
`tool_input.file_path`. Переменной окружения с путём НЕТ (старая $CLAUDE_FILE_PATHS удалена).
Результат отдаём агенту через `hookSpecificOutput.additionalContext` — он попадает в контекст,
и агент чинит ошибки сам, не тратя токены на запуск линтеров.

Уважает опциональность: режим берётся из checks_config (off/warn/block).
  off   — ничего не делает
  warn  — прогоняет, отдаёт находки как контекст (не блокирует)
  block — то же + помечает, что правку нужно довести до зелёного

Никогда не падает: нет линтера / битый вход / нет python-зависимостей → тихий выход 0.
Только стандартная библиотека.

Подключение — в .claude/settings.json:
    {"hooks": {"PostToolUse": [{"matcher": "Edit|Write",
      "hooks": [{"type": "command", "command": "python3 scripts/posttool_lint.py"}]}]}}
"""
import json
import os
import shutil
import subprocess
import sys

TOOLKIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_OUT = 4000          # не раздувать контекст агента


def emit(context: str) -> None:
    """Отдать текст агенту как дополнительный контекст (не блокирует выполнение)."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context[:MAX_OUT],
        }
    }, ensure_ascii=False))


def mode_for(check: str) -> str:
    try:
        sys.path.insert(0, os.path.join(TOOLKIT, "scripts"))
        from checks_config import effective_mode  # noqa: PLC0415
        return effective_mode(check)
    except Exception:
        return "warn"


def run(cmd, cwd):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception:
        return 0, ""


def tool_path(cwd, name):
    """Инструмент из vendor/bin проекта, иначе из PATH, иначе None."""
    local = os.path.join(cwd, "vendor", "bin", name)
    if os.path.isfile(local):
        return local
    return shutil.which(name)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0                                   # не наш вход — молча выходим

    path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not path.lower().endswith(".php") or not os.path.isfile(path):
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    notes = []

    # 1. Стиль — правим автоматически (агенту не нужно тратить на это ход)
    if mode_for("php_cs_fixer") != "off":
        fixer = tool_path(cwd, "php-cs-fixer")
        if fixer:
            run([fixer, "fix", path, "--quiet"], cwd)

    # 2. Статанализ — находки отдаём агенту, чтобы он их починил
    stan_mode = mode_for("phpstan")
    if stan_mode != "off":
        stan = tool_path(cwd, "phpstan")
        has_cfg = any(os.path.isfile(os.path.join(cwd, f)) for f in ("phpstan.neon", "phpstan.neon.dist"))
        if stan and has_cfg:
            rc, out = run([stan, "analyse", path, "--error-format=json", "--no-progress"], cwd)
            if rc != 0 and out.strip():
                msgs = []
                try:
                    # PHPStan печатает JSON, а после него может быть строка "Note: Using configuration…".
                    # json.loads на всём выводе падает → берём ровно первый JSON-объект.
                    start = out.find("{")
                    data = json.JSONDecoder().raw_decode(out, start)[0] if start >= 0 else {}
                    for fpath, info in (data.get("files") or {}).items():
                        for m in info.get("messages", []):
                            msgs.append(f"{os.path.basename(fpath)}:{m.get('line')}: {m.get('message')}")
                except Exception:
                    msgs = [out.strip()[:1000]]
                if msgs:
                    head = "PHPStan нашёл проблемы в изменённом файле"
                    if stan_mode == "block":
                        head += " (режим block — доведи до зелёного, прежде чем завершать)"
                    notes.append(head + ":\n" + "\n".join(msgs[:20]))

    if notes:
        emit("\n\n".join(notes))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)                                # хук никогда не ломает работу агента
