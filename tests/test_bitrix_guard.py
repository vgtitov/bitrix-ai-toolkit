#!/usr/bin/env python3
"""Функциональные тесты детектора bitrix_guard (N+1 «запрос в цикле»).
DISCIPLINE_ALLOW_TEST_EDIT — тесты продукта scripts/bitrix_guard.py.

Запуск:  python3 tests/test_bitrix_guard.py     (exit 0 = все прошли)
Или через pytest, если установлен:  pytest tests/test_bitrix_guard.py
Только стандартная библиотека — работает в onboard-самотесте без зависимостей.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import bitrix_guard  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")


def _hits(name):
    with open(os.path.join(FIX, name), "r", encoding="utf-8") as fh:
        return bitrix_guard.scan_source(fh.read())


def test_bad_detected():
    """В n1_bad.php детектор находит запросы к БД в цикле."""
    hits = _hits("n1_bad.php")
    assert len(hits) >= 2, f"ожидались находки N+1, получено {len(hits)}"
    joined = " ".join(s for _, s in hits)
    assert "GetByID" in joined or "GetProperty" in joined or "getList" in joined, joined


def test_good_clean():
    """В n1_good.php ложных срабатываний нет (GetNext по результату, строки, один запрос)."""
    hits = _hits("n1_good.php")
    assert hits == [], f"ложные срабатывания: {hits}"


def test_string_literal_not_flagged():
    """Слово GetList внутри строкового литерала не должно триггерить."""
    hits = bitrix_guard.scan_source('<?php $x = "call GetList here"; foreach($a as $b){ echo $b; }')
    assert hits == [], hits


def test_exit_code():
    """CLI: exit 1 на плохом файле, exit 0 на хорошем."""
    assert bitrix_guard.main(["prog", os.path.join(FIX, "n1_bad.php")]) == 1
    assert bitrix_guard.main(["prog", os.path.join(FIX, "n1_good.php")]) == 0


# DISCIPLINE_ALLOW_TEST_EDIT — добавлены НОВЫЕ тесты на дефекты, найденные adversarial-ревью
def test_alt_syntax_detected():
    """Альтернативный синтаксис (foreach: … endforeach) — доминирует в шаблонах компонентов Битрикс,
    где N+1 встречается чаще всего. Детектор был к нему слеп."""
    hits = _hits("n1_alt_syntax.php")
    assert len(hits) >= 3, f"ожидались находки во всех трёх циклах, получено {len(hits)}"


def test_no_duplicate_hits():
    """Вложенные циклы дают перекрывающиеся тела — находка не должна дублироваться."""
    src = '<?php\nforeach($a as $x){ foreach($b as $y){ $r = CIBlockElement::GetList([]); } }\n'
    hits = bitrix_guard.scan_source(src)
    assert len(hits) == 1, f"ожидалась 1 находка, получено {len(hits)}: {hits}"


# DISCIPLINE_ALLOW_TEST_EDIT — новый тест на скрытый дефект (heredoc прятал реальный N+1)
def test_heredoc_does_not_hide_findings():
    """Непарная фигурная скобка в heredoc/nowdoc сдвигала баланс и «закрывала» тело цикла раньше —
    реальный N+1 после неё МОЛЧА пропускался (ложноотрицательное, самый опасный класс)."""
    hits = _hits("n1_heredoc.php")
    assert len(hits) == 2, f"оба N+1 должны быть найдены, получено {len(hits)}: {hits}"


def _run():
    tests = [test_bad_detected, test_good_clean, test_string_literal_not_flagged, test_exit_code,
             test_alt_syntax_detected, test_no_duplicate_hits, test_heredoc_does_not_hide_findings]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} прошли")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
