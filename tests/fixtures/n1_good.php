<?php
// ФИКСТУРА (DISCIPLINE_ALLOW_TEST_EDIT): корректный код — детектор НЕ должен ложно срабатывать.

// Один запрос по массиву ID (правильно, не N+1) + явный лимит навигации.
// DISCIPLINE_ALLOW_TEST_EDIT: добавлен nTopCount — эталон «хорошего кода» должен показывать
// и отсутствие N+1, и ограничение выборки (без него правило getlist-without-limit срабатывало
// справедливо, и фикстура противоречила самой себе).
$res = CIBlockElement::GetList([], ['ID' => $ids, 'IBLOCK_ID' => 5], false, ['nTopCount' => 100], ['ID', 'NAME']);
$out = [];
while ($el = $res->GetNext()) {
    $out[] = $el;   // GetNext по УЖЕ выбранному результату — не запрос в цикле
}

// Слово GetList в строке не должно триггерить
$label = "используйте GetList с явным select";

// Безопасный запрос — параметр экранирован (не конкатенация сырого ввода)
global $DB;
$id = (int)$userInput;
$r = $DB->Query("SELECT NAME FROM b_iblock_element WHERE ID = {$id}");

// Современное подключение модуля
\Bitrix\Main\Loader::includeModule('iblock');
