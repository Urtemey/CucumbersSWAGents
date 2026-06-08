# Plan: CLI Visualizer + Web UI для оркестратора

## Overview

Два самостоятельных компонента, которые подключаются к существующему LangGraph-графу без переписывания бизнес-логики.

**Ключевые решения:**
- `astream_events(version="v2")` даёт нам LLM-события (start/end каждого вызова) без правки агентов
- `coder.py` переходит на `ainvoke()` — иначе sync-вызов заблокирует event loop и спиннер не будет анимироваться
- Для sub-шагов coder/submitter — лёгкий `notify()` хук в visualizer.py (thread-safe через `asyncio.Queue`)
- Web UI: FastAPI + SSE + чистый HTML/JS (без Node.js), Tailwind CDN, Highlight.js для кода

---

## Phase 1: Подготовка — async coder + notify-система

**Goal:** Разблокировать event loop и установить канал sub-step событий.

**Tasks:**
- [ ] `src/orchestrator/agents/coder.py` — заменить `.invoke()` на `await llm.ainvoke()`, сделать `node` async
- [ ] `src/orchestrator/agents/submitter.py` — добавить `notify("submitter", "Проверяю репозиторий...")` перед HTTP-запросами
- [ ] `src/orchestrator/visualizer.py` — создать `asyncio.Queue`-based notify-систему и базовый `AgentVisualizer`
- [ ] Убедиться, что граф в `graph.py` совместим с async node (LangGraph 1.2.0 — да)

**Deliverables:**
- Рабочий async coder
- `visualizer.notify(node, message)` работает из sync и async контекста

**Validation:**
```powershell
$env:PYTHONUTF8="1"
python run_task.py taskinfo\task1info.txt task-001 --dry-run
# Нет "RuntimeWarning: coroutine was never awaited"
```

---

## Phase 2: CLI Visualizer

**Goal:** Красивый ASCII live-дисплей работы оркестратора в терминале.

**Tasks:**
- [ ] `visualizer.py` — `AgentVisualizer` класс с Rich `Live` + `Layout`
- [ ] Рендер графа: ASCII-схема с цветными нодами и spinners (⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏)
- [ ] Рендер лога: прокручиваемый лог последних 20 событий с временными метками
- [ ] Рендер кода: панель с подсветкой синтаксиса (Rich `Syntax`) при генерации кода
- [ ] Рендер результата: финальный статус сдачи
- [ ] Фоновая задача-аниматор: `asyncio.create_task` тикает 10fps, обновляет `live.update()`
- [ ] `main.py._execute_graph` — переключиться на `graph.astream_events(v2)`, фиды в visualizer
- [ ] `main.py._run_async` — создать и запустить visualizer

**Layout схема:**
```
╔══════════════════════════════════════════════════════════════╗
║  🥒 CucumbersSWAGents  •  task-001  •  12:34:05             ║
╠═══════════════════════════╦══════════════════════════════════╣
║  ГРАФ АГЕНТОВ             ║  СОБЫТИЯ                         ║
║                           ║                                  ║
║  START                    ║  12:34:01  supervisor → coder    ║
║    │                      ║  12:34:02  coder: генерирую...   ║
║  [SUPERVISOR] ✓           ║  12:34:15  coder: ревьюю код...  ║
║    │                      ║  12:34:20  supervisor → submit   ║
║  ┌─┴──────────┐           ║  12:34:21  submitter: проверяю   ║
║  │ TASK_FETCH │ —         ║                                  ║
║  │   CODER    │ ⠹ active  ║                                  ║
║  │ SUBMITTER  │ ○ idle    ║                                  ║
║  └────────────┘           ║                                  ║
╠═══════════════════════════╩══════════════════════════════════╣
║  КОД (python)                                                ║
║  1  def solve(n):                                            ║
║  2      return n * 2                                         ║
╚══════════════════════════════════════════════════════════════╝
```

**Deliverables:**
- `src/orchestrator/visualizer.py` (~300 строк)
- Изменённые `main.py`, `coder.py`, `submitter.py`

**Validation:**
```powershell
$env:PYTHONUTF8="1"
python run_task.py taskinfo\task1info.txt task-001 --dry-run
# Видим анимированный граф с живыми спиннерами
```

---

## Phase 3: FastAPI SSE сервер

**Goal:** HTTP-сервер, который запускает оркестратор и стримит события через SSE.

**Tasks:**
- [ ] Установить `fastapi` и `sse-starlette` через uv
- [ ] `src/orchestrator/server.py` — FastAPI приложение:
  - `GET /` → отдаёт `src/web/index.html`
  - `POST /api/run` → принимает `{task_id, task_text, dry_run}`, стартует граф, возвращает `{run_id}`
  - `GET /api/stream/{run_id}` → SSE stream событий `{type, node, message, data}`
  - `GET /api/result/{run_id}` → финальное состояние (код + результат)
- [ ] Хранилище запусков: `dict[run_id, asyncio.Queue]` (in-memory, хватит для одного пользователя)
- [ ] Переиспользовать `AgentVisualizer.notify()` — он же кидает события в SSE-очередь

**SSE event types:**
```
node_start   {"node": "coder"}
node_done    {"node": "coder", "data": "...код..."}
node_error   {"node": "coder", "error": "..."}
llm_start    {"node": "coder", "call": "generate"}
llm_end      {"node": "coder", "tokens": 150}
sub_step     {"node": "coder", "message": "Генерирую решение..."}
result       {"submission_result": "OK: https://..."}
done         {}
```

**Deliverables:**
- `src/orchestrator/server.py`
- Запуск: `uvicorn orchestrator.server:app --reload`

**Validation:**
```powershell
# Терминал 1
uvicorn orchestrator.server:app --port 8765
# Терминал 2
curl -X POST http://localhost:8765/api/run -H "Content-Type: application/json" -d '{\"task_id\":\"t1\",\"task_text\":\"напиши hello world\",\"dry_run\":true}'
# Ответ: {"run_id": "abc123"}
curl http://localhost:8765/api/stream/abc123
# Стрим SSE событий
```

---

## Phase 4: Web UI

**Goal:** Браузерный интерфейс типа deep-agents-ui — граф, события, код.

**Tasks:**
- [ ] `src/web/index.html` — single-page app (~500 строк):
  - Tailwind CDN + Highlight.js CDN (нет node_modules)
  - Форма ввода: task_id + task_text + dry_run checkbox
  - Кнопка "Запустить" → POST /api/run → подписка на SSE
  - SVG-граф агентов с анимацией активного нода (пульсация, цвет)
  - Панель событий: live-лог с иконками по типу события
  - Панель кода: подсвеченный код с появлением по символам (typewriter effect)
  - Статус-бар: текущий агент + таймер
- [ ] CSS-анимации: `@keyframes pulse` для активных нодов, `@keyframes flow` для стрелок

**UI-схема:**
```
┌─────────────────────────────────────────────────────┐
│  🥒 CucumbersSWAGents                    [dark mode] │
├──────────────────┬──────────────────────────────────┤
│  ЗАПУСТИТЬ       │  ГРАФ АГЕНТОВ (SVG)              │
│  Task ID: [   ]  │                                  │
│  Task:   [    ]  │  START → [SUPERVISOR]             │
│  [Запустить]     │           ↓         ↓            │
│                  │  [FETCH] [CODER●] [SUBMIT]        │
├──────────────────┴──────────────────────────────────┤
│  СОБЫТИЯ                    │  КОД                  │
│  ●  coder: генерирую...     │  def solve(n):        │
│  ●  llm_start               │      return n * 2     │
│  ●  coder: ревьюю...        │                       │
└─────────────────────────────────────────────────────┘
```

**Deliverables:**
- `src/web/index.html`

**Validation:**
- Открываем `http://localhost:8765`
- Вводим задачу, жмём кнопку
- Видим анимированный граф с реал-тайм событиями и кодом

---

## Risks

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| `astream_events(v2)` не эмитит события для sync-нод | Средняя | Переключить coder на ainvoke(); добавить notify() хуки |
| Rich Live + asyncio: update из другого треда | Низкая | Использовать `live.update()` только из основного event loop |
| SSE соединение рвётся при долгой генерации | Средняя | Heartbeat ping каждые 15 сек: `data: :keepalive\n\n` |
| Windows консоль: UTF-8 спиннеры не рендерятся | Средняя | Fallback ASCII спиннеры (`/-\|`), colorama уже есть |
| FastAPI конфликт с asyncio loop оркестратора | Средняя | Запускать граф через `asyncio.create_task` внутри FastAPI handler |

---

## Definition of Done

- [ ] CLI: `python run_task.py ... --dry-run` показывает анимированный граф с sub-шагами внутри агентов
- [ ] CLI: спиннер анимируется в реальном времени пока LLM думает (не блокирует event loop)
- [ ] Web: `uvicorn orchestrator.server:app --port 8765` запускается без ошибок
- [ ] Web: браузер показывает живой граф и код при выполнении задачи
- [ ] Web: SSE стрим не рвётся при задаче длиннее 30 секунд
- [ ] Все существующие команды (`swagents run`, `swagents tools`) продолжают работать

## Порядок выполнения

```
Phase 1 (async fix)  →  Phase 2 (CLI viz)  →  Phase 3 (server)  →  Phase 4 (web UI)
     ~30 min               ~2 часа               ~1 час               ~2 часа
```
