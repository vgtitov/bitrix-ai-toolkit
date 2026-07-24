#!/usr/bin/env python3
"""init_project — сгенерировать phpstan.neon ПОД РЕАЛЬНЫЙ проект.

Зачем: статический конфиг-образец неизбежно ссылается на пути, которых в конкретном проекте нет
(ядро не там, нет orm_annotations, не установлены расширения) — и PHPStan падает ещё до анализа.
Этот скрипт смотрит, что РЕАЛЬНО есть на диске, и пишет конфиг только из существующих путей.

Что учитывает:
  • путь к ядру Битрикс (bitrix/modules или из version-stack.toml [bitrix].core_path)
  • правлено ли ядро (core_modified) — тогда анализ по фактическому коду
  • КАСТОМНЫЕ СЛОИ ([[custom_layers]]) — свой фреймворк подрядчика со своим namespace
  • где лежит свой код (local/classes, local/modules, src)
  • установлены ли расширения PHPStan

Запуск (из корня проекта Битрикс):
    python3 <toolkit>/scripts/init_project.py              # показать, что нашёл, и записать phpstan.neon
    python3 <toolkit>/scripts/init_project.py --dry-run    # только показать
    python3 <toolkit>/scripts/init_project.py --level 6
"""
import argparse
import os
import sys

try:
    import tomllib
except ImportError:
    tomllib = None

CORE_MODULES = ["main", "iblock", "catalog", "sale", "highloadblock", "currency"]
OWN_CODE = ["local/classes", "local/modules", "local/php_interface", "src"]


def toolkit_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_version_stack(project):
    """version-stack.toml: сначала из проекта, потом из toolkit (config/ и config/local/)."""
    if tomllib is None:
        return {}
    for path in (
        os.path.join(project, "config", "version-stack.toml"),
        os.path.join(toolkit_root(), "config", "local", "version-stack.toml"),
        os.path.join(toolkit_root(), "config", "version-stack.toml"),
    ):
        if os.path.isfile(path):
            try:
                with open(path, "rb") as fh:
                    return tomllib.load(fh)
            except Exception:
                continue
    return {}


def detect(project, cfg):
    found = {"core_dirs": [], "own": [], "custom_layers": [], "notes": []}

    core_path = (cfg.get("bitrix", {}) or {}).get("core_path") or "bitrix/modules"
    core_abs = os.path.join(project, core_path)
    if os.path.isdir(core_abs):
        for m in CORE_MODULES:
            lib = os.path.join(core_path, m, "lib")
            if os.path.isdir(os.path.join(project, lib)):
                found["core_dirs"].append(lib)
        if not found["core_dirs"] and os.path.isdir(core_abs):
            found["core_dirs"].append(core_path)
    else:
        found["notes"].append(
            f"ядро не найдено по пути '{core_path}' — анализ будет без него "
            "(PHPStan не сможет сказать «метода нет в этой версии»). "
            "Укажи core_path в config/version-stack.toml или положи ядро рядом."
        )

    if (cfg.get("bitrix", {}) or {}).get("core_modified"):
        found["notes"].append("ЯДРО ПРАВЛЕНО (core_modified=true): сигнатуры берутся по фактическому коду.")

    for layer in cfg.get("custom_layers", []) or []:
        p = layer.get("path")
        if p and os.path.isdir(os.path.join(project, p)):
            found["custom_layers"].append({
                "name": layer.get("name", "custom"),
                "path": p,
                "namespace": layer.get("namespace", ""),
                "priority": layer.get("priority", ""),
            })
        elif p:
            found["notes"].append(f"кастомный слой '{layer.get('name')}' указан, но путь '{p}' не найден")

    for p in OWN_CODE:
        if os.path.isdir(os.path.join(project, p)):
            found["own"].append(p)

    if tomllib is None:
        found["notes"].append(
            "Python < 3.11: модуля tomllib нет → version-stack.toml НЕ ПРОЧИТАН. "
            "Кастомные слои и путь к ядру не будут учтены. Обнови Python до 3.11+ "
            "или задай пути вручную в сгенерированном конфиге."
        )

    ext_installed = os.path.isdir(os.path.join(project, "vendor", "phpstan", "extension-installer"))
    found["extension_installer"] = ext_installed
    if not ext_installed:
        found["notes"].append(
            "phpstan/extension-installer не установлен — расширения (deprecation-rules и др.) "
            "не подключатся: composer require --dev phpstan/extension-installer"
        )
    return found


def render(found, level):
    lines = [
        "# phpstan.neon — сгенерирован init_project.py под ЭТОТ проект.",
        "# Включены только реально существующие пути (иначе PHPStan падает до анализа).",
        "# Расширения подключаются автоматически через phpstan/extension-installer.",
        "",
        "parameters:",
        f"    level: {level}",
        "",
        "    paths:",
    ]
    if found["own"]:
        for p in found["own"]:
            lines.append(f"        - {p}")
    else:
        # Ничего не нашли — НЕ выдумываем путь: несуществующий paths уронит PHPStan
        # («Path ... does not exist») ровно так же, как это делал статический образец.
        lines.append("        # ⚠️ Свой код не найден (искали: " + ", ".join(OWN_CODE) + ").")
        lines.append("        # Укажи путь вручную, иначе PHPStan упадёт на несуществующем каталоге:")
        lines.append("        # - local/classes")

    if found["custom_layers"]:
        lines += ["", "    # Кастомные слои (свой фреймворк) — ВИДНЫ анализатору, но не анализируются:",
                  "    # сигнатуры оттуда настоящие, а чужой код чинить не наша задача.", "    scanDirectories:"]
        for l in found["custom_layers"]:
            lines.append(f"        - {l['path']}          # {l['name']} {l['namespace']}".rstrip())
        for d in found["core_dirs"]:
            lines.append(f"        - {d}")
    elif found["core_dirs"]:
        lines += ["", "    # Ядро Битрикс — видно, но не анализируется (ловит «метода нет в этой версии»):",
                  "    scanDirectories:"]
        for d in found["core_dirs"]:
            lines.append(f"        - {d}")

    lines += [
        "",
        "    excludePaths:",
        "        - '*/vendor/*'",
        "        - '*/bitrix/*'",
        "        - '*/upload/*'",
        "",
        "    reportUnmatchedIgnoredErrors: false",
        "    treatPhpDocTypesAsCertain: false",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Сгенерировать phpstan.neon под реальный проект")
    ap.add_argument("--dry-run", action="store_true", help="только показать, не писать файл")
    ap.add_argument("--level", type=int, default=6, help="уровень PHPStan для своего кода (по умолчанию 6)")
    ap.add_argument("--out", default="phpstan.neon")
    args = ap.parse_args(argv)

    project = os.getcwd()
    cfg = load_version_stack(project)
    found = detect(project, cfg)

    print("Найдено в проекте:")
    print(f"  свой код:        {', '.join(found['own']) or '— (не найден local/classes, src)'}")
    print(f"  ядро Битрикс:    {len(found['core_dirs'])} каталог(ов)" if found["core_dirs"] else "  ядро Битрикс:    НЕ НАЙДЕНО")
    if found["custom_layers"]:
        for l in found["custom_layers"]:
            print(f"  кастомный слой:  {l['name']} → {l['path']}  ns={l['namespace'] or '?'} ({l['priority'] or 'приоритет не задан'})")
    else:
        print("  кастомный слой:  не настроен ([[custom_layers]] в version-stack.toml)")
    for n in found["notes"]:
        print(f"  ⚠ {n}")

    content = render(found, args.level)
    if args.dry_run:
        print("\n--- phpstan.neon (dry-run) ---\n")
        print(content)
        return 0

    out = os.path.join(project, args.out)
    if os.path.exists(out):
        print(f"\n[!] {args.out} уже существует — НЕ перезаписываю. Смотри вывод --dry-run и слей руками.")
        return 0
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"\n[+] записан {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
