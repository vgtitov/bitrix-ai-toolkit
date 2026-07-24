<?php
// ФИКСТУРА (DISCIPLINE_ALLOW_TEST_EDIT): heredoc/nowdoc с НЕПАРНЫМИ фигурными скобками.
// Без обработки heredoc такая скобка сдвигает баланс и "закрывает" тело цикла раньше времени —
// реальный N+1 после неё МОЛЧА пропускается (ложноотрицательное, самый опасный класс).

foreach ($ids as $id) {
    $tpl = <<<TXT
шаблон с закрывающей скобкой } внутри текста
TXT;
    $r = CIBlockElement::GetList([], ['ID' => $id]);   // ← ДОЛЖЕН быть найден
}

foreach ($ids as $id) {
    $sql = <<<'NOWDOC'
nowdoc: тут { тоже непарная
NOWDOC;
    $p = CIBlockElement::GetProperty(5, $id);          // ← ДОЛЖЕН быть найден
}
