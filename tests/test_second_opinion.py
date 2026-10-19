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
        def f(prompt, files=()):
            calls.append(name)
            return ans
        return f
    no_codex = lambda *a, **k: None  # noqa: E731
    assert so.ask("q", chain=(("a", mk("a", None)), ("b", mk("b", "ответ"))), codex=no_codex) == ("b", "ответ")
    assert calls == ["a", "b"]
    assert so.ask("q", chain=(("a", mk("a", None)),), codex=no_codex) == ("", "")
    assert so.ask("q", chain=(), codex=lambda *a, **k: "codex ok") == ("codex", "codex ok")


def test_pii_goes_only_to_trusted_assistant():
    saved = dict(os.environ)
    try:
        seen = []
        trusted = lambda p, files=(): seen.append(p) or "ответ"  # noqa: E731
        outside = lambda p, files=(): seen.append("ВНЕШНИЙ") or "ответ"  # noqa: E731
        codex_called = []
        codex = lambda *a, **k: codex_called.append(1) or "codex"  # noqa: E731
        chain = (("copilot", trusted), ("notrain", outside))
        pii_texts = ("пиши ivan@example.com", "звони +375 29 123-45-67", "+1 (415) 555-2671", "+44 20 7946 0958",
                     "пиши иван@почта.рф", "8 029 123 45 67", "(415) 555-2671", "029 123-45-67",
                     "8(029)123-45-67", "80291234567", "+375291234567")
        os.environ.pop("AI_TOOLKIT_COPILOT_CMD", None)
        for text in pii_texts:                              # доверенного нет — отказ, никому не уходит
            who, why = so.ask(text, chain=chain, codex=codex)
            assert who == "" and "доверенный" in why, text
        assert not codex_called and not seen
        os.environ["AI_TOOLKIT_COPILOT_CMD"] = "x"
        for text in pii_texts:                              # есть доверенный — только ему, текст без правок
            seen.clear()
            assert so.ask(text, chain=chain, codex=codex)[0] == "copilot", text
            assert seen == [text]
        assert not codex_called
        silent = (("copilot", lambda p, files=(): None), ("notrain", outside))   # доверенный молчит — Codex всё равно нельзя
        for text in pii_texts:
            seen.clear()
            assert so.ask(text, chain=silent, codex=codex) == ("", ""), text
        assert not codex_called and not seen
        for text in ("версия 8.3.27.1606, задача DEV1C-2476", "дата 2026-10-12", "строки 120-135"):
            assert not so.has_pii(text), text
        assert so.ask("без данных", chain=(), codex=codex)[0] == "codex"
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_risk_order_and_files():
    saved = dict(os.environ)
    os.environ.pop("AI_TOOLKIT_COPILOT_CMD", None)
    calls = []

    def mk(n):
        return lambda p, files=(): calls.append((n, tuple(files))) or None
    chain = (("copilot", mk("copilot")), ("notrain", mk("notrain")))
    cdx = lambda *a, **k: calls.append(("codex", ())) or None  # noqa: E731
    for risk, want in (("critical", ["codex", "copilot", "notrain"]), ("normal", ["copilot", "codex", "notrain"]),
                       ("low", ["copilot", "notrain"])):
        calls.clear()
        so.ask("q", chain=chain, codex=cdx, risk=risk)
        assert [c[0] for c in calls] == want, risk
    with tempfile.TemporaryDirectory() as t:
        ok = Path(t) / "a.md"
        ok.write_text("текст без данных")
        bad = Path(t) / "b.md"
        bad.write_text("пиши ivan@example.com")
        calls.clear()
        assert so.ask("q", chain=chain, codex=cdx, files=[str(ok)], risk="low")[0] == ""
        assert calls[0][1] == (str(ok.resolve()),)           # вложение дошло до звена
        os.environ.pop("AI_TOOLKIT_COPILOT_CMD", None)
        who, why = so.ask("q", chain=chain, codex=cdx, files=[str(bad)])
        assert who == "" and "доверенный" in why              # файл с ПД без доверенного ассистента не уходит никому
        assert so.ask("q", chain=chain, codex=cdx, files=[str(Path(t) / "нет.md")])[1].startswith("вложения нет")
    os.environ.clear()
    os.environ.update(saved)


def test_copilot_default_needs_login():
    saved = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory() as t:
            os.environ.pop("AI_TOOLKIT_COPILOT_CMD", None)
            os.environ["HOME"] = os.environ["USERPROFILE"] = t
            import importlib
            importlib.reload(so)
            assert so.copilot_cmd() == ""                     # вход не выполнен — звена нет
            prof = Path(t) / ".cache" / "ai_toolkit_copilot_profile"
            prof.mkdir(parents=True)
            (prof / "Default").write_text("x")
            if so.shutil.which("uv"):
                assert "copilot_adapter.py" in so.copilot_cmd()   # вошли — адаптер по умолчанию
            os.environ["AI_TOOLKIT_COPILOT_CMD"] = "mycmd"
            assert so.copilot_cmd() == "mycmd"                # явная команда главнее
    finally:
        os.environ.clear()
        os.environ.update(saved)
        import importlib
        importlib.reload(so)


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
        os.environ["AI_TOOLKIT_NOTRAIN_MODEL"] = "openrouter/free"
        importlib.reload(so)
        assert so.notrain("q") is None
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
        Path(t, "new.txt").write_text("не добавлен\n")
        assert "new.txt" in so.collect_diff(Path(t), "HEAD", None)          # новый файл виден
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
    test_pii_goes_only_to_trusted_assistant()
    test_risk_order_and_files()
    test_copilot_default_needs_login()
    test_split_diff()
    test_notrain_gates()
    test_collect_diff_sees_worktree_and_merge()
    test_codex_setup_respects_opt_out()
    print("OK: second_opinion")
