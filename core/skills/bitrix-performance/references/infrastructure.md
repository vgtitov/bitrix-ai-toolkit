# Инфраструктура и масштабирование

## Ускорители
- **OPcache** обязателен: `opcache.memory_consumption`, `opcache.max_accelerated_files` 100000+ (много файлов ядра),
  `opcache.validate_timestamps=0` на проде (с деплой-инвалидацией). Проверяется «Панелью проверки системы».
- **Redis/memcached как хранилище кэша** — снимает нагрузку файлового кэша с диска. `.settings.php`:
  ```php
  'cache' => ['value' => [
      'type' => 'redis', 'host' => '127.0.0.1', 'port' => '6379',
      'sid' => $_SERVER['DOCUMENT_ROOT'].'#01',
  ]],
  ```
  Redis предпочтительнее (memcached вытесняет по LRU — риск потери кэша под нагрузкой; Redis — кластер, стабильность).
- **Композит + CDN**: статику на CDN; композитный HTML отдавать через NGINX напрямую, минуя PHP.
- **PHP-FPM**: `pm = dynamic/static`, `pm.max_children` по памяти, `pm.max_requests` (перезапуск против утечек).

## MySQL/MariaDB (InnoDB) под Битрикс
```ini
innodb_buffer_pool_size = 70-80% RAM     # главный — кэширует данные и индексы
innodb_flush_log_at_trx_commit = 2
innodb_flush_method = O_DIRECT
innodb_log_file_size = 256M-512M
table_open_cache = 1200+
transaction-isolation = READ-COMMITTED   # требование Битрикс
innodb_lock_wait_timeout = 50
```
Битрикс требует READ-COMMITTED и определённый `sql_mode` — валидируй «Панель проверки системы»
(`Настройки → Инструменты → Проверка системы`). Штатное окружение **BitrixVM** уже настроено под требования.

## Веб-кластер (highload)
Модуль `cluster`: репликация MySQL master-slave (Битрикс роутит SELECT на реплики, запись в мастер), общий Redis/memcached-пул
кэша, синхронизация сессий и загруженных файлов между веб-нодами, балансировка (NGINX/HAProxy).

## Типичные bottleneck'и магазина
Умный фильтр/фасет (>10 млн) · корзина и оформление (не кэшируются, растут с числом складов/типов цен/правил скидок) ·
каталог (N+1 по свойствам/ценам) · агрегация (тяжёлые COUNT) · поиск (гигантские стемминг-таблицы → Elastic).
