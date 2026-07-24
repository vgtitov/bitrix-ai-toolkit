#!/usr/bin/env python3
"""changed_files — какие файлы проверять.

ПРОФИЛЬ «ГРЯЗНЫЙ ЛЕГАСИ» (`[scope].changed_only = true`, дефолт): только изменённые файлы (git diff).
Это инженерный ответ на «линтер завалит красным весь проект»: легаси не трогается вообще,
разработчик отвечает только за то, к чему сам прикоснулся.

`changed_only = false` → отдаёт пути из `[scope].paths` целиком.

Использование:
    python3 scripts/changed_files.py                # список файлов (по одному в строке)
    python3 scripts/changed_files.py --ext php      # только .php
    python3 scripts/changed_files.py --base HEAD~5  # своя база сравнения

Только стандартная библиотека. Никогда не падает: нет git / не репозиторий → отдаёт scope.paths.
"""
import argparse
import fnmatch
import os
import subprocess
import sys

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None


def _root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_cfg():
    """checks.toml + config/local/checks.toml (локальный перекрывает базовый)."""
    cfg = {}
    if tomllib is None:
        return cfg
    for rel in ("config/checks.toml", "config/local/checks.toml"):
        path = os.path.join(_root(), rel)
        if os.path.isfile(path):
            try:
                with open(path, "rb") as fh:
                    data = tomllib.load(fh)
                cfg = _merge(cfg, data)
            except Exception:
                pass
    return cfg


def _merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _git(args, cwd):
    try:
        r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def changed(base, cwd):
    """Изменённые файлы относительно base. staged = --cached, иначе diff с base."""
    if base == "staged":
        out = _git(["diff", "--cached", "--name-only", "--diff-filter=ACM"], cwd)
    else:
        out = _git(["diff", "--name-only", "--diff-filter=ACM", base + "...HEAD"], cwd) \
            or _git(["diff", "--name-only", "--diff-filter=ACM", base], cwd)
    return [line.strip() for line in out.splitlines() if line.strip()]


def walk(paths, cwd):
    files = []
    for p in paths:
        full = os.path.join(cwd, p)
        if os.path.isfile(full):
            files.append(p)
        for dirpath, _dirnames, filenames in os.walk(full):
            for fn in filenames:
                files.append(os.path.relpath(os.path.join(dirpath, fn), cwd))
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description="Файлы для проверки (diff или scope)")
    ap.add_argument("--ext", help="фильтр по расширению, напр. php")
    ap.add_argument("--base", help="база сравнения (перекрывает конфиг)")
    ap.add_argument("--all", action="store_true", help="принудительно весь scope, игнорируя changed_only")
    args = ap.parse_args(argv)

    cwd = os.getcwd()
    cfg = _load_cfg()
    scope = cfg.get("scope", {})
    paths = scope.get("paths") or ["."]
    exclude = scope.get("exclude") or []
    changed_only = scope.get("changed_only", True)
    base = args.base or scope.get("diff_base", "staged")

    is_git = bool(_git(["rev-parse", "--is-inside-work-tree"], cwd).strip())

    if args.all or not changed_only:
        files = walk(paths, cwd)
    elif not is_git:
        # НЕ git-репозиторий → diff взять неоткуда. Молча отдать пусто нельзя: проверки бы
        # «прошли», не проверив ничего. Поэтому фолбэк на обход scope.paths (как обещает докстринг).
        print("changed_files: не git-репозиторий — проверяю scope.paths целиком", file=sys.stderr)
        files = walk(paths, cwd)
    else:
        files = changed(base, cwd)
        if not files:                      # git есть, изменений нет → проверять нечего (это норма)
            return 0
        # оставляем только то, что попадает в scope.paths
        if paths and paths != ["."]:
            files = [f for f in files if any(f.startswith(p.rstrip("/") + "/") or f == p for p in paths)]

    if args.ext:
        ext = "." + args.ext.lstrip(".")
        files = [f for f in files if f.lower().endswith(ext.lower())]

    for pat in exclude:
        files = [f for f in files if not fnmatch.fnmatch("/" + f, pat) and not fnmatch.fnmatch(f, pat)]

    files = [f for f in files if os.path.isfile(os.path.join(cwd, f))]
    for f in files:
        print(f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
