<?php
/**
 * .php-cs-fixer.dist.php — автоформат PSR-12 для кода /local Битрикс-проекта.
 * Копируй в корень проекта. Прогон:
 *   vendor/bin/php-cs-fixer fix                    # исправить
 *   vendor/bin/php-cs-fixer fix --dry-run --diff   # только показать (для агента/CI)
 */

$finder = PhpCsFixer\Finder::create()
    ->in([__DIR__ . '/local/php_interface', __DIR__ . '/local/components', __DIR__ . '/local/modules', __DIR__ . '/local/classes'])
    ->name('*.php')
    ->exclude(['bitrix', 'vendor', 'upload'])
    ->ignoreDotFiles(true)
    ->ignoreVCS(true);

return (new PhpCsFixer\Config())
    ->setRiskyAllowed(false)
    ->setRules([
        '@PSR12' => true,
        'array_syntax' => ['syntax' => 'short'],
        'no_unused_imports' => true,
        'ordered_imports' => ['sort_algorithm' => 'alpha'],
        'single_quote' => true,
        'trailing_comma_in_multiline' => ['elements' => ['arrays']],
        'no_trailing_whitespace' => true,
        'blank_line_after_namespace' => true,
    ])
    ->setFinder($finder);
