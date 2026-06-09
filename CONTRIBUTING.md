# Contributing to CucumbersSWAGents

## Dev Setup

```powershell
# Зависимости + dev-группа (pytest)
uv sync --group dev

# Проверить, что MCP-серверы видны
$env:PYTHONUTF8="1"
python -m orchestrator.main tools

# Демо визуализатора без LLM и токенов
python demo_visual.py

# E2E smoke-тест (без сдачи): весь пайплайн кроме Gitea и журнала
python -m orchestrator.main run --auto --dry-run

# Unit-тесты
pytest
```

`.env` с реальными токенами обязателен для e2e-прогонов. Шаблон: `.env.example`.

---

## Принципы кода

### Детерминированность вместо промптов

Главный инвариант: **что можно сделать кодом — делаем кодом, не промптом.**

Слабые модели (4B–20B) теряют инструкции из середины контекста. Поэтому критические операции вынесены в `code_utils.py` и выполняются детерминированно:

| Функция | Что чинит |
|---------|----------|
| `extract_code_block()` | 5 уровней парсинга: закрытый fence → открытый → любой ``` → эвристика → as-is |
| `strip_prose_prefix()` | Отрезает «Конечно, вот решение:» до первого ``` ``` ``` |
| `fix_legacy_api()` | LangChain 0.x → 1.x: `AgentExecutor`/`LLMChain` → `create_agent` |
| `inject_llm_params()` | 3-слойная замена плейсхолдеров с гарантией кавычек |
| `syntax_error()` | `ast.parse` → точное сообщение с номером строки |

### Async I/O

- Async везде, где есть LLM / MCP / subprocess / httpx
- Sync только для `ast.parse` и `re`
- MCP-инструменты — только `await ainvoke()`, никогда sync `invoke()`

### Пути к Python

В subprocess всегда `VENV_PYTHON` (резолвится при импорте из проектного `.venv`), никогда `sys.executable`. Иначе зависимости задачи конфликтуют с зависимостями оркестратора.

### Reviewer-safety гейт

Вывод reviewer'а принимается **только** если `looks_like_python() and syntax_error() is None`. Слабый reviewer ломает рабочий черновик чаще, чем улучшает его — откат на черновик coder'а дешевле, чем починка.

### LLM-инжекция параметров

Coder и reviewer пишут плейсхолдеры `__LLM_BASE_URL__` / `__LLM_API_KEY__` / `__LLM_MODEL__` вместо реальных значений. `inject_llm_params()` подставляет реальные значения детерминированно после генерации. Двойной inject обязателен: и на черновике, и на ревью.

---

## Архитектурные правила

### Supervisor — pure function

`supervisor` в `graph.py` принимает state и возвращает `next_node`. Никаких побочных эффектов, никакого I/O. Маршрутизация — только по полям state.

### Submitter — только REST API

`submitter.py` использует httpx напрямую, без LLM-агента. Причина: мелкие модели зависают в tool-calling loop при Gitea-операциях. Не менять на MCP/agent подход.

### journal_publisher — условный skip

Нода работает только если одновременно:
- `submission_result.startswith("OK")` — Gitea-push прошёл
- В `platform_tools` есть `task_update_answer` и `task_submit`
- `task_id` — 24-hex ObjectId (реальная задача из журнала, не `task-001`)

При несоблюдении пишет `journal_status="skipped: <причина>"` и молча выходит.

### Завершение графа

- `--dry-run` → стоп после `tester`, submitter и journal_publisher skip
- submitter упал → journal_publisher auto-skip
- taskId не 24-hex → journal_publisher auto-skip

---

## Rework-семантика

Дефолтный `run --auto` берёт только **возвращённые** задачи (`reworkComment != ""`).

Порядок блоков в `task_description` для rework (primacy effect):
1. `═══ КОММЕНТАРИЙ ПРЕПОДАВАТЕЛЯ ═══` + `reworkComment`
2. Условие задачи
3. Предыдущая отклонённая сдача с пометкой «именно это было отклонено — не повторяй»

Слабая модель видит фидбэк первым и исправляет именно то, на что указал препод.

---

## Конфигурация

- `config.py` вызывает `load_dotenv(override=True)` и принудительно выставляет `os.environ["OPENAI_API_KEY"]` — иначе langchain-openai игнорирует параметр `api_key`
- `_env_first(*names)` берёт первое непустое значение — legacy-алиасы (`LM_STUDIO_*`, `PLATFORM_TOKEN`) сосуществуют с каноническими именами
- Алиас модели: `gpt-oss:20b` → `openai/gpt-oss-20b` через `_MODEL_ALIASES` в `config.py`

---

## ALWAYS / NEVER

**Всегда:**
- `$env:PYTHONUTF8="1"` в PowerShell перед запуском
- `transport: "http"` для Journal MCP (не `"streamable_http"`)
- `confirmSubmit=True` в `task_submit`
- Двойной `inject_llm_params` + `fix_legacy_api` — и на черновике, и на ревью
- `VENV_PYTHON` для subprocess решений

**Никогда:**
- Коммитить `.env` с токенами (он в `.gitignore`)
- Менять `GITEA_URL` на `git.bro-js.ru` — SSL сломан, только `git.brojs.ru`
- Sync `agent.invoke()` для MCP-инструментов — только `await ainvoke()`
- Принимать вывод reviewer'а без `syntax_error() is None` гейта
- Передавать `tasks_list[]._id` или `submissionId` вместо `taskId` в journal-вызовы — это разные идентификаторы

---

## Тестирование

На данный момент:
- **E2E smoke**: `run --auto --dry-run` — проверяет весь пайплайн кроме сдачи
- **Unit-тесты**: `pytest` (минимальное покрытие, `tests/` директория)
- **Regression-набор**: в планах (см. Roadmap в README.md)

При изменении `code_utils.py` (особенно `extract_code_block`, `inject_llm_params`) — обязательно проверить на примерах с незакрытыми fence, с голыми плейсхолдерами без кавычек, с prose-prefix.

При изменении промптов в `coder.py` — прогнать dry-run на нескольких rework-задачах перед мержем.

---

## Структура PR

Придерживаться conventional commits:
- `feat:` — новая функциональность
- `fix:` — исправление бага
- `refactor:` — рефакторинг без изменения поведения
- `docs:` — документация

В описании PR указывать: была ли проверка dry-run, какие модули затронуты, есть ли изменения в промптах.
