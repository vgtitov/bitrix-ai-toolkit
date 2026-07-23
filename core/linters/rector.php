<?php
/**
 * rector.php — авто-рефакторинг и апгрейд PHP под целевую версию (Битрикс: 8.2/8.3).
 * Копируй в корень проекта. Прогон:
 *   vendor/bin/rector process --dry-run   # ПОКАЗАТЬ изменения (агент ВСЕГДА сначала так)
 *   vendor/bin/rector process             # применить
 *
 * ВНИМАНИЕ (Битрикс): готового набора правил «старое ядро → D7» НЕТ (семантика GetList != getList,
 * автозамена рискованна). Здесь — только безопасный апгрейд синтаксиса PHP и чистки. Ядро /bitrix не трогаем.
 */

use Rector\Config\RectorConfig;
use Rector\Set\ValueObject\LevelSetList;

return static function (RectorConfig $rectorConfig): void {
    $rectorConfig->paths([
        __DIR__ . '/local/php_interface',
        __DIR__ . '/local/components',
        __DIR__ . '/local/modules',
        __DIR__ . '/local/classes',
    ]);

    $rectorConfig->skip([
        __DIR__ . '/bitrix',
        __DIR__ . '/vendor',
        __DIR__ . '/upload',
    ]);

    // Целевая версия PHP — выставь под свой проект (8.2 или 8.3).
    $rectorConfig->sets([
        LevelSetList::UP_TO_PHP_83,
    ]);

    $rectorConfig->parallel();
    $rectorConfig->importNames();
};
