#!/usr/bin/env python3
"""Ponytail (github.com/DietrichGebert/ponytail, MIT) в Claude Code и Codex + правило «сначала проверь, что уже есть».

Установщик и обновление набора вызывают скрипт по умолчанию; отключить: флаг --no-ponytail установщика.
Идемпотентно: штатные CLI `claude plugin` и `codex plugin` сами дописывают свои настройки и не
трогают чужие. Не ставит, если пользователь выключил Ponytail: enabled = false у плагина или
defaultMode "off" в ~/.config/ponytail/config.json (команда `/ponytail default off`).

Правило берётся из core/AGENTS.md (блок между метками check-existing-first). Ponytail касается
только кода: документы, постановки, ТЗ, тест-кейсы не сокращаются (сказано в самом правиле).
С --project блок дописывается в AGENTS.md проекта, повторный запуск заменяет блок.

  python scripts/ponytail_setup.py                 # режим по роли: analyst -> off, остальные -> lite
  python scripts/ponytail_setup.py --role analyst  # роль явно (иначе BITRIX_ROLE / ONEC_ACTIVE_PROFILE)
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
RULE_SRC = ROOT / "core" / "AGENTS.md"
BEGIN, END = "<!-- check-existing-first:begin -->", "<!-- check-existing-first:end -->"
# какой режим записал сам установщик: так off аналитика по роли не путается с отказом человека
SET_BY_KEY = "aiToolkitDefault"


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
    try:
        import tomllib
        try:
            return (tomllib.loads(text).get("plugins") or {}).get(PLUGIN, {}).get("enabled") is False
        except tomllib.TOMLDecodeError:
            return False
    except ImportError:  # Python < 3.11: грубая проверка регэкспом
        pass
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
    if "defaultMode" in data:
        return f"режим уже задан: {data['defaultMode']} ({path}), не трогаю"
    data["defaultMode"] = mode
    data[SET_BY_KEY] = mode
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"режим по умолчанию: {mode} ({path})"


def mode_for_role(role: str) -> str:
    # аналитику Ponytail по умолчанию выключен: его результат — текст; правило «только код» действует при любой роли
    return "off" if role.strip().lower() == "analyst" else "lite"


def rule_block() -> str:
    src = RULE_SRC.read_text(encoding="utf-8")
    if src.count(BEGIN) != 1 or src.count(END) != 1 or src.find(END) < src.find(BEGIN):
        raise ValueError("метки повреждены или отсутствуют")
    return BEGIN + src.split(BEGIN, 1)[1].split(END, 1)[0] + END + "\n"


def user_turned_off() -> bool:
    # off, который записал сам установщик по роли (аналитик), — не отказ: плагин можно доставить
    # в агент, появившийся позже; режим при этом остаётся off. Отказ — off, выбранный человеком.
    try:
        data = json.loads(ponytail_config_path().read_text(encoding="utf-8-sig"))
        return data.get("defaultMode") == "off" and data.get(SET_BY_KEY) != "off"
    except (OSError, ValueError, AttributeError):
        return False


def write_rule(project: Path, dry: bool) -> str:
    project = project.resolve()
    if project == ROOT:
        return "правило: проект не указан (это каталог набора), пропуск; передай --project <каталог проекта>"
    if not project.is_dir():
        return f"правило: каталога {project} нет, пропуск"
    target = project / "AGENTS.md"
    try:
        old = target.read_text(encoding="utf-8") if target.exists() else ""
    except (OSError, UnicodeError) as e:
        return f"правило: {target} не читается ({e}), не трогаю"
    try:
        block = rule_block()
    except (OSError, IndexError, ValueError) as e:
        return f"правило: в {RULE_SRC} нет целого блока check-existing-first ({e}), пропуск"
    if old.count(BEGIN) != old.count(END) or old.count(BEGIN) > 1 or old.find(END) < old.find(BEGIN):
        return f"правило: метки check-existing-first в {target} повреждены, не трогаю; поправь руками"
    if BEGIN in old:
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
    ap.add_argument("--mode", choices=MODES, help="режим по умолчанию; без флага — по роли: analyst → off, иначе lite")
    ap.add_argument("--role", default=os.environ.get("BITRIX_ROLE") or os.environ.get("ONEC_ACTIVE_PROFILE") or "",
                    help="роль/профиль (по умолчанию из BITRIX_ROLE или ONEC_ACTIVE_PROFILE)")
    ap.add_argument("--project", type=Path, help="каталог проекта: дописать правило в его AGENTS.md")
    ap.add_argument("--no-plugin", action="store_true", help="плагин не ставить, только правило")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    a.mode = a.mode or mode_for_role(a.role)

    if a.project:
        print("  [ok] " + write_rule(a.project, a.dry_run))
    if a.no_plugin:
        return 0
    installed = False
    if user_turned_off():
        print("  [=] Ponytail выключен пользователем (defaultMode off), плагин не трогаю")
        return 0
    for name, (disabled, steps) in AGENTS.items():
        exe = shutil.which(name)
        if not exe:
            print(f"  [-] {name}: CLI не найден, пропуск")
        elif disabled():
            print(f"  [=] {name}: {PLUGIN} выключен пользователем, не включаю")
        elif all(run([exe, *s], a.dry_run) for s in steps):
            print(f"  [ok] {name}: {PLUGIN}")
            installed = True
        else:
            print(f"  [!] {name}: не поставился (сеть?), вручную: {name} " + " ; ".join(" ".join(s) for s in steps))
    if installed:
        print("  [ok] " + set_default_mode(a.mode, a.dry_run))
    if not shutil.which("node"):
        print("  [!] node не найден: хуки Ponytail молчат, скиллы /ponytail работают")
    return 0  # установка Ponytail необязательна и не должна валить онбординг


if __name__ == "__main__":
    sys.exit(main())
