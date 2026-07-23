# Запросы и ORM — оптимизация выборок

## CIBlockElement::GetList — правила
- Явный `select` — только нужные поля; не тащить все `PROPERTY_*` (каждое множественное свойство → JOIN/размножение строк).
- `filter` по индексируемым полям (`IBLOCK_ID`, `ACTIVE`, `SECTION_ID`, `ID`).
- Свойства пакетно (`GetPropertyValues`) либо `PROPERTY_X` в select только для показываемых.
- Счётчик — `SetRowCount`/лёгкий запрос, не выборка всех строк + `count()`.

```php
$res = CIBlockElement::GetList(
    ['SORT' => 'ASC', 'ID' => 'DESC'],
    ['IBLOCK_ID' => 5, 'ACTIVE' => 'Y', 'SECTION_ID' => $sid],  // по индексам
    false,
    ['nPageSize' => 20, 'iNumPage' => $page],
    ['ID', 'NAME', 'DETAIL_PAGE_URL', 'PROPERTY_PRICE']         // только нужное
);
while ($ob = $res->GetNextElement()) { $f = $ob->GetFields(); }
```
Анти-паттерн: `GetNext()` в цикле + внутри `GetProperty`/`GetList` по каждому элементу = **N+1**.

## D7 ORM (Bitrix\Main\ORM\Query)
```php
use Bitrix\Iblock\ElementTable;
$rows = ElementTable::getList([
    'select' => ['ID', 'NAME', 'IBLOCK' => 'IBLOCK.NAME'],   // join через точку
    'filter' => ['=ACTIVE' => 'Y', '=IBLOCK_ID' => 5],
    'order'  => ['ID' => 'DESC'],
    'limit'  => 20,
    'count_total' => true,
    'cache'  => ['ttl' => 3600, 'cache_joins' => true],       // кэш ORM-запроса
])->fetchAll();
```
Runtime-поля/агрегаты:
```php
use Bitrix\Main\ORM\Fields\ExpressionField;
$q = ElementTable::query()
    ->setSelect(['IBLOCK_ID', new ExpressionField('CNT', 'COUNT(%s)', 'ID')])
    ->setFilter(['=ACTIVE' => 'Y'])
    ->setGroup(['IBLOCK_ID']);
$result = $q->exec()->fetchAll();
```
`setCacheTtl(3600)` + `cacheJoins(true)` — кэш с join. `countTotal(true)` — total (на больших таблицах отдельный
`COUNT(*)` бывает дороже выборки → иногда приблизительный счётчик).

## N+1 — ловить и чинить
Ловить: панель отладки (число SQL) / xhprof (100× вызовов `CDatabase::Query`). Порог тревоги — десятки-сотни однотипных.
Чинить: собрать все ID → один запрос `IN(...)`; свойства пакетно (`GetPropertyValues`/ORM join); дерево разделов предзагрузить один раз.

## Прямой $DB->Query
Когда: массовые операции, тяжёлые агрегаты, batch-обновления. Безопасность: экранировать `$DB->ForSql($val)`/каст —
иначе SQL-инъекция. Не для того, что штатно кэшируется API (потеряешь тегированный сброс).
```php
global $DB;
$id = (int)$id; $name = $DB->ForSql($name);
$res = $DB->Query("SELECT ID, NAME FROM b_iblock_element WHERE IBLOCK_ID = {$id}");
```
