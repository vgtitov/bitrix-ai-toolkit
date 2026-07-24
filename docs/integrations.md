# Интеграции — все ОПЦИОНАЛЬНЫ (выключены, пока не заданы креды)

Перенесены из `claude-1c-toolkit`. Только стандартная библиотека Python, без внешних зависимостей.
**Нет кред → интеграция просто не используется**, ничего не падает и не блокирует работу.

## Jira / Confluence — `scripts/atlassian.py`
Достать контекст задачи и знания из базы одной командой (без MCP и лишних токенов).

```bash
python3 scripts/atlassian.py jira issue PROJ-123 --comments
python3 scripts/atlassian.py jira search "project = PROJ AND status = Done" --limit 10
python3 scripts/atlassian.py conf page 123456789           # id, URL или точный заголовок
python3 scripts/atlassian.py conf tree 987654321 --depth 2
python3 scripts/atlassian.py conf search "критерии приёмки"
python3 scripts/atlassian.py conf publish docs/page.md --parent 123456780   # нужен токен с записью
```

Настройка (`config/local/.env` или окружение):
```
JIRA_URL=https://jira.example.com
JIRA_PAT=...                 # Server/DC: Personal Access Token → Bearer
# JIRA_USER=me@example.com   # Cloud: дополнительно, тогда Basic user:token
CONFLUENCE_URL=https://confluence.example.com
CONFLUENCE_PAT=...
```

**Зачем агенту:** перед реализацией задачи — прочитать ЧТЗ/критерии приёмки из Jira и конвенции из Confluence,
вместо догадок. После — опубликовать артефакт (тех-решение) страницей.

## Мониторинг (Zabbix / Prometheus) — опционально
Если команда мониторит Битрикс-стенды через Zabbix/Prometheus, метрики полезны скиллу `bitrix-performance`
(«почему медленно» — сначала измерение). Подключение — env:
```
ZABBIX_URL=http://zabbix.example/api_jsonrpc.php
ZABBIX_TOKEN=...             # read-only токен: Zabbix UI → Профиль → API tokens
PROMETHEUS_URL=http://prometheus.example
```
> Для 1С в `claude-1c-toolkit` есть готовый `scripts/zabbix_perf.py` и MCP эксплуатации. Под Битрикс основной источник
> измерений — **штатный «Монитор производительности» (perfmon)**, slow query log и xhprof (см. скилл
> `bitrix-performance`); Zabbix/Prometheus — как дополнительный слой инфраструктуры, если он уже есть.

## Безопасность интеграций
- Креды — только в `config/local/.env` / env / keychain. **Никогда в git и не в чат.**
- Для чтения достаточно read-only токенов; запись (publish) — отдельным токеном и осознанно.
- Корпоративные данные (задачи, страницы) не пересылать во внешние сервисы сверх необходимого.
