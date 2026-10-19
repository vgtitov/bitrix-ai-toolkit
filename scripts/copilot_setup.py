#!/usr/bin/env python3
"""M365 Copilot как второе мнение по умолчанию: подготовить адаптер (Playwright и браузер) и проверить вход.

  python scripts/copilot_setup.py          # поставить браузер для Playwright, показать, выполнен ли вход
  python scripts/copilot_setup.py --login  # открыть окно M365: войти рабочей учёткой один раз
  python scripts/copilot_setup.py --check  # только проверить

Идемпотентно. Вход делает человек (в окне корпоративный SSO), всё остальное — сам скрипт. После входа
second_opinion.py находит адаптер без настройки переменных. Не нужен uv или браузер не скачался —
шаг не ломает установку: цепочка второго мнения просто идёт к следующему звену (Codex и далее).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ADAPTER = Path(__file__).resolve().parent / "copilot_adapter.py"
PROFILE = Path.home() / ".cache" / "ai_toolkit_copilot_profile"


def logged_in() -> bool:
    return PROFILE.is_dir() and any(PROFILE.iterdir())


def run(cmd: list, timeout: int = 600) -> bool:
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"    ! {cmd[0]}: {e}")
        return False
    if r.returncode != 0:
        print(f"    ! {' '.join(cmd[:4])}…: {(r.stderr or r.stdout).strip()[-300:]}")
    return r.returncode == 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    uv = shutil.which("uv")
    if a.login:
        if not uv:
            print("  [!] uv не найден: https://astral.sh/uv")
            return 0
        return subprocess.call([uv, "run", "--quiet", "--with", "playwright", "python", str(ADAPTER), "--login"])
    if not a.check:
        if not uv:
            print("  [!] uv не найден: M365 Copilot подключить нельзя, второе мнение пойдёт через Codex")
            return 0
        if run([uv, "run", "--quiet", "--with", "playwright", "python", "-m", "playwright", "install", "chromium"]):
            print("  [ok] браузер для Playwright готов")
        else:
            print("  [!] браузер не скачался (сеть, прокси?): повтори `python scripts/copilot_setup.py`")
    print("  [ok] вход в M365 Copilot выполнен" if logged_in() else
          "  [ ] вход в M365 Copilot не выполнен: `python scripts/copilot_setup.py --login` (откроется окно, войди рабочей учёткой)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
