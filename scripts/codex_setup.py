#!/usr/bin/env python3
"""Codex для второго мнения: официальный плагин OpenAI для Claude Code и CLI `codex`.

Плагин (github.com/openai/codex-plugin-cc, Apache-2.0) даёт команды /codex:review, /codex:adversarial-review,
/codex:rescue; CLI нужен scripts/second_opinion.py. Подходит любой план ChatGPT, включая бесплатный, или ключ
OpenAI API. Идемпотентно; кто выключил плагин руками (enabledPlugins = false), тому не включаем.

  python scripts/codex_setup.py            # поставить плагин и CLI, проверить доступ к OpenAI
  python scripts/codex_setup.py --check    # только проверить: CLI, вход, доступность из этой сети
  python scripts/codex_setup.py --dry-run

Доступ: OpenAI не обслуживает часть стран (в том числе РФ и РБ). Проверка ниже отличает геоблок от
обычной недоступности сети; при геоблоке нужен корпоративный VPN, иначе цепочка второго мнения просто
переходит к следующему звену. Рабочий код: на бесплатном и Plus выключи обучение на своих данных —
ChatGPT → Settings → Data Controls → Improve the model for everyone → Off.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PLUGIN = "codex@openai-codex"
MARKET = "openai/codex-plugin-cc"


def plugin_disabled() -> bool:
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    try:
        data = json.loads((base / "settings.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and (data.get("enabledPlugins") or {}).get(PLUGIN) is False


def run(cmd: list, dry: bool, timeout: int = 600) -> bool:
    if dry:
        print("    $ " + " ".join(cmd))
        return True
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"    ! {cmd[0]}: {e}")
        return False
    if r.returncode != 0:
        print(f"    ! {' '.join(cmd)}: {(r.stderr or r.stdout).strip()[:300]}")
    return r.returncode == 0


def reachability(timeout: int = 10) -> str:
    """ok | geoblock | network: запрос без ключа — 401 значит API отвечает из этой сети."""
    try:
        urllib.request.urlopen("https://api.openai.com/v1/models", timeout=timeout)
        return "ok"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace").lower()
        if e.code == 403 and ("unsupported_country" in body or "country" in body or "region" in body):
            return "geoblock"
        return "ok" if e.code in (401, 403) else "network"
    except (urllib.error.URLError, OSError):
        return "network"


def logged_in(exe: str) -> bool:
    try:
        r = subprocess.run([exe, "login", "status"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def check() -> None:
    exe = shutil.which("codex")
    net = reachability()
    print(f"  CLI codex: {'есть' if exe else 'нет'}; вход: {'да' if exe and logged_in(exe) else 'нет — `codex login`'}")
    print({"ok": "  OpenAI доступен из этой сети",
           "geoblock": "  [!] OpenAI недоступен из этой страны (геоблок). Нужен корпоративный VPN; без него второе мнение "
                       "возьмёт следующее звено цепочки",
           "network": "  [!] OpenAI не отвечает (сеть, прокси). Проверь VPN или прокси"}[net])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        check()
        return 0
    claude = shutil.which("claude")
    if plugin_disabled():
        print(f"  [=] {PLUGIN} выключен пользователем, не включаю")
    elif not claude:
        print(f"  [-] claude CLI не найден: в приложении поставь плагин командой /plugin marketplace add {MARKET}, "
              f"затем /plugin install {PLUGIN}")
    elif (run([claude, "plugin", "marketplace", "add", MARKET], a.dry_run) or True) and \
            run([claude, "plugin", "install", PLUGIN], a.dry_run):    # повторный marketplace add — не ошибка
        print(f"  [ok] плагин {PLUGIN}: /codex:review, /codex:adversarial-review, /codex:rescue")
    if not shutil.which("codex"):
        npm = shutil.which("npm")
        if npm and run([npm, "install", "-g", "@openai/codex"], a.dry_run):
            print("  [ok] CLI codex установлен (npm -g @openai/codex)")
        else:
            print("  [!] CLI codex не установлен: нужен Node.js 18.18+, затем `npm install -g @openai/codex`")
    if not a.dry_run:
        check()
    print("  Вход один раз: `codex login` (план ChatGPT, бесплатный тоже подходит). Для рабочего кода выключи обучение:\n"
          "  ChatGPT → Settings → Data Controls → Improve the model for everyone → Off.")
    return 0                                     # Codex необязателен и не должен валить онбординг


if __name__ == "__main__":
    sys.exit(main())
