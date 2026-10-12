#!/usr/bin/env python3
"""ponytail_setup: не затирает чужие настройки, идемпотентен, без CLI ничего не ставит.

Запуск:  python3 tests/test_ponytail_setup.py   или   pytest tests/test_ponytail_setup.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ponytail_setup as ps  # noqa: E402


def test_all():
    saved = dict(os.environ)
    try:
        _run()
    finally:
        os.environ.clear()
        os.environ.update(saved)


def _run():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        os.environ.pop("BITRIX_ROLE", None)
        os.environ.pop("ONEC_ACTIVE_PROFILE", None)
        os.environ.update(XDG_CONFIG_HOME=str(t / "xdg"), CLAUDE_CONFIG_DIR=str(t / "claude"),
                          CODEX_HOME=str(t / "codex"), PATH=str(t / "empty"))

        # выключенный руками плагин распознаётся
        (t / "claude").mkdir()
        (t / "claude" / "settings.json").write_text('{"enabledPlugins": {"ponytail@ponytail": false}}')
        assert ps.claude_disabled()
        (t / "codex").mkdir()
        (t / "codex" / "config.toml").write_text('[plugins."ponytail@ponytail"]\nenabled = false\n\n[x]\ny = 1\n')
        assert ps.codex_disabled()
        (t / "codex" / "config.toml").write_text('[plugins."ponytail@ponytail"]\nenabled = true\n[x]\nenabled = false\n')
        assert not ps.codex_disabled()

        # без установленного плагина режим не пишется
        cfg = t / "xdg" / "ponytail" / "config.json"
        ps.main(["--mode", "lite"])
        assert not cfg.exists()

        # фальшивый claude: «установка» успешна; codex по-прежнему выключен руками
        (t / "empty").mkdir()
        fake = t / "empty" / "claude"
        fake.write_text(f"#!/bin/sh\necho \"$@\" >> {t}/calls\nexit 0\n")
        fake.chmod(0o755)
        (t / "claude" / "settings.json").write_text("{}")

        # режим пишется один раз, чужие ключи и выбор пользователя сохраняются
        cfg.parent.mkdir(parents=True)
        cfg.write_text('{"hideStatus": true}')
        ps.main(["--mode", "lite"])
        assert json.loads(cfg.read_text()) == {"hideStatus": True, "defaultMode": "lite"}
        ps.main(["--mode", "full"])
        assert json.loads(cfg.read_text())["defaultMode"] == "lite"

        # режим по роли: аналитик -> off, остальные и без роли -> lite; явный --mode главнее
        assert ps.mode_for_role("analyst") == "off"
        assert ps.mode_for_role("franchise") == ps.mode_for_role("") == ps.mode_for_role("developer") == "lite"

        # выключил через /ponytail default off: обновление плагин не трогает
        cfg.write_text('{"defaultMode": "off"}')
        (t / "calls").unlink()
        ps.main([])
        assert not (t / "calls").exists()

        # правило: блок дописывается, повторный запуск его заменяет, а не дублирует
        proj = t / "proj"
        proj.mkdir()
        (proj / "AGENTS.md").write_text("# мои правила\n")
        ps.main(["--no-plugin", "--project", str(proj)])
        ps.main(["--no-plugin", "--project", str(proj)])
        text = (proj / "AGENTS.md").read_text()
        assert text.startswith("# мои правила\n") and text.count(ps.BEGIN) == 1
        assert "Ponytail" in text

        # роль аналитика: его документ в AGENTS.md проекта не сокращается, правило только дописывается
        passport = "# Паспорт задачи\n\n" + "".join(f"## Раздел {i}\nТребование {i}: подробное описание.\n\n" for i in range(50))
        (proj / "AGENTS.md").write_text(passport)
        ps.main(["--no-plugin", "--project", str(proj)])
        assert (proj / "AGENTS.md").read_text().startswith(passport)
        block = ps.rule_block()
        assert "касаются только кода" in block and "Документы не сокращаются" in block
        assert "Для аналитика" in block
        for role in ("analyst", "tester"):
            skill = next((ps.ROOT / "core" / "skills").glob(f"*-{role}")) / "SKILL.md"
            assert "Ponytail здесь не сокращает" in skill.read_text(encoding="utf-8"), skill

        # повреждённые метки не трогаем, несуществующий каталог не валит
        (proj / "AGENTS.md").write_text(ps.BEGIN + "\nстарое\n")
        ps.main(["--no-plugin", "--project", str(proj)])
        assert (proj / "AGENTS.md").read_text() == ps.BEGIN + "\nстарое\n"
        ps.main(["--no-plugin", "--project", str(t / "nope")])

        # каталог самого набора не трогаем
        before = (ps.ROOT / "AGENTS.md").read_bytes()
        ps.main(["--no-plugin", "--project", str(ps.ROOT)])
        assert (ps.ROOT / "AGENTS.md").read_bytes() == before


if __name__ == "__main__":
    test_all()
    print("OK: ponytail_setup")
