#!/usr/bin/env python3
"""Дисциплина выполнения: Stop-хук Claude Code, который не даёт закончить ход «на словах».

Три проверки ТЕКУЩЕГО хода (с последнего сообщения человека, а не всей сессии):
  1. код изменён, а проверка не запускалась (тесты, линтер, BSL LS, смоук, проверка ошибок проекта);
  2. ход кончается обещанием («сейчас сделаю», «далее я…») без вызова инструмента после него;
  3. не-код: заявлено «готово» после работы, но нет ни файла-результата, ни источников.

Режим — переменная AI_TOOLKIT_DISCIPLINE: warn (по умолчанию) показывает предупреждение и не мешает,
enforce возвращает модель доделывать, off выключает. Модель не меняется: хук лишь не даёт ей объявить
готовность без доказательства, одинаково для сильной и слабой модели.

  python scripts/discipline_gate.py            # режим хука: JSON Stop-события на STDIN
  python scripts/discipline_gate.py install    # прописать хук в ~/.claude/settings.json (идемпотентно)
  python scripts/discipline_gate.py uninstall  # убрать хук
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

MARK = "discipline_gate.py"
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
CODE_EXT = (".bsl", ".os", ".mdo", ".form", ".dcs", ".rights", ".php", ".js", ".ts", ".tsx", ".jsx", ".py",
            ".ps1", ".sh")
ARTIFACT_EXT = (".md", ".txt", ".docx", ".xlsx", ".pptx", ".pdf", ".csv", ".json", ".html", ".puml", ".mmd")
# признак проверки: подстрока в команде Bash или в имени инструмента MCP
VERIFY = ("pytest", "unittest", "bsl_guard", "rights_guard", "bsl-ls", "bsl_ls", "bsl-language-server",
          "onec_verify", "smoke", "designer_sync", "yaxunit", "get_project_errors", "syntax_check",
          "phpunit", "phpstan", "php -l", "eslint", "npm test", "npm run test", "tsc", "ruff", "pyright",
          "go test", "cargo test", "make test")
PROMISE = ("i'll ", "i will ", "let me now", "next i ", "далее я ", "сейчас сделаю", "сейчас я ",
           "теперь сделаю", "приступаю", "осталось сделать", "сделаю это", "займусь")
DONE_RE = re.compile(r"готов[оа]?\b|сделал|сделано|исправил|завершил|\bdone\b|\bfixed\b|\bcompleted\b",
                     re.IGNORECASE)
POLITE = ("готов помочь", "готов ответить", "готов продолжить", "ready to help")
EVIDENCE_RE = re.compile(r"https?://|\.(?:md|pdf|docx|xlsx|txt|csv)\b|/[\w.\-]+/[\w.\-]+|источник|согласно|"
                         r"цитат|см\.|\bsource\b|according to", re.IGNORECASE)

MSG_CODE = ("Дисциплина: код изменён, а проверка не запускалась или упала. Прогони проверку (тесты, BSL LS, "
            "смоук, линтер), добейся прохода и покажи вывод, прежде чем говорить «готово».")
MSG_PROMISE = ("Дисциплина: ход кончается обещанием без исполнения. Сделай обещанное сейчас "
               "или прямо скажи, что откладываешь и почему.")
MSG_NONDEV = ("Дисциплина: заявлено «готово», но нет файла с результатом и источников. Сохрани результат "
              "в файл или покажи, на что опирается вывод.")


def _entries(path: str) -> list:
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def _blocks(entry: dict) -> list:
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _is_human_prompt(entry: dict) -> bool:
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    blocks = _blocks(entry)
    return bool(blocks) and not any(b.get("type") == "tool_result" for b in blocks)


def current_turn(entries: list) -> list:
    """Записи после последнего сообщения человека."""
    for i in range(len(entries) - 1, -1, -1):
        if _is_human_prompt(entries[i]):
            return entries[i + 1:]
    return entries


def _failed_ids(turn: list) -> set:
    """id вызовов инструментов, которые вернули ошибку."""
    return {b.get("tool_use_id") for e in turn if e.get("type") == "user" for b in _blocks(e)
            if b.get("type") == "tool_result" and b.get("is_error")}


def _tool_uses(turn: list) -> list:
    """Успешные вызовы инструментов хода; неудачная запись файла не считается ни правкой, ни результатом."""
    failed = _failed_ids(turn)
    return [b for e in turn if e.get("type") == "assistant" for b in _blocks(e)
            if b.get("type") == "tool_use" and b.get("id") not in failed]


def _is_code(path: str) -> bool:
    low = path.lower().replace("\\", "/")
    base = low.rsplit("/", 1)[-1]
    # тест узнаём по имени файла и каталогу tests/; каталог test/ бывает и у обычного кода
    if (base.startswith("test_") or "/tests/" in low or low.startswith("tests/")
            or re.search(r"(_test|\.test|\.spec)\.[a-z]+$", base)
            or re.search(r"Tests?\.php$", path.replace("\\", "/").rsplit("/", 1)[-1])):
        return False
    return low.endswith(CODE_EXT)


def code_edited(uses: list) -> bool:
    for u in uses:
        name, inp = u.get("name", ""), u.get("input") or {}
        if name in EDIT_TOOLS and _is_code(str(inp.get("file_path", ""))):
            return True
        if "write_module_source" in name:
            return True
    return False


READERS = {"echo", "printf", "cat", "grep", "rg", "head", "tail", "less", "more", "ls", "sed", "awk", "find",
           "git", "type", "get-content", "select-string", "write-host"}


def _runs_check(command: str) -> bool:
    """Проверка именно запускается: в отрезке команды есть признак проверки и он не просто читается."""
    for seg in re.split(r"&&|\|\||[;|\n]", command.lower()):
        words = [w for w in seg.split() if "=" not in w or w.startswith("-")]
        if words and words[0] == "cd":
            continue
        if words and words[0] not in READERS and any(tok in seg for tok in VERIFY):
            return True
    return False


def verified(uses: list) -> bool:
    for u in uses:
        name = u.get("name", "")
        if name in ("Bash", "PowerShell"):
            if _runs_check(str((u.get("input") or {}).get("command", ""))):
                return True
        elif any(tok in name.lower() for tok in VERIFY):      # MCP: bsl-ls, get_project_errors…
            return True
    return False


def artifact_written(uses: list) -> bool:
    return any(u.get("name") in EDIT_TOOLS
               and str((u.get("input") or {}).get("file_path", "")).lower().endswith(ARTIFACT_EXT) for u in uses)


def last_reply(turn: list) -> tuple[str, bool]:
    """Текст последнего ответа модели и был ли после него вызов инструмента."""
    for e in reversed(turn):
        if e.get("type") != "assistant":
            continue
        blocks = [b for b in _blocks(e) if b.get("type") in ("text", "tool_use")]
        if not blocks:
            continue
        if blocks[-1].get("type") == "tool_use":        # после текста в том же ответе вызван инструмент
            return "", True
        return " ".join(b.get("text", "") for b in blocks if b.get("type") == "text"), False
    return "", False


def decide(turn: list) -> str:
    uses = _tool_uses(turn)
    text, tool_after = last_reply(turn)
    low = text.lower()
    for p in POLITE:
        low = low.replace(p, " ")
    if code_edited(uses) and not verified(uses):
        return MSG_CODE
    if not tool_after and any(p in low[-400:] for p in PROMISE):
        return MSG_PROMISE
    if (DONE_RE.search(low) and len(uses) >= 2 and not code_edited(uses)
            and not artifact_written(uses) and not EVIDENCE_RE.search(low)):
        return MSG_NONDEV
    return ""


def mode() -> str:
    m = os.environ.get("AI_TOOLKIT_DISCIPLINE", "warn").strip().lower()
    return m if m in ("off", "warn", "enforce") else "warn"


def hook() -> int:
    if mode() == "off":
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if payload.get("stop_hook_active"):          # уже возвращали модель — не зацикливаться
        return 0
    msg = decide(current_turn(_entries(payload.get("transcript_path", ""))))
    if msg:
        out = {"decision": "block", "reason": msg} if mode() == "enforce" else {"systemMessage": msg}
        print(json.dumps(out, ensure_ascii=False))
    return 0                                     # хук никогда не валит сессию


# ---------- установка в пользовательские настройки Claude Code ----------

def settings_path() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "settings.json"


def hook_command() -> str:
    script = Path(__file__).resolve().as_posix()
    pick = "P=$(for c in python3 python; do \"$c\" -c '' >/dev/null 2>&1 && { echo \"$c\"; break; }; done); "
    return pick + "${P:-uv run --quiet --no-project --python 3.12 python} \"" + script + "\" 2>/dev/null || true"


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None


def _strip(data: dict) -> None:
    stop = (data.get("hooks") or {}).get("Stop")
    if not isinstance(stop, list):
        return
    kept = []
    for group in stop:
        hooks = [h for h in (group.get("hooks") or []) if MARK not in str(h.get("command", ""))] \
            if isinstance(group, dict) else group
        if not isinstance(group, dict) or hooks:
            kept.append(dict(group, hooks=hooks) if isinstance(group, dict) else group)
    data["hooks"]["Stop"] = kept
    if not kept:
        del data["hooks"]["Stop"]


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + ".bak-ai-toolkit")          # одна копия исходного файла, до первой правки
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _marked_scripts(data: dict) -> list:
    """Пути скриптов уже установленных хуков дисциплины (из любого набора)."""
    out = []
    for g in (data.get("hooks") or {}).get("Stop") or []:
        for h in (g.get("hooks") or []) if isinstance(g, dict) else []:
            m = re.search(r'"([^"]*discipline_gate\.py)"', str(h.get("command", "")))
            if m:
                out.append(m.group(1))
    return out


def install(remove: bool = False) -> int:
    path = settings_path()
    data = _load(path)
    if not isinstance(data, dict):
        print(f"  [!] {path} не читается как JSON-объект, не трогаю")
        return 0
    if not remove and str((data.get("env") or {}).get("AI_TOOLKIT_DISCIPLINE", "")).lower() == "off":
        print("  [=] дисциплина выключена пользователем (env AI_TOOLKIT_DISCIPLINE=off), не включаю")
        return 0
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict) or not isinstance(hooks.get("Stop", []), list):
        print(f"  [!] {path}: hooks или Stop неожиданной формы, не трогаю")
        return 0
    mine = Path(__file__).resolve().as_posix()
    other = [c for c in _marked_scripts(data) if c != mine and Path(c).exists()]
    if not remove and other:
        print(f"  [=] хук дисциплины уже стоит от другого набора ({other[0]}), второй не добавляю")
        return 0
    data.setdefault("hooks", {})
    _strip(data)
    if not remove:
        data["hooks"].setdefault("Stop", []).append(
            {"hooks": [{"type": "command", "command": hook_command(), "timeout": 20}]})
    if not data["hooks"]:
        del data["hooks"]
    _save(path, data)
    print(f"  [ok] дисциплина {'убрана из' if remove else 'в'} {path}"
          + ("" if remove else f" (режим {mode()}; AI_TOOLKIT_DISCIPLINE=off|warn|enforce)"))
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit(install() if arg == "install" else install(remove=True) if arg == "uninstall" else hook())
