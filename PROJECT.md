# PROJECT.md

## Product Overview

| Field | Value |
|-------|-------|
| **Name** | CucumbersSWAGents |
| **Description** | Deep-agent оркестратор на LangGraph для авто-пересдачи и сдачи учебных заданий на `platform.brojs.ru`. Полный цикл: Journal MCP fetch (rework-first) → LLM coder+reviewer → subprocess-тестирование → push в Gitea → `task_update_answer` + `task_submit` + `task_submission_status`. Всё end-to-end без человека. |
| **Target Users** | Студенты `platform.brojs.ru` для авто-сдачи заданий по AI/LangChain/LangGraph |
| **Business Goals** | (1) Автоматизация пересдачи rework-задач с учётом фидбэка препода; (2) устойчивость к слабым LLM (4B–20B); (3) полноценная интеграция с журналом (не только Gitea-push, но и `task_submit` с обновлением `commitData`) |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| Runtime | CPython 3.11 в проектном `.venv` |
| Framework | LangGraph + LangChain 1.3.x + langchain-mcp-adapters |
| LLM Provider | brojs jrnl-туннель (OpenAI-compatible) → `openai/gpt-oss-20b` |
| MCP Servers | Journal MCP (http, Bearer): `platform.brojs.ru/jrnl-bh/api/mcp` + Gitea MCP (stdio, uvx) |
| HTTP | httpx (Gitea REST API, фетч Mintlify-доков) |
| CLI | typer + rich (Live dashboard) |
| Database | — (state в LangGraph; runlog в `logs/`) |
| Test Framework | E2E: `python -m orchestrator.main run --auto --dry-run` (без сдачи) |
| Package Manager | uv |

## Commands

| Action | Command |
|--------|---------|
| Install | `uv sync` |
| **Live run (основной)** | `python -m orchestrator.main run --auto` — пересдаёт первую rework |
| Live run конкретной | `python -m orchestrator.main run --auto --task-id <ObjectId>` |
| Live, новое если rework нет | `python -m orchestrator.main run --auto --include-new` |
| Dry-run (без сдачи) | `python -m orchestrator.main run --auto --dry-run` |
| Из файла (legacy) | `python run_task.py taskinfo\task1info.txt task-001 --auto --dry-run` |
| Demo visual | `python demo_visual.py` |
| MCP tools | `python -m orchestrator.main tools` |

## Directory Structure

```
CucumbersSWAGIntelligence/
├── src/orchestrator/
│   ├── agents/
│   │   ├── task_fetcher.py       — Journal MCP fetch (rework-first) + docs scrape
│   │   ├── coder.py              — coder + reviewer + repair loop + few-shot
│   │   ├── tester.py             — синтаксис → static → deps → subprocess → LLM-оценка
│   │   ├── submitter.py          — Gitea REST + структурированный return для journal
│   │   └── journal_publisher.py  — task_update_answer + task_submit + status (без LLM)
│   ├── code_utils.py             — extract/inject/fix_legacy/strip_prose/syntax_error
│   ├── common.py                 — OrchestratorState, make_llm()
│   ├── config.py                 — Config + _env_first() с legacy-алиасами
│   ├── graph.py                  — 6-нодовый LangGraph + supervisor routing
│   ├── main.py                   — typer CLI (run / tools / list)
│   ├── mcp_client.py             — gitea + journal MCP server configs
│   ├── runlog.py                 — файловый лог (logs/<task>_<ts>.log)
│   └── visualizer.py             — Rich Live dashboard
├── taskinfo/                     — *.txt с условиями (legacy путь без MCP)
├── logs/                         — файловые логи прогонов
├── solutions/                    — локальные копии (fallback)
├── run_task.py                   — legacy entrypoint (файл-задание)
└── demo_visual.py                — демо визуала без LLM
```

## File Conventions

- Все модули — `from __future__ import annotations` в начале
- Промпты-константы — `_UPPER_SNAKE_CASE` со звёздочками-разделителями (`═══ СЕКЦИЯ ═══`)
- Async I/O везде где есть LLM / MCP / subprocess / httpx; sync только для `ast.parse` и `re`
- Пути к Python в subprocess — через `VENV_PYTHON` (резолв при импорте), никогда `sys.executable`
- Чтение env-переменных — через `_env_first(*names)` чтобы поддерживать legacy-алиасы

## Code Standards

- **Принцип робастности**: что можно сделать кодом — делаем кодом, не промптом
- Reviewer-output принимается ТОЛЬКО после `syntax_error() is None` гейта
- Inject параметров — 3-слойная замена с гарантией кавычек даже для голых плейсхолдеров
- В promo-prompt для слабой модели используем primacy effect — самое важное (формат, MESSAGES API, rework-feedback) в начало
- Никаких комментариев-объяснений ради объяснений; комментарий только для нетривиального why

## Architecture Pattern

LangGraph supervisor-pattern с детерминированной маршрутизацией, **6 нод**:

```
START → supervisor → {task_fetcher | coder | tester | submitter | journal_publisher} → supervisor → END
```

- Supervisor — pure function (state → `next_agent`)
- Каждый суб-агент возвращает дельту state'а
- Каждая нода возвращается в supervisor (звёздообразный граф)
- **Завершение**:
  - `--dry-run` → стоп после `tester` (submitter и journal skip)
  - submitter упал → journal_publisher авто-skip
  - taskId не из платформы (не 24-hex) → journal_publisher авто-skip с пояснением

### Ключевые потоки данных

```
task_fetcher  → task_description + task_id (resolved)
coder         → generated_code (+ авто-fix legacy API, inject params)
tester        → test_results (LLM-оценка markdown table)
submitter     → submission_result, solution_url, repo_url, branch, commit_sha,
                file_path, commit_message
journal_publisher → journal_status (e.g. "ready_for_review", "done (оценка: True)")
```

## Security

- `.env` в `.gitignore` — токены не коммитятся
- Submitter в Gitea использует REST API напрямую, минуя LLM → нет утечки `GITEA_TOKEN` через tool-calling
- Journal MCP вызовы тоже детерминированные (нет LLM-агента) → `JOURNAL_TOKEN` не виден модели
- Subprocess решений запускается в проектном `.venv` с `PYTHONUTF8=1` + `PYTHONDONTWRITEBYTECODE=1`
- `task_submit` требует `confirmSubmit=True` — защита от случайных вызовов
- LLM-инжекция: API-ключ подставляется в код В МОМЕНТ генерации, не сохраняется в промптах

## Implementation Phases

1. ✓ MCP-клиент Gitea + базовый LangGraph
2. ✓ Coder + reviewer с принудительной инжекцией параметров
3. ✓ Tester: синтаксис → static → deps → subprocess → LLM-оценка
4. ✓ Визуализатор: Rich Live, баннер, ноды, стрим, прогресс-бар, Rich-таблица оценки
5. ✓ Робастность под слабые модели: `extract_code_block` (5 уровней), `repair_syntax` loop, few-shot, `fix_legacy_api`, `inject_llm_params` с гарантией кавычек, Messages API в промпте
6. ✓ `--auto` режим для CI/тестирования
7. ✓ **Journal MCP**: подключение + детерминированный fetch (без react-loop)
8. ✓ **Rework-семантика**: дефолт `run --auto` пересдаёт только возвращённые, `reworkComment` вклеивается в task_description первым блоком
9. ✓ **journal_publisher**: `task_update_answer` → `task_submit` → `task_submission_status` после Gitea-push
10. □ Передача reworkComment в reviewer (сейчас видит только coder)
11. □ Retry с фидбэком LLM-оценщика (передавать прошлый `score_text` в новую coder-итерацию)
12. □ HITL-aware stdin генератор (понимает `interrupt`/`Command(resume=...)`)
13. □ `task_comment` при сдаче — постить ссылку на коммит + summary исправлений
14. □ Batch-режим: `run --batch` прогоняет все rework последовательно
15. □ Кеш Mintlify-доков (TTL 24h)
16. □ Регрессионный набор задач для smoke-теста при изменениях промптов

## Validation Status

**Last live run** (one rework cycle, `01:17` total):
- task_fetcher: rework `69b1a07c67bbf488a1177da4` («Текстовая игра LLM+interrupt»), reworkComment вклеен
- coder + reviewer: код сгенерирован, syntax OK, legacy API заменён
- tester: subprocess запустился, LLM-оценка получена
- submitter: Gitea PUT 201, sha получен
- journal_publisher: update_answer ✓, submit ✓, status `ready_for_review` ✓

**Journal snapshot at last check**:
- 18 todo (4 rework + 14 новых)
- 0 ready_for_review (после прогона стало 1)
- 11 done (все на 100/100)

---

> **Note for settings.json:** See `.claude/settings.json` for permissions, env vars, and hook configuration.
