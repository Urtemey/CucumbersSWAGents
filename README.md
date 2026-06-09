# CucumbersSWAGents 🥒

> Deep-agent оркестратор на LangGraph — автоматически решает и пересдаёт учебные задания на `platform.brojs.ru`.

Одна команда → fetch rework из журнала → LLM генерирует код → subprocess тест → Gitea push → `task_submit`. Полный цикл без участия человека. Реальное время: **~1 мин 17 сек** на одной rework-задаче.

---

## Стек

| Слой | Технология |
|------|-----------|
| Язык | Python 3.11 |
| Оркестрация | LangGraph + LangChain 1.3.x + langchain-mcp-adapters |
| LLM | brojs jrnl-туннель → `openai/gpt-oss-20b` (OpenAI-compatible) |
| MCP | Journal MCP (http, Bearer) + Gitea MCP (stdio, uvx) |
| HTTP | httpx (Gitea REST API, scrape Mintlify-доков) |
| CLI | typer + Rich Live dashboard |
| Пакеты | uv |

---

## Быстрый старт

**Prerequisites:** Python 3.11, [uv](https://docs.astral.sh/uv/), uvx (поставляется вместе с uv)

```powershell
# 1. Установить зависимости
uv sync

# 2. Создать .env из шаблона и заполнить токены
Copy-Item .env.example .env
# Открыть .env и заполнить: JOURNAL_TOKEN, GITEA_TOKEN, GITEA_OWNER

# 3. Запустить (PYTHONUTF8=1 обязателен в PowerShell)
$env:PYTHONUTF8="1"
python -m orchestrator.main run --auto
```

### Переменные окружения

| Переменная | Описание |
|-----------|---------|
| `JOURNAL_TOKEN` | Токен платформы: `platform.brojs.ru` → профиль → токены |
| `GITEA_TOKEN` | Personal access token из `git.brojs.ru` |
| `GITEA_OWNER` | Ваш username на git.brojs.ru |
| `LLM_BASE_URL` | URL inference-эндпоинта (дефолт зашит в config.py) |
| `LLM_MODEL` | Модель (дефолт: `gpt-oss:20b`) |
| `SOLUTIONS_REPO` | Репозиторий для решений (дефолт: `cucumbers-solutions`) |

Полный шаблон: [`.env.example`](.env.example)

---

## Команды

```powershell
# Пересдать первую возвращённую (rework) задачу — основной сценарий
python -m orchestrator.main run --auto

# Конкретная задача по ObjectId (24-hex)
python -m orchestrator.main run --auto --task-id 6a047cc6a6fe2e4ac16b35ec

# Взять новое todo если rework нет
python -m orchestrator.main run --auto --include-new

# Dry-run: fetch → code → test, без Gitea и журнала
python -m orchestrator.main run --auto --dry-run

# Пауза после теста для просмотра кода перед сдачей
python -m orchestrator.main run --review

# Список MCP-инструментов (gitea + journal)
python -m orchestrator.main tools

# Список заданий с платформы
python -m orchestrator.main list

# Legacy: из локального файла
python run_task.py taskinfo\task1info.txt task-001 --auto --dry-run

# Демо визуализатора без LLM
python demo_visual.py
```

| Флаг | Что делает |
|------|-----------|
| `--auto`, `-a` | Авто-сдача после tester'а, без интерактива |
| `--dry-run` | Стоп после tester'а, Gitea и журнал не трогаются |
| `--review`, `-r` | Пауза для просмотра кода перед сдачей |
| `--include-new` | Брать новые todo, если rework нет |
| `--task-id <id>` | Конкретная задача (rework-фильтр не применяется) |
| `--task-text "..."` | Передать задание текстом, без MCP-фетча |

---

## Архитектура

```
START
  └─> supervisor  (детерминированная маршрутизация, pure function)
        ├─> task_fetcher       Journal MCP: rework-first fetch + scrape docs
        ├─> coder              LLM генерация + reviewer + repair loop + few-shot
        ├─> tester             py_compile → AST → pip install → subprocess → LLM-оценка
        ├─> submitter          Gitea REST API (httpx), без LLM
        ├─> journal_publisher  task_update_answer → task_submit → task_submission_status
        └─> END
```

| Нода | LLM? | Суть |
|------|------|------|
| `task_fetcher` | нет | Фильтрует `tasks_list` по `reworkComment != ""`, достаёт текст, скрапит Mintlify-доки |
| `coder` | да | Coder (temp=0.1) + reviewer (temp=0.0) + repair loop (до 2 итераций) |
| `tester` | только оценка | Синтаксис → static AST → deps install → subprocess 60s → LLM rubric |
| `submitter` | нет | Gitea PUT, base64, conventional commit, возвращает `commit_sha` + `repo_url` |
| `journal_publisher` | нет | `task_update_answer` → `task_submit(confirmSubmit=True)` → `task_submission_status` |
| `supervisor` | нет | `state → next_node`, чистая функция без побочных эффектов |

**Ключевой принцип:** LLM используется только там, где без неё невозможно. Всё остальное — детерминированный код: инжекция параметров, fix legacy API, парсинг кода, сдача в Gitea.

---

## Структура файлов

```
src/orchestrator/
  agents/
    task_fetcher.py       — Journal MCP fetch + docs enrichment
    coder.py              — coder + reviewer + repair loop
    tester.py             — pipeline тестирования
    submitter.py          — Gitea REST API
    journal_publisher.py  — сдача в платформу (без LLM)
  code_utils.py           — extract/inject/fix_legacy/strip_prose/syntax_error
  common.py               — OrchestratorState (TypedDict), make_llm()
  config.py               — Config + _env_first() с legacy-алиасами
  graph.py                — 6-нодовый LangGraph граф + supervisor
  main.py                 — typer CLI: run / tools / list
  mcp_client.py           — конфиги MCP-серверов
  runlog.py               — файловый лог (logs/<task>_<ts>.log)
  visualizer.py           — Rich Live dashboard
taskinfo/                 — *.txt условия задач (legacy)
logs/                     — файловые логи прогонов
solutions/                — локальные копии решений (fallback)
run_task.py               — legacy entrypoint (из файла)
demo_visual.py            — демо визуализатора без LLM
```

---

## Визуализатор

Rich Live dashboard, 10 fps. Каждый прогон отображает:
- ASCII-баннер с градиентом + таймер `mm:ss` + прогресс-бар
- Активную ноду с пульсирующей анимацией `◐◓◑◒`
- Live-стрим кода (Syntax monokai) в процессе генерации
- Stdout subprocess в реальном времени
- Rich-таблицу LLM-оценки
- Финальный результат: `📦 Gitea: <url>` + `📓 Журнал: ready_for_review`

---

## Известные особенности

- **`PYTHONUTF8=1`** обязателен в PowerShell — без него кириллица в выводе ломается
- **Journal MCP** требует `transport: "http"`, не `"streamable_http"` (иначе 4xx)
- **`GITEA_URL`** — только `git.brojs.ru`, не `git.bro-js.ru` (SSL сломан на втором)
- **HITL-задачи** с `interrupt`/`Command(resume=...)` не покрываются subprocess-тестом полноценно — tester зафиксирует timeout 60s, это не автоматически провал
- **MCP-туннель brojs** может отвечать 504; main.py делает retry до 5 минут с интервалом 5с

---

## Roadmap

- [ ] Batch-режим: `run --batch` прогоняет все rework последовательно
- [ ] Передача `reworkComment` в reviewer (сейчас видит только coder)
- [ ] Retry с фидбэком LLM-оценщика (прошлый `score_text` → новая coder-итерация)
- [ ] HITL-aware stdin-генератор (понимает `interrupt`/`Command(resume=...)`)
- [ ] Кеш Mintlify-доков (TTL 24h)
- [ ] Регрессионный набор задач для smoke-теста при изменениях промптов
