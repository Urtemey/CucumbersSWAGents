# CucumbersSWAGents

Deep-agent оркестратор на LangGraph для авто-решения и пересдачи учебных задач на `platform.brojs.ru`. Полный цикл без участия человека: fetch задания → генерация кода → тестирование → Gitea push → сдача в журнал.

## Стек технологий

| Слой | Что |
|------|-----|
| Язык | Python 3.11 |
| Пакетный менеджер | `uv` (venv в `.venv/`) |
| Оркестрация | LangGraph ≥ 0.2, langchain ≥ 0.3, langchain-mcp-adapters |
| LLM-провайдер | langchain-openai → `platform.brojs.ru` inference tunnel (или OpenRouter) |
| MCP | Journal MCP (http transport, Bearer auth), Gitea MCP (stdio, uvx) |
| HTTP-клиент | httpx (Gitea REST без LLM) |
| CLI | typer + rich (Rich Live dashboard) |
| Web-сервер | FastAPI + SSE (`server.py`) |
| Точка входа | `python -m orchestrator.main` / скрипт `swagents` |

## Структура проекта

```
src/orchestrator/
  main.py              — typer CLI: run / tools / list
  graph.py             — LangGraph StateGraph, supervisor routing
  common.py            — OrchestratorState (TypedDict), make_llm()
  config.py            — Config dataclass, _env_first(), load_dotenv(override=True)
  code_utils.py        — extract_code_block / inject_llm_params / fix_legacy_api / syntax_error
  mcp_client.py        — конфиги MCP-серверов (gitea + journal)
  visualizer.py        — Rich Live CLI dashboard
  runlog.py            — файловый лог прогонов в logs/
  server.py            — FastAPI SSE-сервер (web UI)
  agents/
    task_fetcher.py    — fetch rework/todo через Journal MCP
    coder.py           — генерация + ревью + repair loop
    tester.py          — compile / static / deps / subprocess / LLM-оценка
    submitter.py       — Gitea REST API push
    journal_publisher.py — task_update_answer / task_submit / status

src/web/index.html     — фронтенд web UI
run_task.py            — legacy entrypoint (из локального .txt)
pyproject.toml         — зависимости, скрипт swagents
.env.example           — шаблон переменных окружения
logs/                  — файловые логи прогонов (не коммитить)
solutions/             — локальные копии решений, fallback если Gitea недоступен
```

## Ключевые команды

### Первый запуск

```powershell
uv sync                         # установить зависимости в .venv
.venv\Scripts\activate
$env:PYTHONUTF8="1"             # обязательно на Windows
cp .env.example .env            # заполнить токены
```

### Запуск оркестратора

```powershell
# Пересдать первое rework-задание (основной сценарий)
python -m orchestrator.main run --auto

# Конкретная задача по ID (24-hex ObjectId из tasks_list)
python -m orchestrator.main run --auto --task-id 6a047cc6a6fe2e4ac16b35ec

# Включить новые todo (если rework нет)
python -m orchestrator.main run --auto --include-new

# Без сдачи: fetch → code → test → стоп
python -m orchestrator.main run --auto --dry-run

# Пауза для просмотра кода перед сдачей
python -m orchestrator.main run --review

# Список MCP-инструментов
python -m orchestrator.main tools

# Список заданий с платформы
python -m orchestrator.main list

# Legacy: условие из локального файла
python run_task.py <path.txt> task-001 --auto --dry-run
```

### Web UI

```powershell
uvicorn orchestrator.server:app --port 8765 --reload
# → http://localhost:8765
```

### Тесты

```powershell
uv run pytest
```

## Конфигурация (.env)

Файл `.env` в `.gitignore` — никогда не коммитить. Скопировать из `.env.example` и заполнить:

```env
# LLM
LLM_BASE_URL=https://platform.brojs.ru/jrnl-bh/api/inference/v1
LLM_MODEL=gpt-oss:20b
OPENAI_API_KEY=lm-studio          # заглушка; config подставит JOURNAL_TOKEN

# Gitea
GITEA_URL=https://git.brojs.ru
GITEA_TOKEN=...
GITEA_OWNER=your_username

# Journal MCP
PLATFORM_MCP_URL=https://platform.brojs.ru/jrnl-bh/api/mcp
JOURNAL_TOKEN=jrnl_...            # platform.brojs.ru → профиль → токены
                                  # PLATFORM_TOKEN — legacy-алиас

# Репозиторий решений
SOLUTIONS_REPO=cucumbers-solutions
AUTO_CREATE_REPO=true
```

`config.py` вызывает `load_dotenv(override=True)` и принудительно пишет `os.environ["OPENAI_API_KEY"]` — без этого langchain-openai игнорирует переданный `api_key`.

## Git

- Основная ветка: `master`
- Не коммитить: `logs/`, `solutions/`, `.env`, `.venv/`, `__pycache__/`

## Что нельзя трогать

| Что | Почему |
|-----|--------|
| `.env` | Токены — никогда не коммитить |
| `GITEA_URL` | Только `git.brojs.ru`; `git.bro-js.ru` — SSL сломан |
| `config.py` → `load_dotenv(override=True)` | Без этого токены из .env не подтянутся |
| Journal MCP transport | Только `"http"`, не `"streamable_http"` (иначе 4xx) |
| `task_submit` | Всегда с `confirmSubmit=True`, иначе MCP отвергнет |
| MCP-инструменты | Только `await ainvoke()`, не sync `invoke()` |
| Reviewer-safety gate в `coder.py` | Принимать вывод reviewer только при `syntax_error() is None` |
| Gitea push | Через REST API в `submitter.py`, не через LLM-агент |

## Известные особенности

- **`$env:PYTHONUTF8="1"`** обязателен в PowerShell — иначе сломан вывод Rich
- **gitea-mcp** (stdio): запускать с `--python 3.11`, иначе SRE module mismatch на Windows
- **Плейсхолдеры LLM**: coder пишет `__LLM_BASE_URL__` / `__LLM_API_KEY__` / `__LLM_MODEL__`; `inject_llm_params()` заменяет их детерминированно с гарантией кавычек
- **`task_id` в journal-вызовах**: 24-hex ObjectId из `task_text()` / `tasks_list()`; `tasks_list[]._id` и `submissionId` — другие поля, не путать
- **HITL-задачи** с `interrupt`: subprocess-тестер даёт timeout 60s — это не автоматический провал
- **Rate limit OpenRouter**: HTTP 429 → подождать сброса суточного лимита или сменить модель в `LLM_MODEL`

## Agent Team

| Агент | Роль | Модель |
|-------|------|--------|
| `product-manager` | PRD, user stories, acceptance criteria | opus |
| `architect` | System design, API contracts, data models | opus |
| `implementer` | Реализация по PRD и дизайну | inherit |
| `code-reviewer` | Качество, безопасность, производительность | inherit |
| `tester` | Написание тестов, валидация критериев | sonnet |
| `debugger` | RCA, исследование багов | inherit |
| `docs-writer` | API docs, архитектурная документация | sonnet |

## Скиллы

- `/new-feature` — PRD → дизайн → реализация → тесты → ревью
- `/fix-bug` — исследование → RCA → фикс → регрессионный тест → ревью
- `/review-code` — структурированное код-ревью по уровням серьёзности
- `/quick` — точечное изменение без полного пайплайна
- `/plan` / `/execute` — план и пошаговое исполнение
- `/commit` — стейджинг и коммит с conventional commit message
- `/validate` — полная проверка: lint, types, tests, build
- `/security-audit` — аудит по OWASP Top 10
