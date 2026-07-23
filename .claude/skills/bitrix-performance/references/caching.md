# Кэширование Битрикс — слои, код, подводные камни

Правильный кэш даёт 10-100× по времени генерации. На каталоге 50K: без кэша 0.8-1.77с/стр, с кэшем < 0.2с (Intervolga).

## 1. Кэш компонента (самый частый)
Параметры: `CACHE_TIME` (TTL сек; 0 = бесконечно, сброс по тегам), `CACHE_TYPE` (A авто / Y всегда / N выкл),
`CACHE_GROUPS` (Y — группы юзера в ключ, если контент зависит от прав; N — общий, быстрее).

```php
// component.php
if ($this->startResultCache()) {              // false = валидный кэш уже есть
    $this->arResult['ITEMS'] = getExpensiveData();
    $this->setResultCacheKeys(['ITEMS', 'ID']); // ТОЛЬКО нужные шаблону ключи
    $this->includeComponentTemplate();
}
```

Низкоуровнево (произвольный участок):
```php
$obCache = new CPHPCache();
$cacheId = 'my_key_'.$param;
if ($obCache->InitCache(3600, $cacheId, '/my/cache/path/')) {
    $vars = $obCache->GetVars();
} elseif ($obCache->StartDataCache()) {
    $vars = ['data' => heavy()];
    $obCache->EndDataCache($vars);
}
```

**Ошибки:** приватные данные при `CACHE_GROUPS=N` (утечка) · `setResultCacheKeys` со всем arResult (раздутый I/O) ·
кэш вложенного компонента при закэшированном родителе (двойная работа — вложенным `CACHE_TYPE=N`) ·
ключ не учитывает все параметры (страница/сортировка/фильтр) → «чужой» кэш.

## 2. D7 `Bitrix\Main\Data\Cache`
```php
use Bitrix\Main\Data\Cache;
$cache = Cache::createInstance();
if ($cache->initCache(3600, 'mykey', '/mypath/')) {
    $vars = $cache->getVars();
} elseif ($cache->startDataCache()) {
    $vars = ['data' => expensive()];
    // $cache->abortDataCache();  // отменить запись при исключении
    $cache->endDataCache($vars);
}
```

## 3. Тегированный кэш — автосброс по инфоблоку
```php
use Bitrix\Main\Application; use Bitrix\Main\Data\Cache;
$cache = Cache::createInstance();
$tagged = Application::getInstance()->getTaggedCache();
if ($cache->initCache($ttl, $key, $path)) {
    $vars = $cache->getVars();
} elseif ($cache->startDataCache()) {
    $tagged->startTagCache($path);
    $tagged->registerTag('iblock_id_17');   // привязка к инфоблоку 17
    $vars = ['items' => load()];
    $cache->endDataCache($vars);
    $tagged->endTagCache();
}
```
Старый API: `$CACHE_MANAGER->StartTagCache($path); RegisterTag('iblock_id_17'); EndTagCache();`
Сброс: `$CACHE_MANAGER->ClearByTag('iblock_id_17');`
Стандартные теги: `iblock_id_{ID}`, `blog_post_{ID}`, `forum_{id}`, `sonet_group_{id}`. Компоненты каталога сами
регистрируют/сбрасывают `iblock_id_*` на `OnAfterIBlockElement*`. **Требует включённого управляемого кэша.**
**HL-блоки тег НЕ сбрасывают — чисти вручную из обработчика события.**

## 4. Управляемый кэш (лёгкий ключ-значение)
```php
$mc = Application::getInstance()->getManagedCache();
if ($mc->read(3600, 'my_key')) { $res = $mc->get('my_key'); }
else { $res = expensive(); $mc->set('my_key', $res); }
```

## 5. Композит (Composite)
Мгновенная статика из кэша + AJAX-догрузка динамики (корзина, авторизация). Улучшает Core Web Vitals.
**Подводные камни:** только GET (POST/формы не композитятся) · динамические области ОБЯЗАТЕЛЬНО оборачивать
(`\Bitrix\Main\Composite\Engine`/`BX.Composite`), иначе персональные данные в общий кэш = утечка · ломается от
`RestartBuffer()`, незакрытого вывода, ошибок PHP · отладка: расширение «Bitrix Composite Notifier» + панель статистики.
Док: docs.1c-bitrix.ru/pages/performance/composite-site.html

## 6. Хранилище кэша и меню
Файлы (`bitrix/cache/`) на нагрузке упираются в диск/inode → переключить на **Redis/memcached** (`.settings.php` секция
`cache`). Redis стабильнее (memcached вытесняет по LRU), поддерживает кластер. Меню: `CACHE_SELECTED_ITEMS=N` на больших
сайтах (иначе отдельный кэш на каждую страницу), активный пункт — через JS/CSS.

**Что кэшировать:** списки/детальные каталога, меню, статические инфоблоки, тяжёлые агрегаты, ответы внешних API.
**Что НЕ общим кэшем:** корзину, авторизацию, персональные цены/скидки — только композит-динамика или AJAX.
