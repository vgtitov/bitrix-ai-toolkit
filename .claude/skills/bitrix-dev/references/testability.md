# Тестируемость в Битрикс-проекте

**Главный тезис: тестируемость — не про PHPUnit, а про то, КУДА положен код.** Логика в `template.php` непокрываема
в принципе; та же логика в `Local\Catalog\Application\CalculatePrice` покрывается за 5 минут.

## Границы
```
БЕЗ ЯДРА (unit, миллисекунды, покрытие 80%+)
  Domain:      VO, Entity, доменные сервисы, спецификации
  Application: UseCase с замоканными портами
  Mappers:     array (строка GetList) ↔ Domain      ← самое ценное и дешёвое
ИНТЕГРАЦИОННЫЕ (ядро поднято, тестовая БД, медленно)
  Репозитории-адаптеры, миграции, обработчики событий
E2E / ручные
  Компоненты, шаблоны, оформление заказа
```

## Чек-лист «код тестируем»
- [ ] нет `new` инфраструктуры внутри метода — всё в конструкторе;
- [ ] нет статических вызовов ядра (`CIBlockElement::`, `Option::get`, `$USER->`, `$APPLICATION->`) вне инфраструктуры;
- [ ] нет `time()`/`date()`/`rand()` → `ClockInterface` (PSR-20), `Random\Randomizer` через интерфейс;
- [ ] нет `$_REQUEST`/`$_SESSION`/`$GLOBALS` глубже presentation;
- [ ] нет `exit`/`die`/`LocalRedirect` внутри сервисов;
- [ ] метод **возвращает значение**, а не «печатает»/пишет в `$arResult`;
- [ ] зависимости — интерфейсы (иначе нечего мокать).

## Инструменты
**PHPUnit** (дефолт) / **Pest** (надстройка, совместима) · **bitrix-ci** (`bitrix-toolkit/bitrix-ci` — ядро в `vendor`
для CI/интеграционных без установки продукта) · **bxApiDocs** (стабы для IDE/PHPStan).

## In-memory реализация вместо мока — надёжнее
```php
final class InMemoryProductRepository implements ProductRepository {
    /** @var array<int, Product> */ private array $items = [];
    public function add(Product $p): void { $this->items[$p->id()->value] = $p; }
    public function byId(ProductId $id): Product {
        return $this->items[$id->value] ?? throw ProductNotFound::byId($id);
    }
}
```
Переиспользуется во всех тестах юзкейсов и не ломается при рефакторинге сигнатур — в отличие от
`expects($this->once())->method(...)`.

## Два набора тестов
```xml
<testsuites>
  <testsuite name="unit">        <!-- bootstrap: только vendor/autoload.php -->
    <directory>tests/Unit</directory>
  </testsuite>
  <testsuite name="integration"> <!-- bootstrap: prolog_before.php + тестовая БД -->
    <directory>tests/Integration</directory>
  </testsuite>
</testsuites>
```
`tests/bootstrap-integration.php`:
```php
$_SERVER['DOCUMENT_ROOT'] = dirname(__DIR__);
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);
require $_SERVER['DOCUMENT_ROOT'] . '/bitrix/modules/main/include/prolog_before.php';
```

## Реалистичная планка
Не «покрыть проект», а **«покрыть деньги»**: расчёт цены/скидки, статусы заказа, обмен с 1С, интеграции.
Это ~5–10% кода и ~90% рисков. Тесты — слабое место рынка Битрикс, поэтому здесь наибольшая отдача от AI.
