#!/usr/bin/env python3
"""Второе мнение другой моделью: ревью диффа или проверка документа, решения, гипотезы.

Claude не проверяет сам себя: ревью и проверку выносит модель другого семейства. Цепочка идёт по
порядку и вызывает только то, что у человека настроено:

  1. Codex (OpenAI)          — если установлен CLI `codex` и выполнен вход (`codex login`).
  2. Copilot или иной        — если задана AI_TOOLKIT_COPILOT_CMD: команда, которая читает вопрос
     корпоративный ассистент   со STDIN и печатает ответ (адаптер к M365 Copilot или другому сервису).
  3. Модель без обучения     — только если есть OPENROUTER_API_KEY И явно разрешено AI_TOOLKIT_NOTRAIN=1;
                               запрос уходит лишь провайдерам, которые не хранят и не обучаются
                               (provider.data_collection = deny), и только без e-mail и телефонов в тексте.
                               Бесплатные модели не вызываются никогда: они обучаются на запросах.

Звено пропускается, если его нет, оно в лимите, недоступно из страны (геоблок OpenAI в РФ, РБ и
других регионах — нужен VPN) или вернуло пустой ответ. Не ответил никто — код 2, и «готово» нельзя.

  python scripts/second_opinion.py review --base origin/main [--repo .]
  python scripts/second_opinion.py review --commit HEAD
  python scripts/second_opinion.py ask "полный контекст и вопрос"     (или «-» = STDIN)
  python scripts/second_opinion.py status                              # что из цепочки настроено

Отчёт: ~/.ai-toolkit/reviews/<время>-<вид>-<кто>.md; кто проверял — в последней строке вывода.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

REPORTS = Path.home() / ".ai-toolkit" / "reviews"
CHUNK = 24000
TIMEOUT = 1800
DOWN_RX = re.compile(r"(?m)^(ERROR:.*(usage limit|rate.?limit|429|quota|unauthori[sz]ed|not logged in|"
                     r"unsupported.?country|forbidden|403))", re.I)
PII_RX = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}|(?<!\d)(?:\+7|\+375|\+998|\+996|\+994|\+971|8)[\s(-]*\d{2,3}"
                    r"[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)", re.I)
REVIEW_PROMPT = ("Ты ревьюер кода. Часть {part} диффа репозитория {repo}. Найди дефекты: ошибки логики, "
                 "безопасность, потерю данных, регрессии, несоответствие описанию. Для каждого: [P0–P3] файл:строка "
                 "— что не так и как исправить. Стиль не обсуждай. Нет дефектов — так и напиши.\n\n{chunk}")
NOTRAIN_MODEL = os.environ.get("AI_TOOLKIT_NOTRAIN_MODEL", "openai/gpt-4.1-mini")


# ---------- звенья цепочки: каждое возвращает текст или None (звено недоступно) ----------

def codex_exec(args: list, cwd: Path, stdin: str | None = None) -> str | None:
    exe = shutil.which("codex")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, *args], cwd=cwd, input=stdin, capture_output=True, text=True, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"⚠ Codex: {e}", flush=True)
        return None
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 or not out.strip() or DOWN_RX.search(out[-800:]):
        print(f"⚠ Codex не ответил: {(out.strip().splitlines() or [str(r.returncode)])[-1][:160]}", flush=True)
        return None
    return out


def copilot(prompt: str) -> str | None:
    cmd = os.environ.get("AI_TOOLKIT_COPILOT_CMD", "").strip()
    if not cmd:
        return None
    try:
        r = subprocess.run(shlex.split(cmd, posix=os.name != "nt"), input=prompt, capture_output=True,
                           text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        print(f"⚠ Copilot: {e}", flush=True)
        return None
    return r.stdout if r.returncode == 0 and r.stdout.strip() else None


def notrain(prompt: str) -> str | None:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key or os.environ.get("AI_TOOLKIT_NOTRAIN") != "1":
        return None
    if PII_RX.search(prompt):
        print("⚠ модель без обучения пропущена: в тексте e-mail или телефон", flush=True)
        return None
    body = json.dumps({"model": NOTRAIN_MODEL, "messages": [{"role": "user", "content": prompt}],
                       "provider": {"data_collection": "deny"}}).encode("utf-8")
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.load(resp)
        return (data.get("choices") or [{}])[0].get("message", {}).get("content") or None
    except Exception as e:                                   # noqa: BLE001 — звено недоступно, идём дальше
        print(f"⚠ модель без обучения: {str(e)[:160]}", flush=True)
        return None


TEXT_CHAIN = (("copilot", copilot), ("notrain", notrain))


# ---------- сценарии ----------

def split_diff(diff: str, limit: int = CHUNK) -> list:
    """Дифф → куски не длиннее limit по границам файлов; длинный файл режется подряд."""
    out, cur = [], ""
    for f in (x for x in re.split(r"(?m)^(?=diff --git )", diff) if x.strip()):
        for p in (f[i:i + limit] for i in range(0, len(f), limit)):
            if cur and len(cur) + len(p) > limit:
                out.append(cur)
                cur = ""
            cur += p
    return out + ([cur] if cur else [])


def review(repo: Path, base: str | None, commit: str | None, chain=TEXT_CHAIN, codex=codex_exec) -> tuple:
    out = codex(["exec", "review"] + (["--commit", commit] if commit else ["--base", base]), repo)
    if out:
        return "codex", out
    cmd = ["git", "show", "--format=", "--no-color", "-U5", commit] if commit else \
        ["git", "diff", "--no-color", "-U5", f"{base}...HEAD"]
    diff = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=True).stdout
    if not diff.strip():
        return "none", "Дифф пуст — проверять нечего."
    chunks = split_diff(diff)
    for who, fn in chain:
        parts = []
        for i, ch in enumerate(chunks, 1):
            ans = fn(REVIEW_PROMPT.format(part=f"{i} из {len(chunks)}", repo=repo.name, chunk=ch))
            if not ans:
                break
            parts.append(f"## Часть {i}\n\n{ans.strip()}\n")
        if len(parts) == len(chunks):
            return who, "\n".join(parts)
    return "", ""


def ask(prompt: str, chain=TEXT_CHAIN, codex=codex_exec) -> tuple:
    out = codex(["exec", "--skip-git-repo-check", "-s", "read-only", "-"], Path.cwd(), stdin=prompt)
    if out:
        return "codex", out
    for who, fn in chain:
        ans = fn(prompt)
        if ans:
            return who, ans
    return "", ""


def status() -> int:
    print("Codex CLI:", "есть" if shutil.which("codex") else "нет (scripts/codex_setup.py)")
    print("Copilot/иной ассистент:", "AI_TOOLKIT_COPILOT_CMD задана" if os.environ.get("AI_TOOLKIT_COPILOT_CMD")
          else "не настроен")
    print("Модель без обучения:", "включена" if os.environ.get("OPENROUTER_API_KEY")
          and os.environ.get("AI_TOOLKIT_NOTRAIN") == "1" else "выключена (OPENROUTER_API_KEY + AI_TOOLKIT_NOTRAIN=1)")
    return 0


def _report(kind: str, who: str, body: str) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    p = REPORTS / f"{datetime.now():%Y%m%d-%H%M%S}-{kind}-{who}.md"
    p.write_text(body, encoding="utf-8")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    rv = sub.add_parser("review")
    rv.add_argument("--repo", type=Path, default=Path.cwd())
    g = rv.add_mutually_exclusive_group(required=True)
    g.add_argument("--base")
    g.add_argument("--commit")
    ak = sub.add_parser("ask")
    ak.add_argument("text")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        return status()
    if a.cmd == "review":
        who, body = review(a.repo.resolve(), a.base, a.commit)
    else:
        who, body = ask(sys.stdin.read() if a.text == "-" else a.text)
    if not who:
        print("Второе мнение недоступно: ни одно звено цепочки не ответило. Проверь `status`; готовым не считать.")
        return 2
    print(body)
    print(f"\nПроверял: {who}. Отчёт: {_report(a.cmd, who, body)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
