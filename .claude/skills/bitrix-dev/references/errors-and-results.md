# Ошибки: исключения в домене, `Main\Result` на границе

Проект живёт в двух парадигмах — важно не смешивать их в одном слое.
- **Домен и приложение — исключения** (нарушение инварианта, «не найдено», невозможность операции).
- **Граница с пользователем/ядром — `\Bitrix\Main\Result`** (`Result`/`Error`/`ErrorCollection`): исключение не умеет
  вернуть 5 ошибок валидации сразу. Это Either/Notification-паттерн, и он у Битрикс штатный.

```php
// Application: правило нарушено → исключение
throw new InsufficientStock($sku, $requested, $available);

// Presentation (Controller/component): переводим в Result для UI
public function addToBasketAction(int $productId, int $quantity): \Bitrix\Main\Result {
    $result = new \Bitrix\Main\Result();
    try { $this->addToBasket->handle(new AddToBasketCommand($productId, $quantity)); }
    catch (InsufficientStock $e) { $result->addError(new \Bitrix\Main\Error($e->userMessage(), 'INSUFFICIENT_STOCK')); }
    catch (\Throwable $e) {
        $this->logger->error('add to basket failed', ['exception' => $e, 'productId' => $productId]);
        $result->addError(new \Bitrix\Main\Error('Не удалось добавить товар', 'INTERNAL'));
    }
    return $result;
}
```

## Иерархия доменных исключений
```php
abstract class CatalogException extends \RuntimeException {}          // корень контекста

final class ProductNotFound extends CatalogException {                // «не нашли» — часто 404, не 500
    public static function byId(ProductId $id): self { return new self(sprintf('Product %d not found', $id->value)); }
}

final class InsufficientStock extends CatalogException {              // несёт ДАННЫЕ для UI, не только текст
    public function __construct(
        public readonly Sku $sku, public readonly int $requested, public readonly int $available,
    ) { parent::__construct(sprintf('Requested %d of %s, available %d', $requested, $sku->value, $available)); }

    public function userMessage(): string { return sprintf('Доступно только %d шт.', $this->available); }
}
```

## Правила
1. **Сообщение исключения — для разработчика** (в лог); для пользователя — отдельный метод/код.
   Никогда не показывать `getMessage()` конечному пользователю: там бывают SQL и пути.
2. **Ловить там, где можешь осмысленно обработать.** Границы: экшен контроллера, `component.php`, обработчик события,
   агент, cli-entrypoint. Внутри — не ловят.
3. **`catch (\Throwable)` только на границе** и обязан логировать + пробросить/конвертировать. Пустой `catch` — запрещён.
4. Оборачивать чужие исключения с причиной: `throw new PaymentFailed('…', previous: $e);`
5. `finally` — освобождение ресурсов (файл, блокировка, кэш-lock). Транзакции — см. `quality-standards.md`.

Исключения ядра: `Main\SystemException` (корень), `ArgumentException`, `ArgumentNullException`,
`ArgumentOutOfRangeException`, `ObjectNotFoundException`, `Main\DB\SqlQueryException`, `LoaderException`.

## Логирование — PSR-3, он у Битрикс уже есть
```php
public function __construct(
    private readonly OrderRepository $orders,
    private readonly \Psr\Log\LoggerInterface $logger,   // ← PSR-3, не AddMessage2Log
) {}
```
Реализация — `\Bitrix\Main\Diag\FileLogger` (без внешних зависимостей, настройка в `.settings_extra.php`) или Monolog
(если нужны Sentry/ELK/Telegram). `AddMessage2Log()` — годится для быстрой отладки, но **не как архитектура**
(нет уровней, контекста, хендлеров). Контекст структурированный: `['orderId' => $id, 'exception' => $e]`.
Уровни: `error` — сломалось и нужен человек · `warning` — деградация/ретрай · `info` — бизнес-факт · `debug` — только стенд.
ПДн и секреты не логировать; `#[\SensitiveParameter]` (8.2) маскирует значение в стектрейсе.

## Ошибки в компонентах + ЛОВУШКА КЭША
```php
try { $this->arResult['PRODUCTS'] = $useCase->handle($query); }
catch (ProductNotFound) { \Bitrix\Iblock\Component\Tools::process404('', true, true, true); return; }
catch (\Throwable $e) {
    $this->logger->error('catalog component failed', ['exception' => $e, 'params' => $this->arParams]);
    ShowError('Не удалось загрузить каталог'); return;
}
```
⚠️ Исключение **внутри** `startResultCache()/endResultCache()` оставляет незакрытый кэш → закэшируется битый результат:
```php
if ($this->startResultCache()) {
    try { $this->arResult = $useCase->handle($query); $this->includeComponentTemplate(); }
    catch (\Throwable $e) { $this->abortResultCache(); throw $e; }   // ОБЯЗАТЕЛЬНО
}
```
