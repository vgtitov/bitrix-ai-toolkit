---
name: bitrix-admin-devops
description: >
  Администрирование, окружение и DevOps под 1С-Битрикс (сайт/интернет-магазин): установка/обновление продукта и
  модулей, окружение разработки (bitrixdock, BitrixVM, docker), публикация и деплой /local (git/rsync/Deployer),
  применение миграций sprint.migration, CI/CD (GitLab CI/GitHub Actions с PHPStan+CS-Fixer), бэкап и восстановление,
  настройка веб-сервера/PHP/MySQL/Redis. ОБЯЗАТЕЛЬНО используй при установке/обновлении Битрикс, настройке локального
  окружения, деплое, сборке CI/CD-пайплайна, бэкапе. Настройки инфраструктуры — под свой проект. Производительность и
  тюнинг СУБД — глубоко в bitrix-performance; написание кода — bitrix-dev.
---

# Администрирование и DevOps под 1С-Битрикс

## Окружение разработки
- **bitrixdock** (github.com/bitrixdock/bitrixdock, 620★, живой) — народный Docker-стек (nginx/apache + php-fpm + mysql + workspace).
  Локалка для разработки. На Apple Silicon — amd64-образы через эмуляцию (медленнее); для чистой разработки кода полный сайт не обязателен.
- **BitrixVM** — штатная виртуалка вендора для стейджа/прода, преднастроена под требования платформы.
- **Официальные PHP-образы для CI:** `quay.io/bitrix24/php:8.3-fpm-alpine`.

## Раскладка проекта (современная)
`/local` версионируется (компоненты, модули, шаблоны, php_interface, PSR-4 классы), ядро `/bitrix` и `upload/` — в `.gitignore`.
composer.json/vendor — вне DOCUMENT_ROOT (иначе ломается выгрузка «1С→Битрикс»). Свои классы — PSR-4 `\Local\`.

## Деплой /local
- **GitLab CI + rsync** — массовый паттерн: `build (composer install + npm build) → test (phpcs/phpstan) → deploy (rsync -a --delete по SSH + sprint.migration)`.
- **Deployer** — атомарные релизы/симлинки (зрелые команды).
- Обязательный шаг после выкладки — `php sprint.php migrate` (применение миграций структуры).
- Быстрый rollback — через артефакты/симлинки релизов.

## Миграции — два разных слоя
- **Структура** (инфоблоки, HL, свойства, права) — `andreyryabin/sprint.migration` (207★, живой):
  `php migrate.php add <name>` → правка → `php migrate.php up`. Не руками в БД/админке без версионирования.
  НЕ использовать мёртвый arrilot.
- **Данные сущностей** между окружениями (dev→stage→prod) — `INTERVOLGA/intervolga.migrato` (90★, живой).
  sprint.migration переносит **структуру**, migrato — **содержимое**. Это разные задачи, часто нужны обе.

## CI/CD (эталон)
Референс: `ilimurzin/bitrix-project-example` (GitLab) — полный `.gitlab-ci.yml` с PHPStan (уровни 0-10) + PHP-CS-Fixer + Rector,
docker с распакованным ядром. Переносится на GitHub Actions тривиально. Стадии: lint (cs-fixer --dry-run, phpstan) → test (phpunit) → deploy.

## Обновление
Обновления продукта перезаписывают `/bitrix` — правки там теряются (потому правим только `/local`). С 01.02.2026 обновления
недоступны на PHP < 8.2. Перед обновлением — бэкап (БД + файлы), проверка на стейдже.

## Бэкап и безопасность
БД (`mysqldump`/xtrabackup) + файлы `/local` + `/upload`. Проверять восстановимость. Сканер известных уязвимостей развёрнутого
сайта — `k1rurk/check_bitrix` (100★). Токены/ключи — в env, не в git.
