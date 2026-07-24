# Архитектура PHP-приложения под Битрикс

## Слои и раскладка
```
Presentation   /local/components/**, /local/templates/**, Main\Engine\Controller (ajax/rest)
   ↓ Command/Query DTO
Application    Local\<Ctx>\Application\  — UseCase/Handler, DTO, транзакции, оркестрация
   ↓ интерфейсы портов
Domain         Local\<Ctx>\Domain\       — Entity, VO, доменные сервисы, ИНТЕРФЕЙСЫ репозиториев, исключения
   ↑ реализация портов
Infrastructure Local\<Ctx>\Infrastructure\ — репозитории на CIBlockElement/ORM, шлюзы к API, кэш
```
```
local/
  classes/                 # PSR-4 "Local\" → composer.json
    Catalog/{Domain,Application,Infrastructure}/…
  php_interface/init.php   # ТОЛЬКО регистрация: autoload + подписки на события
  components/local/…       # тонкие компоненты
  modules/local.catalog/   # если нужен модуль (свои таблицы, options, install)
```

**Железное правило:** зависимости направлены внутрь. `Domain` не знает про `Bitrix\`, `C*`-классы, `$_REQUEST`,
`$APPLICATION`. Проверяется грепом и **Deptrac** (`qossmic/deptrac`) в CI, а не «на честном слове».

## Anti-Corruption Layer над легаси — ЦЕНТРАЛЬНЫЙ приём
Порт (домен, чистый PHP):
```php
interface ProductRepository {
    /** @throws ProductNotFound */
    public function byId(ProductId $id): Product;
    /** @param list<ProductId> $ids @return array<int, Product> */
    public function byIds(array $ids): array;
}
```
Адаптер (инфраструктура — только здесь живёт `CIBlockElement`):
```php
final class IblockProductRepository implements ProductRepository {
    public function __construct(private readonly int $iblockId, private readonly ProductMapper $mapper) {}

    public function byIds(array $ids): array {
        if ($ids === []) return [];
        $rows = \CIBlockElement::GetList([], [
            'IBLOCK_ID' => $this->iblockId, 'ACTIVE' => 'Y',
            'ID' => array_map(static fn(ProductId $id) => $id->value, $ids),   // ОДИН запрос, без N+1
        ], false, false, ['ID','NAME','CODE','PROPERTY_ARTICLE']);             // явный select
        $out = [];
        while ($row = $rows->Fetch()) { $p = $this->mapper->toDomain($row); $out[$p->id()->value] = $p; }
        return $out;
    }
}
```
Что даёт в Битрикс: домен тестируется **без ядра** (мс вместо минут) · переезд `CIBlockElement` → D7 ORM/HL/внешний
сервис = правка ОДНОГО класса · «два поколения API» не текут по проекту · версионные различия ядра локализованы.

**Маппер — отдельный класс** (`toDomain(array $row): Product` / `toRow()`): не мешать «достать из БД» и «собрать объект».
Там же строки Битрикса превращаются в VO и enum'ы.

## DI в Битрикс — три уровня
**0. Конструкторы.** 90% пользы: зависимости через `__construct`, внутри — никаких `::getInstance()`.

**1. `\Bitrix\Main\DI\ServiceLocator`** (main 20.5.400+, **реализует PSR-11**). Регистрация в
`/bitrix/.settings_extra.php` или `.settings.php` своего модуля:
```php
'services' => ['value' => [
    'local.catalog.productRepository' => [
        'className' => \Local\Catalog\Infrastructure\Iblock\IblockProductRepository::class,
        'constructorParams' => static fn(): array => [(int)Option::get('local.catalog','IBLOCK_ID'), new ProductMapper()],
    ],
    \Local\Catalog\Domain\ProductRepository::class => [   // алиас интерфейс → реализация
        'constructor' => static fn() => ServiceLocator::getInstance()->get('local.catalog.productRepository'),
    ],
], 'readonly' => true],
```
> **КЛЮЧЕВОЕ ПРАВИЛО:** ServiceLocator дёргается **только в composition root** (`component.php`, экшен контроллера,
> обработчик события, агент, cli). Ниже по стеку — только конструкторная инъекция. `ServiceLocator::getInstance()->get()`
> внутри доменного/прикладного сервиса — **баг архитектуры**, а не стиль.

**2. Внешний контейнер** (symfony/di, php-di) — когда >40–50 сервисов, нужен автоварайринг/теги/декораторы.
Обязательно **скомпилированный/задампленный** контейнер, иначе сборка графа на каждом хите съест выигрыш кэша.
Мост: в `init.php` строим контейнер и регистрируем сервисы в `ServiceLocator` через `addInstanceLazy()` — единый PSR-11.

`[проверить по ядру]` Автоварайринг ServiceLocator работает не во всех версиях → грепнуть
`bitrix/modules/main/lib/di/servicelocator.php` своей версии.

## Когда НЕ усложнять — критерии глубины
| Задача | Глубина | Что делать |
|---|---|---|
| Вёрстка, поле в вывод, сортировка | **0 слоёв** | `result_modifier.php`/шаблон. Классы не заводить |
| Одна операция, одна сущность, нет правил (≈до 100 строк) | **1 слой** | Один сервис в `/local/classes` + вызов из компонента |
| Бизнес-правила, ≥2 источника данных, нужен тест | **2–3 слоя** | UseCase + интерфейс репозитория + адаптер |
| Деньги/остатки/скидки/статусы, интеграции, долгая жизнь | **полный** | Domain+Application+Infrastructure+ACL+тесты+ADR |
| Одноразовый скрипт миграции | **0** | Процедурно, но с транзакцией и логом |

Стоп-сигналы «слишком»: слой `Application` только проксирует репозиторий → лишний · у интерфейса одна реализация и он
не нужен для теста → лишний · DTO повторяет entity 1:1 и не пересекает границу процесса → лишний.
**Но:** трогаем деньги/заказы/остатки → тест обязателен → интерфейс репозитория обязателен. Не обсуждается.

**Разная глубина в одном проекте — норма, а не непоследовательность.**

## Строительные блоки
| Блок | Признак «сделано верно» | Битрикс |
|---|---|---|
| **Value Object** | нельзя создать невалидным, сравнение по значению | `Money`, `Sku`, `Phone`. В кэш — массивы, не объекты |
| **Entity** | инварианты внутри, нет публичных сеттеров | `Order`, `Product`. **Не** наследник `DataManager` |
| **DTO** | нет логики, `readonly public` | `$arParams` → `ShowCatalogQuery` |
| **Repository** | домен не знает о SQL/инфоблоках | адаптеры на `ElementTable`/`CIBlockElement`/`Sale\Order` |
| **Domain Service** | без состояния, без I/O | `PriceCalculator`, `DiscountPolicy` |
| **UseCase/Action** | один публичный `__invoke`/`handle`, вход — Command | зовётся и из компонента, и из Controller |
| **Specification** | комбинируется and/or/not | фильтры каталога → массив `filter` в адаптере |

## Полезные паттерны (битрикс-привязка)
**Adapter** — главный паттерн проекта (всё легаси за адаптером) · **Strategy** — доставки/оплаты/скидки вместо `if/elseif`
· **Decorator** — кэш/логи/ретраи (`CachedProductRepository` оборачивает репозиторий; **кэш не внутри репозитория**) ·
**Factory** — сборка `Order` из корзины · **Null Object** — `GuestUser`, `NoDiscount` · **Command+Handler** — один сценарий
из компонента/ajax/агента/cli без копипаста.

```php
final class CachedProductRepository implements ProductRepository {
    public function byId(ProductId $id): Product {
        $cache = Cache::createInstance();
        if ($cache->initCache($this->ttl, 'product_'.$id->value, '/local/catalog'))
            return $this->inner->hydrate($cache->getVars()['row']);
        $cache->startDataCache();
        $product = $this->inner->byId($id);
        $tagged = Application::getInstance()->getTaggedCache();
        $tagged->startTagCache('/local/catalog');
        $tagged->registerTag('iblock_id_'.$this->iblockId);
        $tagged->endTagCache();
        $cache->endDataCache(['row' => $product->toArray()]);   // МАССИВ, не объект
        return $product;
    }
}
```

## События: домен vs интеграция
Доменные события публикуем **после коммита**; наружу — через адаптер на `EventManager`:
```php
$connection->startTransaction();
try { $order = $this->placeOrder->handle($cmd); $connection->commitTransaction(); }
catch (\Throwable $e) { $connection->rollbackTransaction(); throw $e; }
foreach ($order->releaseEvents() as $e) { $this->integrationBus->publish($e); }
```
Подписка в `init.php` — только регистрация (ленивый автолоад):
```php
EventManager::getInstance()->addEventHandler('sale','OnSaleOrderSaved',
    [\Local\Sale\Presentation\OrderSavedHandler::class, 'onSaleOrderSaved']);
```

## Анти-паттерны (битрикс-конкретика)
Бизнес-логика в `init.php` (на каждом хите, ломает композит) · логика/запросы в `template.php` · статический
хелпер-помойка (немокируем → нетестируем) · **ServiceLocator внутри сервисов** · God-object · «умная» модель
(`DataManager` с правилами и письмами в `onAfterAdd`) · копия типового компонента ради одной правки · правка
`/bitrix/modules` · хардкод ID инфоблоков · `catch (\Throwable) {}` · слои ради слоёв.

## Свод «пиши сразу так»
`declare(strict_types=1)` в своих классах · полная типизация (generics через PHPDoc `list<Product>`) · **`final` по
умолчанию** (кроме требуемых Битриксом наследников: `DataManager`, `CBitrixComponent`, `Main\Engine\Controller`) ·
иммутабельность (`readonly`, withers вместо сеттеров) · **никакой статики/синглтонов** в своём коде · null-safety
(«не найдено» → исключение/Null Object, а не молчаливый `null`) · **никакой магии** `__get/__set/__call` ·
enum вместо строковых констант (на границе с ядром — `from()/tryFrom()`, в БД/кэш — `->value`).

## PSR — что применимо
`ServiceLocator` = **PSR-11** · `Bitrix\Main\Diag\Logger` = **PSR-3** (есть `FileLogger`, настройка в `.settings_extra.php`)
· PSR-4 автолоад обязателен · **PSR-12/PER-CS 3.0** — стиль · **PSR-20 Clock** — дёшево и делает тесты детерминированными ·
PSR-18 HTTP — для внешних интеграций (мокируемо) · PSR-6/16 кэш — только адаптером (свой `TaggedCache` сильнее) ·
PSR-14 — только для СВОИХ доменных событий (событиями ядра правит `EventManager`) · PSR-15 — неприменим (аналог `ActionFilter`).

## PHPStan: два бюджета качества
Новый код `/local/classes`, `/local/modules` — **level 6** минимум (цель 8); компоненты/шаблоны/`init.php` — **level 1–2**
(`$arResult` — `array<mixed>` по природе, гнать выше бессмысленно). Level 9/10 — только чистый домен без ядра.
