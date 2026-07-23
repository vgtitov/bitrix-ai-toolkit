# Окружение Битрикс — VM, локалка, организация разработки, траблшутинг

Toolkit помогает настроить окружение и решать проблемы. Ниже — варианты, команды, типовые проблемы.

## Варианты окружения (что когда)
| Вариант | Когда | Замечания |
|---|---|---|
| **BitrixVM** (виртуалка вендора) | стейдж/прод, «как в бою» | преднастроена под требования платформы (nginx+php-fpm+mysql+push+memcached). `menu.sh` — управление. |
| **bitrixdock** (Docker, 620★) | локальная разработка | народный стек. На Apple Silicon amd64-образы через эмуляцию (медленнее старт). |
| **Нативно (brew php+mysql+nginx)** | лёгкая разработка кода | быстро на ARM; для «Claude читает/правит/линтит код» полный сайт не нужен. |
| **quay.io/bitrix24/php** | CI-раннеры | официальные PHP-образы для пайплайнов. |

## Минимальная настройка (нативно, для разработки кода)
```bash
brew install php composer                    # PHP 8.3 + Composer
composer require --dev phpstan/phpstan phpstan/phpstan-deprecation-rules \
    friendsofphp/php-cs-fixer phpcsstandards/php_codesniffer rector/rector phpunit/phpunit
```
Для BitrixVM: скачать образ вендора → импортировать в VirtualBox/VMware → `menu.sh` → создать пул/сайт → развернуть из BitrixSetup или восстановить бэкап.

## Организация разработки (дисциплина)
- **Раскладка:** `/local` в git (компоненты, модули, шаблоны, php_interface, PSR-4 `\Local\` классы); ядро `/bitrix` и `upload/` — в `.gitignore`.
- **composer.json/vendor — вне DOCUMENT_ROOT** (иначе ломает выгрузку «1С→Битрикс»).
- **Структура — миграциями** (`sprint.migration`), не руками в БД/админке.
- **Ветвление:** feature-ветки → ревью → merge; деплой `/local` через GitLab CI + rsync/Deployer + `sprint.php migrate`.
- **Хуки** (`scripts/install_git_hooks.py`): commit-msg (чистые сообщения) + pre-commit (bitrix-guard N+1).
- **Настройки dev/prod:** `.settings.php` `exception_handling.debug=true` только на dev; на проде false.

## Типовые проблемы окружения и разбор
| Симптом | Причина / что смотреть |
|---|---|
| «Правки не видны» | композит/кэш браузера/CDN edge-кэш; сбросить кэш Битрикс (`Настройки → Автокэширование → сбросить`), версия ассета в query-string, `Ctrl+F5`. |
| «Белый экран/500» | `.settings.php` `exception_handling.debug=true` + смотреть `bitrix/modules/error.log`; права на `/bitrix/cache`, `/upload`. |
| «Класс ядра не найден» PHPStan/IDE | нет стабов/autoload: `composer dump-autoload -o`, `scanDirectories` на ядро своей версии, стабы `bxApiDocs`/`bitrix-ci`. |
| «Медленно после установки» | холодный кэш (норма первые минуты); файловый кэш вместо Redis; OPcache выключен. См. skill `bitrix-performance`. |
| «Не ставится обновление» | PHP < 8.2 (с 01.02.2026 обновления недоступны); проверить «Проверку системы». |
| «1С-обмен падает» | vendor/composer.json внутри DOCUMENT_ROOT ломает обмен; права; таймауты; размер пакета CommerceML. |
| «Права/доступ на сервере» | владелец файлов (`bitrix:bitrix` в BitrixVM), `chmod` кэша/upload, SELinux/AppArmor. |

## Проверка системы
`Настройки → Инструменты → Проверка системы` — валидирует PHP/MySQL/окружение против требований платформы (версии, `sql_mode`,
`transaction-isolation=READ-COMMITTED`, OPcache, права). Первое, что смотреть при подозрении на окружение.
