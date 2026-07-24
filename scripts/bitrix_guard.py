#!/usr/bin/env python3
"""bitrix_guard — детектор «обращение к БД в цикле» (N+1) в PHP-коде под Битрикс.

Ловит вызовы, порождающие запрос к БД, внутри while/for/foreach:
  CIBlockElement::GetList / ::GetByID / ->GetNextElement (внутри цикла по элементам),
  *Table::getList / ->getList,  $DB->Query,  ->GetProperty / ::GetPropertyValues.
Это прямой аналог bsl_guard.py из claude-1c-toolkit (там — Запрос…Выполнить() в Пока/Для).

Чистый Python (stdlib), кроссплатформенно. Используется pre-commit хуком и вручную:
  python scripts/bitrix_guard.py local/**/*.php
exit 1 при находках (печатает файл:строку), exit 0 если чисто.

Эвристика: находим заголовок цикла (while|for|foreach ...), затем по балансу фигурных скобок
определяем тело цикла и ищем в нём паттерны БД-вызовов. Строки/комментарии огрубляются.
Не претендует на 100% точность — цель поймать явный N+1 до прода; обойти разово: git commit --no-verify.
"""
import re
import sys

LOOP_RE = re.compile(r'\b(while|for|foreach)\b\s*\(', re.IGNORECASE)
DB_CALL_RE = re.compile(
    r'(::GetList\s*\(|->GetList\s*\(|::getList\s*\(|->getList\s*\('
    r'|\$DB\s*->\s*Query\s*\(|\$DB\s*->\s*Fetch\s*\(|->GetNextElement\s*\('
    # свойства/элементы поштучно — классический N+1 в Битрикс (и статически, и через объект)
    r'|::GetProperty\s*\(|->GetProperty\s*\('
    r'|::GetPropertyValues\s*\(|->GetPropertyValues\s*\('
    r'|::GetByID\s*\(|->GetByID\s*\('
    # ORM-хелперы поштучного получения
    r'|::getRow\s*\(|->getRow\s*\(|::getById\s*\(|->getById\s*\()',
)


def strip_noise(src: str) -> str:
    """Убрать содержимое строковых литералов и комментариев, сохранив длину/переводы строк,
    чтобы номера строк не поехали, а фигурные скобки внутри строк не ломали баланс."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        two = src[i:i + 2]
        if two == '//':
            j = src.find('\n', i)
            j = n if j == -1 else j
            out.append(' ' * (j - i)); i = j; continue
        if two == '/*':
            j = src.find('*/', i + 2)
            j = n if j == -1 else j + 2
            out.append(''.join(ch if ch == '\n' else ' ' for ch in src[i:j])); i = j; continue
        if two == '#[':  # attribute — не важно
            out.append(src[i]); i += 1; continue
        if c == '#':
            j = src.find('\n', i)
            j = n if j == -1 else j
            out.append(' ' * (j - i)); i = j; continue
        if c in ('"', "'"):
            q = c; j = i + 1
            while j < n:
                if src[j] == '\\':
                    j += 2; continue
                if src[j] == q:
                    j += 1; break
                j += 1
            out.append(''.join(ch if ch == '\n' else ' ' for ch in src[i:j])); i = j; continue
        out.append(c); i += 1
    return ''.join(out)


ALT_END = {"while": "endwhile", "for": "endfor", "foreach": "endforeach"}


def find_loop_bodies(clean: str):
    """Вернуть список (start_idx, end_idx) тел циклов по огрублённому исходнику.

    Поддерживаются ОБА синтаксиса:
      • фигурные скобки:      foreach (...) { ... }
      • альтернативный:       foreach (...): ... endforeach;
    Альтернативный доминирует в шаблонах компонентов Битрикс (template.php), где N+1 встречается
    чаще всего — без него детектор слеп именно там, где нужнее всего.
    """
    bodies = []
    for m in LOOP_RE.finditer(clean):
        kw = m.group(1).lower()
        # пройти условие цикла до закрывающей ')'
        p = m.end()
        depth = 1  # мы уже внутри первой '(' условия
        while p < len(clean) and depth > 0:
            if clean[p] == '(':
                depth += 1
            elif clean[p] == ')':
                depth -= 1
            p += 1
        while p < len(clean) and clean[p] in ' \t\r\n':
            p += 1
        if p >= len(clean):
            continue

        if clean[p] == '{':
            start = p + 1
            bdepth = 1
            p = start
            while p < len(clean) and bdepth > 0:
                if clean[p] == '{':
                    bdepth += 1
                elif clean[p] == '}':
                    bdepth -= 1
                p += 1
            bodies.append((start, p))
        elif clean[p] == ':':
            # альтернативный синтаксис: тело до соответствующего endforeach/endfor/endwhile
            start = p + 1
            end_kw = ALT_END.get(kw)
            if not end_kw:
                continue
            end_re = re.compile(r'\b' + end_kw + r'\b', re.IGNORECASE)
            em = end_re.search(clean, start)
            bodies.append((start, em.start() if em else len(clean)))
        # иначе — однострочный цикл без блока: пропускаем
    return bodies


def scan_source(src: str):
    """Вернуть список (номер строки, фрагмент) с БД-вызовом внутри тела цикла.

    Вложенные циклы дают перекрывающиеся тела → одна и та же находка попадалась несколько раз.
    Дедуплицируем по позиции. splitlines() считаем один раз (было O(n²) на больших файлах).
    """
    clean = strip_noise(src)
    lines = src.splitlines()
    seen = set()
    hits = []
    for (s, e) in find_loop_bodies(clean):
        for m in DB_CALL_RE.finditer(clean, s, e):
            if m.start() in seen:
                continue
            seen.add(m.start())
            line = clean.count('\n', 0, m.start()) + 1
            snippet = lines[line - 1].strip() if line - 1 < len(lines) else ''
            hits.append((line, snippet))
    return sorted(hits)


def main(argv):
    files = argv[1:]
    if not files:
        return 0
    found = False
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as fh:
                src = fh.read()
        except OSError:
            continue
        for (line, snippet) in scan_source(src):
            found = True
            print(f"{path}:{line}: [bitrix-guard] запрос к БД в цикле (N+1): {snippet}")
    if found:
        print("\nСоберите ID и сделайте один запрос IN(...), либо грузите свойства пакетно.")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
