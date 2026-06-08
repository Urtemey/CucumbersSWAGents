# CucumbersSWAGents — Claude Code Configuration

## Что это

Deep-agent оркестратор на LangGraph для авто-решения и **пере**сдачи учебных задач на `platform.brojs.ru`.

**Полный цикл**: Journal MCP (fetch rework / new todo) → coder + reviewer → tester (subprocess) → Gitea push → `task_update_answer` + `task_submit` + `task_submission_status`. Без участия человека.

## Стек

| Слой | Технология |
|------|-----------|
| Язык | Python 3.11 |
| Оркестрация | LangGraph + langchain-mcp-adapters |
| LLM | brojs jrnl-туннель → `openai/gpt-oss-20b` (через langchain-openai) |
| MCP журнала | `https://platform.brojs.ru/jrnl-bh/api/mcp` (http, Bearer JOURNAL_TOKEN) |
| MCP Gitea | `gitea-mcp` (stdio, uvx) → `git.brojs.ru` |
| Сдача в Gitea | REST API (httpx) — без LLM |
| CLI | typer + rich Live dashboard |
| Пакетный менеджер | uv |

## Быстрый старт

```powershell
.venv\Scripts\activate
$env:PYTHONUTF8="1"

# Пересдать первое возвращённое (rework) — основной рабочий сценарий
python -m orchestrator.main run --auto

# Пересдать конкретное задание по taskId (24-hex ObjectId из tasks_list)
python -m orchestrator.main run --auto --task-id 6a047cc6a6fe2e4ac16b35ec

# Если rework нет — взять первое новое todo
python -m orchestrator.main run --auto --include-new

# Без сдачи: fetch → code → test → СТОП (Gitea и журнал не дёргаются)
python -m orchestrator.main run --auto --dry-run

# Из локального файла (legacy путь, без MCP) — условие в произвольном .txt
python run_task.py <path-to-task.txt> task-001 --auto --dry-run

# Список MCP-инструментов (gitea + journal)
python -m orchestrator.main tools
```

### Флаги run

| Флаг | Что делает |
|------|-----------|
| `--auto`, `-a` | Без интерактива: авто-сдача после tester'а |
| `--dry-run` | Останавливается после tester'а, не сдаёт |
| `--review`, `-r` | Пауза для просмотра кода перед сдачей |
| `--include-new` | Брать новые todo, если rework нет (по умолчанию — только rework) |
| `--task-id <ObjectId>` | Конкретная задача (rework-фильтр не применяется) |
| `--task-text "..."` | Передать задание текстом, без MCP |

## Архитектура графа

```
START
  └─> supervisor                      (детерминированная маршрутизация)
        ├─> task_fetcher              (Journal MCP: rework → или новые todo)
        ├─> coder                     (генерация + ревью + repair loop + few-shot)
        ├─> tester                    (синтаксис → static → deps → subprocess → LLM-оценка)
        ├─> submitter                 (REST API → Gitea; skip при --dry-run)
        ├─> journal_publisher         (task_update_answer + task_submit + status)
        └─> END
```

### Суб-агенты

| Агент | Файл | Что делает |
|-------|------|-----------|
| `supervisor` | `graph.py` | Pure-function маршрутизация по state |
| `task_fetcher` | `agents/task_fetcher.py` | Детерминированный fetch через Journal MCP (без LLM) + Mintlify-md/HTML scrape доков |
| `coder` | `agents/coder.py` | Coder (temp=0.1) + reviewer (temp=0.0) + repair loop, few-shot, legacy-API auto-fix |
| `tester` | `agents/tester.py` | py_compile → AST static → pip install в `.venv` → subprocess (60s) → LLM-оценка |
| `submitter` | `agents/submitter.py` | Gitea REST API, возвращает `commit_sha`/`repo_url`/`file_path` для journal |
| `journal_publisher` | `agents/journal_publisher.py` | Без LLM: `task_update_answer` → `task_submit` → `task_submission_status` |

### Семантика task_fetcher

- **rework-only по умолчанию**: `_journal_fetch` фильтрует `tasks_list(status="todo")` по `reworkComment != ""`
- Если найдено — берёт первую rework
- Если нет rework и НЕ `--include-new` — останавливается с «нет задач для пересдачи»
- При rework: **первым блоком** в `task_description` вклеивается feedback препода (primacy для слабой модели), затем условие, затем предыдущая сдача с пометкой «именно это вернули»
- Если описание из `tasks_list` короче 500 симв — добивается через `task_text(taskId)`

### Семантика journal_publisher

- **Skip-условия** (нода работает только если все TRUE):
  - `submission_result.startswith("OK")` (Gitea-push прошёл)
  - В platform_tools есть `task_update_answer` И `task_submit`
  - `task_id` — 24-hex ObjectId (т.е. реальная задача из журнала, не локальная вроде `task-001`)
- При skip пишет в state `journal_status="skipped: <причина>"`
- На успех — кладёт `journal_status` от `task_submission_status` (обычно `ready_for_review`, возможно с оценкой)

### Состояние (`OrchestratorState`)

`TypedDict, total=False`. Поля: `task_id`, `task_description`, `prepared`, `generated_code`, `test_results`, `submission_result`, `dry_run`, `retry_count`, `include_new`, **`solution_url`/`repo_url`/`branch`/`commit_sha`/`file_path`/`commit_message`** (для journal_publisher), `journal_status`.

### LLM-инжекция в генерируемый код

Coder + reviewer **не должны** помнить длинные значения — пишут плейсхолдеры `__LLM_BASE_URL__`/`__LLM_API_KEY__`/`__LLM_MODEL__`. `inject_llm_params()` детерминированно подставляет реальные значения **с гарантией кавычек** (3-слойная замена: `"PH"` → `'val'`, `'PH'` → `'val'`, голый `PH` → `'val'`). Плюс типовые заглушки `localhost:1234`, `api_key='fake'`, `<название модели>`.

## Робастность под слабые модели

Принцип: **что можно сделать кодом — делаем кодом, не промптом.** Слабые модели (4–20B) теряют инструкции из середины контекста и галлюцинируют устаревший API.

### Детерминированные защиты (`code_utils.py`)

| Функция | Что делает |
|---------|-----------|
| `extract_code_block()` | 5 уровней: закрытый fence → открытый → любой ``` → эвристика по `import`/`def` → as-is. Режет хвостовую болтовню. |
| `strip_prose_prefix()` | Отрезает «Конечно! Вот решение:» до первого ```` ``` ```` |
| `fix_legacy_api()` | langchain 0.x → 1.x: `AgentExecutor`/`create_react_agent`/`LLMChain`/`langchain.llms.OpenAI` → `create_agent` |
| `inject_llm_params()` | 3-слойная подстановка с гарантией кавычек |
| `syntax_error()` | `ast.parse` → точное сообщение с номером строки |

### Защиты в `coder.py`

- **Few-shot** в системном промпте — слабые модели мимикрируют формат
- **Авто-регенерация** если ответ < 120 симв или не похож на Python (1 повтор со строгим напоминанием)
- **Repair loop**: после `ast.parse`-ошибки модель получает ТОЧНОЕ сообщение и фиксит точечно. До 2 проходов.
- **Reviewer-safety**: вывод reviewer'а принимается ТОЛЬКО при `looks_like_python() and syntax_error() is None`. Иначе откат на черновик.
- **Двойной inject + fix_legacy_api**: и на draft, и на reviewed

### API-контракт в промпте

Жёстко зафиксированы:
1. langchain 1.x: `from langchain.agents import create_agent`, `from langchain.tools import tool`
2. langgraph: `StateGraph`/`START`/`END`/`InMemorySaver`/`interrupt` из правильных модулей
3. **Messages API** — `msg.content` (атрибут), а не `msg.get("content")`. Без этого правила модель пишет AttributeError-код.

### Защиты в `tester.py`

- Зависимости ставятся **в проектный `.venv`** через `VENV_PYTHON` (резолв при импорте)
- Источники deps: `pip install` из задания + AST-импорты из сгенерированного кода
- LLM генерирует stdin-сценарий (для `input()` циклов), включая `exit` для chat'ов
- Subprocess стримит stdout построчно в визуализатор
- Stderr **целиком** (последние 1500 симв) — без агрессивного фильтра, чтобы Traceback не терял `File:line`

### Защиты при пересдаче (rework)

- Feedback препода вклеивается **первым** блоком (primacy effect) с маркером `═══ КОММЕНТАРИЙ ПРЕПОДАВАТЕЛЯ ПО ВОЗВРАЩЁННОЙ СДАЧЕ ═══`
- Предыдущая сдача (`answer.content`) добавляется с пометкой «именно это было отклонено — не повторяй»
- В визуале `task_fetcher` пишет `⚠ REWORK: <preview>` в sub-step

## Визуализатор (`visualizer.py`)

CLI Rich Live, 10 fps, async queue для notify-событий, 6-нодовый пайплайн.

| Элемент | Реализация |
|---------|-----------|
| Баннер | 6 строк ASCII-арта с градиентом cyan→magenta→red построчно |
| Header | Пульсирующий логотип, `mm:ss`, прогресс-бар `▰▰▰▱▱▱` (4 → 6 нод), активная нода с искрой |
| Active нода | Rounded `╭─╮╰─╯` + пульс `◐◓◑◒` в цвет ноды |
| Done нода | Double `╔═╗╚═╝` + ярко-зелёная ✓ |
| Skip нода | Точечная `············` рамка |
| Connector | Радужная анимированная `▼` + искра `✦✧✶✷✸✹` для active, зелёная для done |
| Bottom panel | Стрим кода (Syntax monokai) → stdout скрипта → **Rich-таблица** оценки → финальный «🎉 УСПЕХ» |
| Финальный экран | `📦 Gitea: <url>` + `📓 Журнал: <status>` |

API:
- `viz.node_start(name)` / `node_done(name)` / `node_error(name, err)` / `node_skip(name)`
- `viz.set_code(text)` / `set_test_results(text)` / `set_result(url)` / `set_journal_status(s)`
- `visualizer.update_streaming_code(buf, label)` — live-стриминг
- `visualizer.notify(node, msg, etype)` — push событий

Лейблы стрима: `генерация`, `регенерация`, `ремонт`, `ревью`, `запуск`, `вывод`, `оценка`.

## Конфигурация (.env)

```env
# ── LLM (через brojs jrnl-туннель к их inference) ────────────
# Канонические имена. LM_STUDIO_* всё ещё поддерживаются как fallback.
LLM_BASE_URL=https://platform.brojs.ru/jrnl-bh/api/inference/v1
LLM_MODEL=gpt-oss:20b
OPENAI_API_KEY=lm-studio          # заглушка, config подставит JOURNAL_TOKEN

# ── Gitea ────────────────────────────────────────────────────
GITEA_URL=https://git.brojs.ru
GITEA_TOKEN=...
GITEA_OWNER=ababaykin2016

# ── Journal MCP ──────────────────────────────────────────────
# URL по умолчанию зашит в config.py — можно оставить пустым
PLATFORM_MCP_URL=https://platform.brojs.ru/jrnl-bh/api/mcp
JOURNAL_TOKEN=jrnl_...             # platform.brojs.ru → профиль → токены
                                   # PLATFORM_TOKEN — legacy-алиас

# ── Куда сдавать ─────────────────────────────────────────────
SOLUTIONS_REPO=cucumbers-solutions
AUTO_CREATE_REPO=true
```

`_env_first()` берёт первое непустое из перечисленных переменных — поэтому legacy и canonical имена сосуществуют.

## Структура файлов

```
src/orchestrator/
  common.py               — OrchestratorState (TypedDict total=False), make_llm()
  config.py               — Config + _env_first(), дефолтные URL'ы platform/journal
  code_utils.py           — extract/inject/fix_legacy/strip_prose/syntax_error
  mcp_client.py           — gitea + journal MCP configs (http transport)
  graph.py                — LangGraph 6-нодовый граф + supervisor routing
  visualizer.py           — Rich Live dashboard (баннер, нода, стрим, метрики)
  runlog.py               — файловый лог (logs/<task>_<ts>.log)
  agents/
    task_fetcher.py       — Journal MCP fetch (rework-first) + docs enrichment
    coder.py              — coder + reviewer + repair loop
    tester.py             — pipeline тестирования
    submitter.py          — Gitea REST API + структурированный return для journal
    journal_publisher.py  — task_update_answer + task_submit + status (без LLM)
  main.py                 — typer CLI: run / tools / list
run_task.py               — legacy entrypoint (произвольный .txt с условием)
logs/                     — файловые логи прогонов
solutions/                — локальные копии (fallback если Gitea недоступен)
```

## Решения в Gitea

Репозиторий: `https://git.brojs.ru/ababaykin2016/cucumbers-solutions`
Структура: `solutions/<task-id>/solution.<ext>`

Submitter:
1. Проверяет/создаёт репозиторий (`auto_init=True`)
2. Берёт SHA если файл уже есть (для update вместо create)
3. PUT с base64-контентом, коммит `feat: solution for <task-id>`
4. Возвращает в state: `solution_url`, `repo_url`, `branch="main"`, `commit_sha`, `file_path`, `commit_message`

## Сдача в журнал

`journal_publisher` (без LLM) последовательно:
1. `task_update_answer(taskId, answerType="link", content=<gitea_url>, commit={repoUrl, branch, commitSha, message, files=[{path,url}]})`
2. `task_submit(taskId, confirmSubmit=True)`
3. `task_submission_status(taskId)` → парсит status/grade/feedback

Состояния, которые видны в финальном экране:
- `ready_for_review` — отправлено преподу
- `done (оценка: True)` — принято
- `todo` с reworkComment — снова на доработку
- `skipped: ...` — нода намеренно пропущена

## Известные особенности

- **`PYTHONUTF8=1`** обязателен в PowerShell для корректного вывода
- **gitea-mcp** запускается с `--python 3.11` (без него SRE module mismatch на Windows)
- **Journal MCP** требует `transport: "http"`, НЕ `"streamable_http"` (иначе 4xx)
- **`config.py`** вызывает `load_dotenv(override=True)` и принудительно выставляет `os.environ["OPENAI_API_KEY"]` — иначе langchain-openai игнорирует параметр `api_key`
- **Submitter без LLM** — мелкие модели (4B) зависают в tool-calling loop
- **Locale-aware**: `cfg.lm_model="gpt-oss:20b"` → API ждёт `openai/gpt-oss-20b` (см. `_MODEL_ALIASES`)
- **HITL-задачи**: задания с `interrupt`/`Command(resume=...)` subprocess-тестом не покрываются полноценно — он не может корректно эмулировать human input. Tester отметит timeout 60s — это **не** автоматически провал.

## Boundaries

**ALWAYS:**
- `load_dotenv(override=True)` в config.py
- `$env:PYTHONUTF8="1"` в PowerShell
- Сдавай в Gitea через REST API, не через LLM-агент
- В тестере используй `VENV_PYTHON` (проектный .venv)
- Промптовый pin: указывай **версию** langchain (1.3.x) и список запретных конструкций 0.x
- Для journal MCP — `transport: "http"`

**NEVER:**
- Коммить `.env` с токенами (он в .gitignore)
- Менять `GITEA_URL` на `git.bro-js.ru` (SSL сломан) — только `git.brojs.ru`
- Использовать sync `agent.invoke()` для MCP-инструментов — только `await ainvoke()`
- Полагаться на промпт там, где работает код: подстановка параметров, fix legacy API, извлечение кода — всё детерминированно
- Принимать вывод reviewer'а без `syntax_error()` гейта — слабый reviewer ломает рабочий черновик
- Вызывать `task_submit` без `confirmSubmit=True` — MCP отвергнет
- Передавать `tasks_list[]._id` или `submissionId` вместо `taskId` в journal-вызовы — это разные ID

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
