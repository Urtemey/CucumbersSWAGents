# CucumbersSWAGents — Claude Code Configuration

## Что это

Deep-agent оркестратор на базе LangGraph для автоматического решения задач с платформы препода (`platform.brojs.ru`). Читает задание → генерирует код → ревьюит → пушит в Gitea.

## Стек

| Слой | Технология |
|------|-----------|
| Язык | Python 3.11 |
| Оркестрация | LangGraph + langchain-mcp-adapters |
| LLM | OpenRouter (`baidu/cobuddy:free`) через langchain-openai |
| MCP | gitea-mcp (stdio) → `git.brojs.ru` |
| Сдача решений | Gitea REST API (httpx, без LLM) |
| Пакетный менеджер | uv |

## Быстрый старт

```powershell
# Активировать окружение
.venv\Scripts\activate

# Решить задачу из файла
$env:PYTHONUTF8="1"
python run_task.py taskinfo\task1info.txt task-001

# Сгенерировать без сдачи (dry-run)
python run_task.py taskinfo\task1info.txt task-001 --dry-run

# Посмотреть доступные MCP-инструменты
python -m orchestrator.main tools

# Передать задание текстом напрямую
python -m orchestrator.main run --task-id task-001 --task-text "Напиши функцию..."
```

## Архитектура графа

```
START
  └─> supervisor        (детерминированная маршрутизация)
        ├─> task_fetcher   (если нет task_description — берёт с платформы)
        ├─> coder          (генерирует код + само-ревью)
        ├─> submitter      (пушит в Gitea через REST API)
        └─> END
```

### Суб-агенты

| Агент | Файл | Что делает |
|-------|------|-----------|
| `supervisor` | `graph.py` | Детерминированная маршрутизация по стадиям |
| `task_fetcher` | `agents/task_fetcher.py` | Получает задание через MCP платформы (если есть) |
| `coder` | `agents/coder.py` | Coder (temp=0.1) + reviewer (temp=0.0), оба на OpenRouter |
| `submitter` | `agents/submitter.py` | REST API к Gitea — без LLM, детерминированно |

### LLM-инжекция в генерируемый код

Coder и reviewer **принудительно** подставляют в генерируемый код актуальные параметры из `.env`:
- `base_url`, `api_key`, `model` — чтобы решения работали с тем же провайдером что и оркестратор.

## Конфигурация (.env)

```env
# LLM провайдер
LM_STUDIO_BASE_URL=https://openrouter.ai/api/v1
LM_STUDIO_MODEL=baidu/cobuddy:free
OPENAI_API_KEY=sk-or-v1-...

# Gitea
GITEA_URL=https://git.brojs.ru
GITEA_TOKEN=...
GITEA_OWNER=ababaykin2016

# Platform MCP (пока нет рабочего эндпоинта)
PLATFORM_MCP_URL=
PLATFORM_TOKEN=jrnl_...

# Куда сдавать
SOLUTIONS_REPO=cucumbers-solutions
AUTO_CREATE_REPO=true
```

## Структура файлов

```
src/orchestrator/
  common.py          — OrchestratorState, make_llm()
  config.py          — Config dataclass + load_dotenv(override=True)
  mcp_client.py      — MultiServerMCPClient конфиги
  graph.py           — LangGraph граф + supervisor
  agents/
    task_fetcher.py  — получение задания
    coder.py         — генерация + ревью кода
    submitter.py     — сдача в Gitea (REST API)
  main.py            — CLI (typer): run / tools / list
run_task.py          — запуск по файлу с заданием
taskinfo/            — файлы с заданиями (task1info.txt, ...)
solutions/           — локальные копии решений (fallback)
```

## Решения в Gitea

Репозиторий: `https://git.brojs.ru/ababaykin2016/cucumbers-solutions`

Структура: `solutions/<task-id>/solution.<ext>`

Submitter автоматически:
1. Проверяет/создаёт репозиторий
2. Обновляет файл (с SHA для update если уже существует)
3. Делает коммит `feat: solution for <task-id>`

## Известные особенности

- **`PYTHONUTF8=1`** — обязателен в PowerShell для корректного вывода
- **gitea-mcp** запускается с `--python 3.11` (без него SRE module mismatch на Windows)
- **MCP платформы** (`platform.brojs.ru`) пока недоступен как MCP — платформа отдаёт SPA-HTML на всех путях. Задания передаются через `--task-text` или файл.
- **`config.py`** вызывает `load_dotenv(override=True)` и принудительно выставляет `os.environ["OPENAI_API_KEY"]` — иначе langchain-openai игнорирует параметр `api_key`.
- **Submitter без LLM** — мелкие модели (4B) зависают в tool-calling loop, поэтому сдача сделана через прямой REST API.

---

## Agent Team (Claude Code skills)

You are the **Team Lead**. You manage specialized agents, coordinate workflows, and ensure quality.

| Agent | Role | Model |
|-------|------|-------|
| `product-manager` | PRDs, user stories, acceptance criteria | opus |
| `architect` | System design, API contracts, data models | opus |
| `implementer` | Code implementation per PRD and design | inherit |
| `code-reviewer` | Quality, security, performance review | inherit |
| `tester` | Test writing, acceptance criteria validation | sonnet |
| `debugger` | Root cause analysis, bug investigation | inherit |
| `docs-writer` | API docs, architecture docs, changelogs | sonnet |

## Skills

- `/new-feature` — Full pipeline: PRD → design → implement → test → review
- `/fix-bug` — Investigate → RCA → fix → regression test → review
- `/review-code` — Structured code review with severity levels
- `/quick` — Quick targeted change without full pipeline
- `/plan` / `/execute` — Plan then execute step by step
- `/commit` — Stage and commit with conventional commit message
- `/validate` — Full health check: lint, types, tests, build
- `/security-audit` — Security audit against OWASP Top 10

## Boundaries

**ALWAYS:**
- Используй `load_dotenv(override=True)` в config.py
- Запускай с `$env:PYTHONUTF8="1"` в PowerShell
- Сдавай через REST API (не через LLM-агент) — мелкие модели зависают

**NEVER:**
- Коммить `.env` с токенами (он в .gitignore)
- Менять `GITEA_URL` на `git.bro-js.ru` (SSL сломан) — только `git.brojs.ru`
- Использовать sync `agent.invoke()` для MCP-инструментов — только `await agent.ainvoke()`
