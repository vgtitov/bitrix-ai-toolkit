# Рефакторинг легаси в Битрикс-проекте

## Порядок действий (не переставлять)
1. **Замер/факт** — что именно болит (perfmon, лог ошибок, частота правок файла).
2. **Характеризационные тесты** (Feathers): тест фиксирует **текущее** поведение, включая странное. Цель — не
   «правильно», а «как есть», чтобы поймать регресс. Прогнать реальные входные данные, снапшотнуть выход.
3. **Найти шов (seam)** — место подмены поведения без правки окружения. В PHP почти всегда *object seam*: заменить
   прямой `CIBlockElement::GetList` на вызов метода объекта, переданного внутрь.
4. **Извлечь** — сначала чистые расчёты (нет I/O — безопаснее), потом доступ к данным.
5. **Заменить и удалить** старое.

## Strangler Fig — душим легаси, не переписывая всё
```php
interface PriceCalculator { public function calculate(ProductId $id, UserContext $ctx): Money; }

// 1) обёртка над старым — поведение не меняется
final class LegacyPriceCalculator implements PriceCalculator {
    public function calculate(ProductId $id, UserContext $ctx): Money {
        return Money::fromFloat(\CCatalogProduct::GetOptimalPrice($id->value, 1, $ctx->groups())['DISCOUNT_PRICE']);
    }
}
// 2) новая реализация рядом, покрыта тестами
final class DomainPriceCalculator implements PriceCalculator { /* … */ }

// 3) сверка на бою (safety net) — наружу пока старое
final class ComparingPriceCalculator implements PriceCalculator {
    public function calculate(ProductId $id, UserContext $ctx): Money {
        $legacy = $this->legacy->calculate($id, $ctx);
        try {
            $new = $this->new->calculate($id, $ctx);
            if (!$new->equals($legacy))
                $this->logger->warning('price mismatch', ['id'=>$id->value,'legacy'=>(string)$legacy,'new'=>(string)$new]);
        } catch (\Throwable $e) { $this->logger->error('new calculator failed', ['exception'=>$e]); }
        return $legacy;
    }
}
// 4) расхождений нет N дней → переключаем → удаляем легаси-ветку
```
Переключение — через `Option::get('local.catalog','USE_NEW_PRICE')` + регистрация нужной реализации в ServiceLocator.

## Как безопасно резать God-класс
1. **Не** начинать с «разложить по слоям». Начать с **группировки методов по данным, которые они трогают** — это
   естественные границы будущих классов.
2. Резать **по сценариям**, а не по техническим типам: не «Repository/Service/Helper», а `PlaceOrder`, `CancelOrder`,
   `RecalculateOrder` — каждый выносится отдельным коммитом.
3. Каждый вынос: характеризационный тест → `Extract Class` → старый метод становится делегирующей однострочкой →
   переключить вызовы → удалить.
4. **Не менять поведение и структуру в одном коммите.** Рефакторинг и фикс бага — разные PR.
5. Общее состояние (`$this->arResult`, приватные поля-«кэши») — сложнее всего: сначала превратить в явные
   параметры/возвраты, потом резать.

## Rector — механика, не архитектура
```php
return RectorConfig::configure()
    ->withPaths([__DIR__.'/local/classes', __DIR__.'/local/modules'])
    ->withSkip([__DIR__.'/local/templates'])      // шаблоны — руками, там HTML вперемешку
    ->withPhpSets(php83: true)                     // строго по таргету из version-stack
    ->withPreparedSets(deadCode: true, codeQuality: true, typeDeclarations: true);
```
Правила: **всегда `--dry-run` сначала**; каждый набор — отдельным коммитом; на `/bitrix` **никогда** не натравливать;
после каждого набора — PHPStan + тесты. Типичная последовательность апгрейда: `php74 → 80 → 81 → 82 → 83`,
между шагами — прогон на стенде. Rector делает синтаксис/типы/dead code — **слои он не сделает**.

Каталог приёмов: refactoring.com/catalog · Fowler «Strangler Fig», «Branch by Abstraction» · Feathers «Working
Effectively with Legacy Code».
