<?php
// ФИКСТУРА (DISCIPLINE_ALLOW_TEST_EDIT): анти-паттерны, которые ДОЛЖНЫ ловиться (bitrix-guard + ast-grep).

// N+1: запрос в цикле
foreach ($ids as $id) {
    $el = CIBlockElement::GetByID($id)->GetNext();
    $props = CIBlockElement::GetProperty(5, $id);
}

// N+1: getList в while
while ($row = $res->fetch()) {
    $more = \Bitrix\Iblock\ElementTable::getList(['filter' => ['ID' => $row['ID']]]);
}

// SQL-инъекция: конкатенация в $DB->Query
global $DB;
$r = $DB->Query("SELECT * FROM b_iblock_element WHERE ID = " . $userInput);

// Старое API вместо Loader::includeModule
CModule::IncludeModule("iblock");
