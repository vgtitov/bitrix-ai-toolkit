#!/usr/bin/env python3
"""Поставить git-хуки bitrix-ai-toolkit (ПО УМОЛЧАНИЮ — только в текущий репозиторий):
  - commit-msg — срезает соавторство/атрибуцию AI-инструментов из сообщений коммитов (по СТРУКТУРЕ
    строки — трейлер/attribution-глагол, не по списку имён — см. scripts/git-hooks/commit-msg);
  - pre-commit — bitrix-guard: блокирует staged *.php с обращением к БД в цикле (N+1). В чужих
    репозиториях (нет detector'а) молча пропускает.

Org-agnostic, идемпотентно, кроссплатформенно, только стандартная библиотека.
  - core.hooksPath: берётся существующий; если не задан — ставится ~/.git-global-hooks.
  - копирует scripts/git-hooks/* в этот каталог; чужой commit-msg НЕ затирает (предупреждает).

Запуск:  python scripts/install_git_hooks.py            # локально в этот репозиторий (безопасно)
Опции:   --global — поставить ГЛОБАЛЬНО (меняет core.hooksPath всей машины, отключит
         .git/hooks в остальных репозиториях: husky, pre-commit, lefthook)
"""
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MARKER = "claude-no-coauthor"
SRC = Path(__file__).resolve().parent / "git-hooks"
HOOKS = ("commit-msg", "pre-commit")


def gget(key):
    r = subprocess.run(["git", "config", "--global", "--get", key], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def gset(key, value):
    subprocess.run(["git", "config", "--global", key, value], capture_output=True, text=True)


def make_executable(p: Path):
    try:
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def copy_hook(name: str, dst_dir: Path):
    """Скопировать хук. ЧУЖОЙ существующий хук НИКОГДА не затираем (любой, не только commit-msg):
    в глобальном каталоге может лежать chain-хук или хук другого toolkit'а — перезапись его сломает."""
    src = SRC / name
    dst = dst_dir / name
    if dst.exists():
        try:
            existing = dst.read_text(encoding="utf-8", errors="replace")
        except OSError:
            existing = ""
        ours = MARKER in existing or "bitrix-guard" in existing
        if not ours:
            print(f"[!] {dst} уже существует и НЕ наш — НЕ затираю (чтобы не сломать чужой/chain-хук).")
            print(f"    Наш хук: {src}")
            print("    Варианты: 1) поставить локально в репозиторий:  python3 scripts/install_git_hooks.py --local")
            print("              2) если там chain-хук — локальной установки достаточно, он сам вызовет наш")
            return False
    shutil.copyfile(src, dst)
    make_executable(dst)
    print(f"[+] {name} → {dst}")
    return True


def main(argv):
    if not SRC.is_dir():
        print(f"[!] нет каталога с хуками: {SRC}", file=sys.stderr)
        return 1

    # ПО УМОЛЧАНИЮ — ЛОКАЛЬНО, в текущий репозиторий.
    # Глобальная установка меняет core.hooksPath на ВСЕЙ машине: git перестаёт видеть .git/hooks
    # во всех остальных репозиториях (husky, pre-commit framework, lefthook, корпоративные хуки
    # молча отключаются). Это слишком агрессивно для инструмента, который человек просто попробовал.
    # Глобально — только по явному флагу --global.
    global_install = "--global" in argv
    local = not global_install
    if local:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if top.returncode != 0:
            print("[!] не git-репозиторий", file=sys.stderr)
            return 1
        dst = Path(top.stdout.strip()) / ".git" / "hooks"
        dst.mkdir(parents=True, exist_ok=True)
        print(f"[i] локальная установка в {dst}")
    else:
        hooks_dir = gget("core.hooksPath")
        if hooks_dir:
            dst = Path(os.path.expanduser(hooks_dir))
            print(f"[i] core.hooksPath уже задан: {dst}")
        else:
            dst = Path.home() / ".git-global-hooks"
            print("[!] ВНИМАНИЕ: глобальная установка меняет core.hooksPath для ВСЕЙ машины.")
            print("    Git перестанет использовать .git/hooks в ОСТАЛЬНЫХ репозиториях —")
            print("    husky, pre-commit framework, lefthook и корпоративные хуки отключатся.")
            print("    Отменить: git config --global --unset core.hooksPath")
            gset("core.hooksPath", dst.as_posix())
            print(f"[i] core.hooksPath → {dst}")
        dst.mkdir(parents=True, exist_ok=True)

    all_installed = True
    for h in HOOKS:
        all_installed = copy_hook(h, dst) and all_installed

    if not all_installed:
        print("[!] hooks установлены частично; устрани конфликт и повтори.", file=sys.stderr)
        return 2
    print("[ok] git-хуки установлены. Обойти разово: git commit --no-verify")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
