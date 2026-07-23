# Диагностика производительности — инструменты

## Монитор производительности (perfmon)
`Настройки → Производительность`. Тест конфигурации (балл + рекомендации). Замер (панель) — снимать ВО ВРЕМЯ нагрузки
(нет посетителей → кликать самому весь замер): топ нагруженных страниц, хиты, среднее время, число SQL, PHP vs SQL.
**APDEX** — индекс удовлетворённости. Раздел «Разработчикам» — таблица SQL страницы (дубли, тяжёлые).
Док: dev.1c-bitrix.ru/api_help/perfmon/index.php

## Панель отладки и Diag
Нижняя панель (админ): время генерации, память, число SQL, файлов, компонентов — первое, куда смотреть.
```php
\Bitrix\Main\Diag\Debug::writeToFile($var, 'label', 'debug.log');
$s = microtime(true); /* ... */
\Bitrix\Main\Diag\Debug::writeToFile(microtime(true)-$s, 'block time', 'perf.log');
if ($USER->IsAdmin()) { /* профилирование только админу */ }
```

## Внешние профилировщики
- **xhprof + XHGui** — иерархический (время/память/вызовы). Запускать на проде в пик (perfmon — когда нагрузка низкая).
- **Blackfire / Tideways** — APM с флеймграфами, регрессионным сравнением.
- **slow query log** + `EXPLAIN` — тяжёлые SQL.

## Отладка в конфигах
`bitrix/php_interface/dbconn.php`:
```php
$DBDebug = true; $DBDebugToFile = true;   // SQL → /bitrix/php_interface/log/sql.log
```
`.settings.php` секция `exception_handling`: `'debug' => true` (НА ПРОДЕ false), `log.settings.file`.

MySQL slow log (`my.cnf`):
```ini
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 1
log_queries_not_using_indexes = 1
```
Диагностика СУБД: `SHOW PROCESSLIST`, `SHOW ENGINE INNODB STATUS`, `SHOW STATUS`, `EXPLAIN <query>`.
