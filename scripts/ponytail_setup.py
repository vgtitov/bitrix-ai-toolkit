#!/usr/bin/env python3
"""Необязательно: Ponytail (github.com/DietrichGebert/ponytail, MIT) и правило «сначала проверь, что уже есть».

Установщик набора вызывает этот скрипт ТОЛЬКО по явному флагу --with-ponytail; без флага ничего
не меняется. Скрипт ставит плагин в Claude Code и Codex и, если передан --project, дописывает
правило из core/optional/check-existing-first.md в AGENTS.md проекта (блок между метками,
повторный запуск заменяет блок). Идемпотентно: штатные CLI `claude plugin` и `codex plugin`
сами дописывают свои настройки и не трогают чужие. Если пользователь выключил Ponytail
руками (enabled = false), установщик его не включает обратно.

  python scripts/ponytail_setup.py                 # режим lite (по умолчанию, для команд)
  python scripts/ponytail_setup.py --mode full     # одиночная работа
  python scripts/ponytail_setup.py --project DIR   # плюс правило в DIR/AGENTS.md
  python scripts/ponytail_setup.py --no-plugin --project DIR   # только правило
  python scripts/ponytail_setup.py --dry-run       # только показать, что будет сделано

Режим пишется в ~/.config/ponytail/config.json (defaultMode), только если его там ещё нет.
Сменить потом: команда `/ponytail default full` в агенте или PONYTAIL_DEFAULT_MODE.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = "ponytail@ponytail"
REPO = "DietrichGebert/ponytail"
MODES = ("off", "lite", "full", "ultra")
ROOT = Path(__file__).resolve().parents[1]
RULE = ROOT / "core" / "optional" / "check-existing-first.md"
BEGIN, END = "<!-- check-existing-first:begin -->", "<!-- check-existing-first:end -->"


def claude_disabled() -> bool:
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    try:
        data = json.loads((base / "settings.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    return (data.get("enabledPlugins") or {}).get(PLUGIN) is False


def codex_disabled() -> bool:
    base = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    try:
        text = (base / "config.toml").read_text(encoding="utf-8")
    except OSError:
        return False
    # ponytail: регэксп вместо tomllib — работает и на Python < 3.11
    m = re.search(r'^\[plugins\."ponytail@ponytail"\]\s*\n((?:(?!\[).*\n?)*)', text, re.M)
    return bool(m and re.search(r"^\s*enabled\s*=\s*false\b", m.group(1), re.M))


def ponytail_config_path() -> Path:
    # тот же порядок, что в самом Ponytail (hooks/ponytail-config.js)
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]) / "ponytail" / "config.json"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "ponytail" / "config.json"
    return Path.home() / ".config" / "ponytail" / "config.json"


def set_default_mode(mode: str, dry: bool) -> str:
    path = ponytail_config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            return f"{path}: не JSON-объект, не трогаю"
    except FileNotFoundError:
        data = {}
    except (OSError, ValueError):
        return f"{path}: не читается, не трогаю"
    if data.get("defaultMode"):
        return f"режим уже задан: {data['defaultMode']} ({path}), не трогаю"
    data["defaultMode"] = mode
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"режим по умолчанию: {mode} ({path})"


def write_rule(project: Path, dry: bool) -> str:
    project = project.resolve()
    if project == ROOT:
        return "правило: проект не указан (это каталог набора), пропуск; передай --project <каталог проекта>"
    target = project / "AGENTS.md"
    old = target.read_text(encoding="utf-8") if target.exists() else ""
    block = f"{BEGIN}\n{RULE.read_text(encoding='utf-8').strip()}\n{END}\n"
    if BEGIN in old and END in old:
        head, rest = old.split(BEGIN, 1)
        new = head + block + rest.split(END, 1)[1].lstrip("\n")
    else:
        new = old + ("\n" if old and not old.endswith("\n") else "") + ("\n" if old else "") + block
    if not dry and new != old:
        target.write_text(new, encoding="utf-8")
    hint = ""
    claude_md = project / "CLAUDE.md"
    if claude_md.exists() and "@AGENTS.md" not in claude_md.read_text(encoding="utf-8", errors="ignore"):
        hint = "; Claude Code читает его, только если в CLAUDE.md есть строка @AGENTS.md"
    return f"правило «сначала проверь, что уже есть» -> {target}{hint}"


def run(cmd: list[str], dry: bool) -> bool:
    if dry:
        print("    $ " + " ".join(cmd))
        return True
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"    ! {cmd[0]}: {e}")
        return False
    if r.returncode != 0:
        print(f"    ! {' '.join(cmd)}: {(r.stderr or r.stdout).strip()[:300]}")
    return r.returncode == 0


AGENTS = {
    "claude": (claude_disabled, [["plugin", "marketplace", "add", REPO], ["plugin", "install", PLUGIN]]),
    "codex": (codex_disabled, [["plugin", "marketplace", "add", REPO], ["plugin", "add", PLUGIN]]),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=MODES, default="lite", help="режим по умолчанию (lite — команда, full — одиночка)")
    ap.add_argument("--project", type=Path, help="каталог проекта: дописать правило в его AGENTS.md")
    ap.add_argument("--no-plugin", action="store_true", help="плагин не ставить, только правило")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    if a.project:
        print("  [ok] " + write_rule(a.project, a.dry_run))
    if a.no_plugin:
        return 0
    for name, (disabled, steps) in AGENTS.items():
        exe = shutil.which(name)
        if not exe:
            print(f"  [-] {name}: CLI не найден, пропуск")
        elif disabled():
            print(f"  [=] {name}: {PLUGIN} выключен пользователем, не включаю")
        elif all(run([exe, *s], a.dry_run) for s in steps):
            print(f"  [ok] {name}: {PLUGIN}")
        else:
            print(f"  [!] {name}: не поставился (сеть?), вручную: {name} " + " ; ".join(" ".join(s) for s in steps))
    print("  [ok] " + set_default_mode(a.mode, a.dry_run))
    if not shutil.which("node"):
        print("  [!] node не найден: хуки Ponytail молчат, скиллы /ponytail работают")
    return 0  # установка Ponytail необязательна и не должна валить онбординг


if __name__ == "__main__":
    sys.exit(main())
