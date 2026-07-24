# Локализация под компанию — настройки отдельно от ядра

Принцип: **toolkit самодостаточен**. Без каких-либо настроек он работает на безопасных дефолтах и не ломается.
Настройки конкретной компании — **отдельный слой**, который можно хранить в приватном репозитории и подключать.

## Слои (по возрастанию приоритета)
1. **Ядро toolkit** (этот публичный репозиторий) — generic-правила, скиллы, проверки, дефолты.
2. **`config/*.example.*`** — образцы; копируются и правятся под проект.
3. **`config/local/`** — локальный слой компании/проекта (**в `.gitignore`**, в публичный репо не попадает).
4. **env** — самый высокий приоритет (`BITRIX_AI_CHECKS`, `JIRA_URL`, …). Удобно для CI и разовых прогонов.

## Что кладут в локальный слой
| Файл | Назначение |
|---|---|
| `config/local/checks.toml` | режимы проверок компании (off/warn/block), scope путей |
| `config/local/version-stack.toml` | версии PHP/ядра/модулей, `core_modified`, пути к патчам ядра |
| `config/local/.env` | креды интеграций (Jira/Confluence/Zabbix) — **только локально, не в git** |
| `core/skills/*/references/local/` | конвенции компании: префиксы, точки расширения, слепые зоны (скиллы читают ПЕРЕД работой) |

## Отдельный приватный репозиторий (рекомендуемый способ для команды)
Компанейские настройки удобно держать в своём private-репо (например `bitrix-ai-toolkit-<company>`), чтобы
раздавать команде и версионировать:

```
bitrix-ai-toolkit-acme/          # приватный репо компании
├── checks.toml
├── version-stack.toml
├── conventions/                 # references/local/* для скиллов
└── README.md                    # как подключить
```

Подключение (любой из способов):
```bash
# вариант 1 — клонировать ВНУТРЬ существующего config/local
#   (сам каталог создаётся onboard'ом и не пуст — клонировать «в него целиком» нельзя)
git clone git@git.company:team/bitrix-ai-toolkit-acme.git config/local/company
cp config/local/company/checks.toml config/local/checks.toml        # или симлинки на файлы
cp config/local/company/version-stack.toml config/local/version-stack.toml

# вариант 2 — симлинки на ФАЙЛЫ (а не на каталог: config/local уже существует,
#   и `ln -s dir config/local` создаст ссылку ВНУТРИ него, которую скрипты не увидят)
ln -sf /path/to/company/checks.toml       config/local/checks.toml
ln -sf /path/to/company/version-stack.toml config/local/version-stack.toml

# вариант 3 — только env (для CI)
export BITRIX_AI_CHECKS=warn
```

`scripts/checks_config.py` сам подхватывает `config/local/checks.toml` поверх `config/checks.toml`.
**Нет локального слоя → работают дефолты.** Ничего не падает.

## Правила гигиены
- В публичное ядро **не коммитить** ничего компанейского: имена клиентов, домены, креды, внутренние конвенции.
- Секреты — только в `config/local/.env` или env/keychain, никогда в git.
- Локальный слой может переопределять правила, но **не должен ломать ядро**: при удалении `config/local` всё обязано
  продолжать работать.
