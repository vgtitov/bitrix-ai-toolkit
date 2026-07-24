#!/usr/bin/env python3
"""checks_config — эффективный режим проверки с учётом опциональности.

Возвращает режим для проверки: off | warn | block. Источники (по приоритету):
  1. env BITRIX_AI_CHECKS (глобальный выключатель: off/warn/block)
  2. config/local/checks.toml  → [checks.<name>].mode или [mode].default
  3. config/checks.toml        → то же
  4. дефолт: warn (мягко, не блокирует)
Если [checks.<name>].enabled = false → off. Нет tomllib (Python <3.11) → работает по env + дефолту.

Использование (в хуках/скриптах):
  MODE=$(python3 scripts/checks_config.py n1_guard)   # off|warn|block
  # off → пропустить; warn → показать, не блокировать; block → блокировать при находках

Только стандартная библиотека. Никогда не падает — при любой ошибке возвращает 'warn' (или env).
"""
import os
import sys

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

VALID = {"off", "warn", "block"}
DEFAULT = "warn"


def _root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)  # каталог toolkit (родитель scripts/)


def _load(path):
    if not (tomllib and os.path.isfile(path)):
        return {}
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}


def effective_mode(check_name):
    # 1. env — глобальный выключатель, главнее всего
    env = os.environ.get("BITRIX_AI_CHECKS", "").strip().lower()
    if env in VALID:
        return env

    root = _root()
    # 2-3. локальный конфиг компании перекрывает базовый
    cfg = {}
    for rel in ("config/checks.toml", "config/local/checks.toml"):
        data = _load(os.path.join(root, rel))
        if data:
            cfg = _merge(cfg, data)

    if not cfg:
        return DEFAULT

    section = cfg.get("checks", {}).get(check_name, {})
    if section.get("enabled") is False:
        return "off"
    mode = section.get("mode") or cfg.get("mode", {}).get("default") or DEFAULT
    mode = str(mode).strip().lower()
    return mode if mode in VALID else DEFAULT


def _merge(a, b):
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "default"
    print(effective_mode(name))
