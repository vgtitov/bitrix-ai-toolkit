<?php
// ФИКСТУРА (DISCIPLINE_ALLOW_TEST_EDIT): альтернативный синтаксис циклов — доминирует в шаблонах
// компонентов Битрикс (template.php, component_epilog.php), где N+1 встречается чаще всего.
// Детектор ОБЯЗАН это ловить наравне с фигурными скобками.
?>
<?php foreach ($arResult["ITEMS"] as $item): ?>
    <?php $props = CIBlockElement::GetProperty($item["ID"], 0); ?>
    <div><?= $item["NAME"] ?></div>
<?php endforeach; ?>

<?php for ($i = 0; $i < 10; $i++): ?>
    <?php $el = CIBlockElement::GetByID($ids[$i])->GetNext(); ?>
<?php endfor; ?>

<?php while ($row = $res->Fetch()): ?>
    <?php $more = \Bitrix\Iblock\ElementTable::getList(['filter' => ['ID' => $row['ID']]]); ?>
<?php endwhile; ?>
