#!/usr/bin/env python3
"""discipline_gate: три проверки текущего хода, режимы, идемпотентная установка.

Запуск:  python3 tests/test_discipline_gate.py   или   pytest tests/test_discipline_gate.py
"""
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import discipline_gate as dg  # noqa: E402


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def tool(name, _id="t", **inp):
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "id": _id, "name": name, "input": inp}]}}


def result(_id="t", error=False):
    return {"type": "user", "message": {"role": "user",
            "content": [{"type": "tool_result", "tool_use_id": _id, "content": "ok", "is_error": error}]}}


def say(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def test_decide():
    edit = tool("Edit", file_path="src/CommonModules/Мой/Ext/Module.bsl")
    # код без проверки
    assert dg.decide(dg.current_turn([user("поправь"), edit, result(), say("Готово")])) == dg.MSG_CODE
    # код и BSL LS
    turn = [user("поправь"), edit, result(), tool("Bash", command="python scripts/bsl_guard.py x.bsl"),
            result(), say("Готово, проверка прошла")]
    assert dg.decide(dg.current_turn(turn)) == ""
    # проверка из ПРОШЛОГО хода не засчитывается
    old = [user("раньше"), tool("Bash", command="pytest -q"), result(), say("ok")]
    assert dg.decide(dg.current_turn(old + [user("поправь"), edit, result(), say("Готово")])) == dg.MSG_CODE
    # правка тестов — не код продукта
    assert dg.decide(dg.current_turn([user("x"), tool("Write", file_path="tests/test_a.py"), result(),
                                      say("Готово")])) == ""
    # EDT MCP
    assert dg.decide(dg.current_turn([user("x"), tool("mcp__edt__write_module_source", path="M"), result(),
                                      say("Сделал")])) == dg.MSG_CODE
    # обещание без исполнения
    assert dg.decide(dg.current_turn([user("x"), say("Понял. Сейчас сделаю выгрузку.")])) == dg.MSG_PROMISE
    # обещание, за которым вызов инструмента, — не обещание
    assert dg.decide(dg.current_turn([user("x"), say("Сейчас сделаю"), tool("Read", file_path="a.md")])) == ""
    # не-код: «готово» без файла и источников после работы
    work = [user("разбери"), tool("Read", file_path="a.md"), result(), tool("Grep", pattern="x"), result()]
    assert dg.decide(dg.current_turn(work + [say("Готово, всё разобрал")])) == dg.MSG_NONDEV
    assert dg.decide(dg.current_turn(work + [say("Готово, вывод по docs/a.md")])) == ""
    assert dg.decide(dg.current_turn(work + [tool("Write", file_path="out/разбор.md"), result(),
                                             say("Готово")])) == ""
    # упавшая проверка не засчитывается; каталог test/ у обычного кода — это код
    assert dg.decide(dg.current_turn([user("x"), edit, result(), tool("Bash", _id="p", command="pytest -q"),
                                      result("p", error=True), say("Готово")])) == dg.MSG_CODE
    assert dg._is_code("src/test/service.py") and not dg._is_code("src/OrderTest.php")
    assert dg._is_code("tools/latest.py") and dg._is_code("Contest.bsl")
    assert not dg._is_code("tests/fixtures/a.bsl") and not dg._is_code("web/cart.spec.ts")
    # чтение слова pytest — не проверка; запуск через cd && uv run — проверка
    for cmd, ok in (("echo pytest", False), ("grep -r pytest README.md", False), ("cat pytest.log", False),
                    ("cd tests && uv run --with pytest python -m pytest -q", True), ("FOO=1 bsl-ls --check x", True)):
        turn = [user("x"), edit, result(), tool("Bash", command=cmd), result(), say("Готово")]
        assert (dg.decide(dg.current_turn(turn)) == "") is ok, cmd
    # текст и вызов инструмента в одном ответе — не обещание
    both = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": "Сейчас сделаю"}, {"type": "tool_use", "id": "z", "name": "Read", "input": {}}]}}
    assert dg.decide(dg.current_turn([user("x"), both])) == ""
    # запись результата с ошибкой не засчитывается
    assert dg.decide(dg.current_turn(work + [tool("Write", _id="w", file_path="out/r.md"), result("w", error=True),
                                             say("Готово")])) == dg.MSG_NONDEV
    # вежливость и короткий разговор не трогаем
    assert dg.decide(dg.current_turn([user("привет"), say("Готов помочь")])) == ""


def _run_hook(transcript, env):
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "t.jsonl"
        p.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in transcript) + "\n", encoding="utf-8")
        saved_in, saved_out, saved_env = sys.stdin, sys.stdout, dict(os.environ)
        sys.stdin, sys.stdout = io.StringIO(json.dumps({"transcript_path": str(p)})), io.StringIO()
        os.environ.update(env)
        try:
            assert dg.hook() == 0
            return sys.stdout.getvalue()
        finally:
            out = sys.stdout.getvalue()
            sys.stdin, sys.stdout = saved_in, saved_out
            os.environ.clear()
            os.environ.update(saved_env)


def test_modes():
    bad = [user("x"), tool("Edit", file_path="a.bsl"), result(), say("Готово")]
    assert json.loads(_run_hook(bad, {"AI_TOOLKIT_DISCIPLINE": "warn"})) == {"systemMessage": dg.MSG_CODE}
    assert json.loads(_run_hook(bad, {"AI_TOOLKIT_DISCIPLINE": "enforce"}))["decision"] == "block"
    assert _run_hook(bad, {"AI_TOOLKIT_DISCIPLINE": "off"}) == ""


def test_install():
    saved = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory() as t:
            os.environ["CLAUDE_CONFIG_DIR"] = t
            cfg = Path(t) / "settings.json"
            cfg.write_text(json.dumps({"model": "x", "hooks": {"Stop": [{"hooks": [
                {"type": "command", "command": "чужой хук"}]}]}}), encoding="utf-8")
            dg.install()
            dg.install()                                   # повтор не плодит записи
            data = json.loads(cfg.read_text(encoding="utf-8"))
            cmds = [h["command"] for g in data["hooks"]["Stop"] for h in g["hooks"]]
            assert data["model"] == "x" and "чужой хук" in cmds
            assert sum(dg.MARK in c for c in cmds) == 1
            dg.install(remove=True)
            cmds = [h["command"] for g in json.loads(cfg.read_text(encoding="utf-8"))["hooks"]["Stop"]
                    for h in g["hooks"]]
            assert cmds == ["чужой хук"]
            # человек выключил — install не включает
            cfg.write_text(json.dumps({"env": {"AI_TOOLKIT_DISCIPLINE": "off"}}), encoding="utf-8")
            dg.install()
            assert "hooks" not in json.loads(cfg.read_text(encoding="utf-8"))
            # битый JSON не трогаем
            cfg.write_text("{не json", encoding="utf-8")
            dg.install()
            assert cfg.read_text(encoding="utf-8") == "{не json"
    finally:
        os.environ.clear()
        os.environ.update(saved)


if __name__ == "__main__":
    test_decide()
    test_modes()
    test_install()
    print("OK: discipline_gate")
