"""Тесты commit-msg хука (scripts/git-hooks/commit-msg).

Фильтр — СТРУКТУРНЫЙ (git-трейлер или фраза с attribution-глаголом), а не по списку имён
AI-инструментов: список всегда неполный, и бэйр-упоминание инструмента как ТЕМЫ коммита
("Скилл интеграции с Copilot") не должно резаться наравне с реальной атрибуцией.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path


HOOK = Path(__file__).parents[1] / "scripts" / "git-hooks" / "commit-msg"
INSTALLER = HOOK.parents[1] / "install_git_hooks.py"
ONBOARD = HOOK.parents[2] / "onboard" / "install.sh"


def installer_module():
    spec = importlib.util.spec_from_file_location("bitrix_install_git_hooks", INSTALLER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_hook(tmp_path: Path, message: str) -> str:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text(message, encoding="utf-8")
    result = subprocess.run(["sh", str(HOOK), str(message_file)], check=False)
    assert result.returncode == 0
    return message_file.read_text(encoding="utf-8")


def test_hook_keeps_installer_ownership_marker() -> None:
    assert installer_module().MARKER in HOOK.read_text(encoding="utf-8")


def test_hook_removes_new_ai_system_names(tmp_path: Path) -> None:
    # Структурная атрибуция (трейлер + "generated with") — снимается независимо от того,
    # что имя инструмента (Codex/ChatGPT) нигде не перечислено денлистом.
    message = (
        "Исправить импорт\n"
        "Generated with Codex\n"
        "Co-Authored-By: ChatGPT <bot@openai.com>\n"
    )
    assert run_hook(tmp_path, message) == "Исправить импорт\n"


def test_hook_removes_attribution_from_tool_not_in_any_denylist(tmp_path: Path) -> None:
    # Ключевой тест структурного подхода: "FutureNeuroAssistant" нигде не перечислен —
    # фильтр обязан снять атрибуцию по ФОРМЕ строки, а не по знанию имени инструмента.
    message = (
        "Исправить обработку очереди\n"
        "Co-Authored-By: FutureNeuroAssistant Zeta <bot@futureneuro.example>\n"
        "Generated with FutureNeuroAssistant Zeta\n"
        "Обычная заметка\n"
    )
    assert run_hook(tmp_path, message) == "Исправить обработку очереди\nОбычная заметка\n"


def test_hook_preserves_bare_tool_mention_as_topic(tmp_path: Path) -> None:
    # Регрессия исходного бага: коммит ПРО AI-инструмент как ТЕМУ (не атрибуция от его лица)
    # не должен резаться только потому, что в строке встретилось имя copilot/cursor/claude.
    message = "Скилл интеграции с M365 Copilot\n\nПроверил через Cursor.\n"
    assert run_hook(tmp_path, message) == message


def test_hook_preserves_ordinary_text_containing_ai_letters(tmp_path: Path) -> None:
    # Регрессия: старая версия резала ЛЮБУЮ строку с отдельным словом "ai"/"ии" — а этот
    # toolkit сам называется bitrix-AI-toolkit и постоянно упоминает "AI"/"ИИ" как тему.
    message = "Добавить skill для AI-агента\n\nЛестница проверки maintainable и repairable.\n"
    assert run_hook(tmp_path, message) == message


def test_installer_refreshes_owned_hook_after_toolkit_update(tmp_path: Path) -> None:
    target = tmp_path / "commit-msg"
    target.write_text("#!/bin/sh\n# claude-no-coauthor\n# old version\n", encoding="utf-8")

    installer_module().copy_hook("commit-msg", tmp_path)

    assert target.read_text(encoding="utf-8") == HOOK.read_text(encoding="utf-8")


def test_copy_hook_reports_foreign_hook_conflict(tmp_path: Path) -> None:
    target = tmp_path / "commit-msg"
    original = "#!/bin/sh\n# foreign dispatcher\n"
    target.write_text(original, encoding="utf-8")

    copied = installer_module().copy_hook("commit-msg", tmp_path)

    assert copied is False
    assert target.read_text(encoding="utf-8") == original


def test_onboarding_does_not_swallow_hook_installer_failure() -> None:
    text = ONBOARD.read_text(encoding="utf-8")
    hook_line = next(
        line for line in text.splitlines()
        if "python3 scripts/install_git_hooks.py" in line
    )

    assert "||" not in hook_line


def test_hook_preserves_message_when_filter_command_fails(tmp_path: Path) -> None:
    message = tmp_path / "COMMIT_EDITMSG"
    original = "Исправить импорт\n"
    message.write_text(original, encoding="utf-8")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_grep = fake_bin / "grep"
    fake_grep.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
    fake_grep.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    result = subprocess.run(
        ["sh", str(HOOK), str(message)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode != 0
    assert message.read_text(encoding="utf-8") == original
