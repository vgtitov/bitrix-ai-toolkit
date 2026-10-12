#!/usr/bin/env python3
"""second_opinion и codex_setup: цепочка по порядку, пропуск ненастроенного, без ПД в модель без обучения.

Запуск:  python3 tests/test_second_opinion.py   или   pytest tests/test_second_opinion.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_setup as cs  # noqa: E402
import second_opinion as so  # noqa: E402


def test_chain_order():
    calls = []

    def mk(name, ans):
        def f(prompt):
            calls.append(name)
            return ans
        return f
    no_codex = lambda *a, **k: None  # noqa: E731
    assert so.ask("q", chain=(("a", mk("a", None)), ("b", mk("b", "ответ"))), codex=no_codex) == ("b", "ответ")
    assert calls == ["a", "b"]
    assert so.ask("q", chain=(("a", mk("a", None)),), codex=no_codex) == ("", "")
    assert so.ask("q", chain=(), codex=lambda *a, **k: "codex ok") == ("codex", "codex ok")


def test_pii_blocks_every_link():
    hit = lambda *a, **k: "ответ"  # noqa: E731
    for text in ("пиши ivan@example.com", "звони +375 29 123-45-67", "+1 (415) 555-2671", "+44 20 7946 0958",
                 "пиши иван@почта.рф", "8 029 123 45 67"):
        who, why = so.ask(text, chain=(("a", hit),), codex=hit)
        assert who == "" and "--allow-pii" in why, text
    assert so.ask("+44 20 7946 0958", chain=(), codex=hit, allow_pii=True)[0] == "codex"
    assert so.ask("версия 8.3.27.1606, задача DEV1C-2476", chain=(), codex=hit)[0] == "codex"


def test_split_diff():
    diff = "".join(f"diff --git a/f{i} b/f{i}\n" + "x" * 50 + "\n" for i in range(10))
    parts = so.split_diff(diff, limit=200)
    assert "".join(parts) == diff and all(len(p) <= 200 for p in parts)


def test_notrain_gates():
    saved = dict(os.environ)
    try:
        os.environ.pop("OPENROUTER_API_KEY", None)
        assert so.notrain("q") is None                     # нет ключа
        os.environ["OPENROUTER_API_KEY"] = "k"
        os.environ.pop("AI_TOOLKIT_NOTRAIN", None)
        assert so.notrain("q") is None                     # нет явного разрешения
        os.environ["AI_TOOLKIT_NOTRAIN"] = "1"
        os.environ["AI_TOOLKIT_NOTRAIN_MODEL"] = "x/model:free"
        import importlib
        importlib.reload(so)
        assert so.notrain("q") is None                     # бесплатная модель запрещена
        os.environ.pop("AI_TOOLKIT_NOTRAIN_MODEL")
        importlib.reload(so)
        os.environ.pop("AI_TOOLKIT_COPILOT_CMD", None)
        assert so.copilot("q") is None                     # Copilot не настроен
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_collect_diff_sees_worktree_and_merge():
    import subprocess as sp
    with tempfile.TemporaryDirectory() as t:
        g = lambda *a: sp.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=t,  # noqa: E731
                              capture_output=True, text=True, check=True).stdout
        g("init", "-q", "-b", "main")
        Path(t, "a.txt").write_text("1\n")
        g("add", "-A"); g("commit", "-qm", "base")
        g("checkout", "-qb", "f"); Path(t, "b.txt").write_text("2\n"); g("add", "-A"); g("commit", "-qm", "f")
        g("checkout", "-q", "main"); g("merge", "-q", "--no-ff", "f", "-m", "merge")
        assert "b.txt" in so.collect_diff(Path(t), None, "HEAD")       # merge — к первому родителю
        Path(t, "a.txt").write_text("changed\n")                       # незакоммиченная правка
        assert "changed" in so.collect_diff(Path(t), "HEAD", None)


def test_codex_setup_respects_opt_out():
    saved = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory() as t:
            os.environ["CLAUDE_CONFIG_DIR"] = t
            assert not cs.plugin_disabled()
            (Path(t) / "settings.json").write_text(json.dumps({"enabledPlugins": {cs.PLUGIN: False}}))
            assert cs.plugin_disabled()
    finally:
        os.environ.clear()
        os.environ.update(saved)


if __name__ == "__main__":
    test_chain_order()
    test_pii_blocks_every_link()
    test_split_diff()
    test_notrain_gates()
    test_collect_diff_sees_worktree_and_merge()
    test_codex_setup_respects_opt_out()
    print("OK: second_opinion")
