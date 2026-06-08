# 🥒 CucumbersSWAGents — Deep-Agent, который сдаёт ваши учебные задания за вас

> *«Пока студент спит — агент кодит, тестирует, пушит в Gitea и жмёт `task_submit`. Утром в журнале — `ready_for_review`.»*

---

## 🎤 60-секундный elevator pitch

Представьте: у вас 18 задач в журнале `platform.brojs.ru`. Четыре из них — **возвращённые** на доработку с комментариями препода. Вы открываете терминал, пишете **одну команду**:

```powershell
python -m orchestrator.main run --auto
```

…и идёте пить кофе. Через 1 минуту 17 секунд в журнале статус задачи меняется на `ready_for_review`. Код залит в Gitea, коммит подписан, `commitData` прокинут в журнал, фидбэк препода учтён в новой версии решения. **Ни одного клика. Ни одной строчки, написанной руками.**

Это и есть **CucumbersSWAGents** — deep-agent оркестратор на LangGraph, который закрывает **полный жизненный цикл** учебного задания: от `tasks_list` до `task_submission_status`.

---

## 🧠 Зачем это вообще нужно

Существующие AI-помощники для кода умеют **одну** вещь — сгенерировать сниппет в чате. Но реальная сдача задания — это **семь шагов**:

1. Найти невыполненные/возвращённые задания
2. Прочитать условие + фидбэк препода (если rework)
3. Скачать релевантные доки (Mintlify, LangChain, LangGraph)
4. Сгенерировать код + отревьюить + починить синтаксис
5. Установить зависимости, **запустить** в subprocess, проверить что не падает
6. Запушить в Gitea с правильной структурой папок
7. Дёрнуть `task_update_answer` → `task_submit` → проверить статус

CucumbersSWAGents делает **все семь**. End-to-end. Без человека в цикле.

---

## 🏗 Архитектура: 6 нод, один LangGraph

```
                      ┌──────────────┐
                      │  supervisor  │  (pure-function routing)
                      └──────┬───────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
 ┌─────────────┐     ┌─────────────┐      ┌─────────────┐
 │task_fetcher │ ──▶ │    coder    │ ───▶ │   tester    │
 └─────────────┘     └─────────────┘      └─────────────┘
                                                 │
                             ┌───────────────────┘
                             ▼
                      ┌─────────────┐      ┌──────────────────┐
                      │  submitter  │ ───▶ │journal_publisher │
                      └─────────────┘      └──────────────────┘
                             │                      │
                             └──────────▶ END ◀─────┘
```

| Нода | Что делает | LLM? |
|------|-----------|------|
| `task_fetcher` | Journal MCP → `tasks_list(status=todo)` → фильтр по `reworkComment` → достаёт `task_text` + скрапит Mintlify-доки | **нет** (детерминированно) |
| `coder` | Coder (temp=0.1) → reviewer (temp=0.0) → repair loop (до 2 итераций) → few-shot → авто-fix legacy API | **да** |
| `tester` | `py_compile` → AST static analysis → `pip install` в `.venv` → subprocess (60s) → LLM-оценка по rubric | **да** (только оценка) |
| `submitter` | Gitea REST API (httpx): create/update file, base64, conventional commit | **нет** |
| `journal_publisher` | `task_update_answer(answerType=link, commit={…})` → `task_submit(confirmSubmit=True)` → `task_submission_status` | **нет** |
| `supervisor` | Pure function: state → next node | **нет** |

**Ключевая идея архитектуры**: LLM используется только там, где без неё **нельзя** (генерация кода, оценка результата). Всё остальное — детерминированный код. Это даёт **предсказуемость** и **дешевизну**: мелкая модель (4B–20B) не зависает в tool-calling-loop'ах, не теряет токены на «давайте я подумаю», не галлюцинирует REST-вызовы.

---

## ⚔️ Главный челлендж: слабые модели

Проект работает с **`openai/gpt-oss-20b`** через jrnl-туннель `platform.brojs.ru`. Это **не GPT-4**. Это модель, которая:

- Теряет инструкции из середины контекста
- Галлюцинирует устаревший API LangChain 0.x вместо 1.3.x
- Иногда возвращает «Конечно! Вот ваш код:» вместо самого кода
- Может закрыть code-fence в неправильном месте
- Забывает, что `msg.content` — атрибут, а не словарь

И мы должны заставить её **стабильно** генерировать рабочий, проходящий ревью препода код. Как?

### Принцип: **что можно сделать кодом — делаем кодом, не промптом**

| Защита | Что чинит |
|--------|-----------|
| `extract_code_block()` — **5 уровней** парсинга | Незакрытый fence, prose-prefix, голый код без fence |
| `strip_prose_prefix()` | «Конечно, вот решение:» → выкидывается |
| `fix_legacy_api()` | `AgentExecutor`/`create_react_agent`/`LLMChain` → `create_agent` |
| `inject_llm_params()` — 3-слойная замена | `__LLM_BASE_URL__` → `'…'` с гарантией кавычек даже для голых плейсхолдеров |
| `syntax_error()` — `ast.parse` гейт | Точное сообщение со строкой → передаётся в repair loop |
| Reviewer-safety гейт | Вывод reviewer'а принимается **только** если syntax OK, иначе откат на черновик |
| Few-shot в системном промпте | Слабые модели мимикрируют формат — даём 1 рабочий пример |
| Primacy effect для rework | `reworkComment` препода — **первый блок** в task_description |
| Repair loop (до 2 проходов) | После `ast.parse`-ошибки модель получает точное сообщение и фиксит точечно |

**Reviewer-safety гейт** — особенно ценная штука. Слабый reviewer **ломает** рабочий код чаще, чем улучшает его. Поэтому мы пропускаем его вывод через `looks_like_python() and syntax_error() is None`. Не прошёл — откатываемся на черновик coder'а.

---

## 🔄 Rework-семантика — то, ради чего всё затевалось

Дефолтный вызов `run --auto` **не** берёт случайную задачу. Он берёт **возвращённые** (`reworkComment != ""`). Логика:

1. `_journal_fetch` фильтрует `tasks_list(status=todo)` по непустому `reworkComment`
2. Берёт первую rework
3. Если rework нет и **не** указан `--include-new` → стоп с сообщением «нет задач для пересдачи»
4. **Первым блоком** в `task_description` вклеивается:
   ```
   ═══ КОММЕНТАРИЙ ПРЕПОДАВАТЕЛЯ ПО ВОЗВРАЩЁННОЙ СДАЧЕ ═══
   <reworkComment>
   ```
5. Затем условие из `tasks_list` (если короче 500 симв — добивается через `task_text(taskId)`)
6. Затем **предыдущая отклонённая сдача** с пометкой «именно это было отклонено — не повторяй»

Слабая модель видит фидбэк **первым** (primacy effect) и **поверх** условия — и в 4 из 5 случаев исправляет именно то, на что указал препод.

---

## 🎨 Визуализатор — потому что terminal-арт это весело

Rich Live dashboard, 10 fps, async queue. Каждый прогон выглядит как кино:

- **Баннер**: 6 строк ASCII-арта с градиентом `cyan → magenta → red`
- **Header**: пульсирующий логотип, секундомер `mm:ss`, прогресс-бар `▰▰▰▱▱▱` (6 нод)
- **Active нода**: rounded `╭─╮╰─╯` + пульс `◐◓◑◒` в цвет ноды
- **Done нода**: double `╔═╗╚═╝` + ярко-зелёная ✓
- **Skip нода**: точечная `············` рамка
- **Connector**: радужный анимированный `▼` + искра `✦✧✶✷✸✹`
- **Bottom panel**: live-стрим кода (Syntax monokai) → stdout subprocess → Rich-таблица оценки
- **Финал**: `📦 Gitea: <url>` + `📓 Журнал: ready_for_review`

Не просто для красоты — **observability**. Когда LLM на 47-й секунде зависла, ты **видишь**, на какой ноде. Когда coder уходит в `регенерация` → `ремонт` → `ревью` — видишь все три прохода.

---

## 🔌 Интеграции

### Journal MCP (платформа)
- URL: `https://platform.brojs.ru/jrnl-bh/api/mcp`
- Transport: **`http`** (не `streamable_http` — иначе 4xx!)
- Auth: `Bearer <JOURNAL_TOKEN>`
- Tools used: `tasks_list`, `task_text`, `task_update_answer`, `task_submit`, `task_submission_status`

### Gitea MCP (репозиторий решений)
- Server: `gitea-mcp` через `uvx --python 3.11`
- Repo: `git.brojs.ru/ababaykin2016/cucumbers-solutions`
- Structure: `solutions/<task-id>/solution.<ext>`
- Но **submitter** ходит напрямую в REST API (httpx), минуя MCP — мелкие модели зависают в tool-loop'ах

### LLM (через jrnl-туннель)
- Endpoint: `https://platform.brojs.ru/jrnl-bh/api/inference/v1` (OpenAI-compatible)
- Model: `openai/gpt-oss-20b` (через локальный alias `gpt-oss:20b`)
- `OPENAI_API_KEY = JOURNAL_TOKEN` — переиспользуем токен платформы

---

## 🛡 Boundaries

**ALWAYS:**
- `load_dotenv(override=True)` в config.py
- `$env:PYTHONUTF8="1"` в PowerShell
- Сдача в Gitea — через REST API, **не** через LLM-агент
- В тестере — `VENV_PYTHON`, не `sys.executable`
- Для journal MCP — `transport: "http"`
- В промптах — указывать **версию** LangChain (1.3.x) и список запретных конструкций 0.x

**NEVER:**
- Коммитить `.env`
- Менять `GITEA_URL` на `git.bro-js.ru` (SSL сломан)
- Использовать sync `agent.invoke()` для MCP — только `await ainvoke()`
- Принимать вывод reviewer'а без `syntax_error()` гейта
- Вызывать `task_submit` без `confirmSubmit=True`
- Полагаться на промпт там, где работает код

---

## 📊 Реальные цифры

**Last live run (one rework cycle):**
- Полный e2e цикл: **01:17**
- 6 нод пройдено: fetch → code → test → submit → publish ✓
- Coder: 1 черновик + 1 ревью + 0 repair-итераций
- Tester: pip install 3 deps → subprocess 12s → LLM-оценка 8s
- Submitter: Gitea PUT 201, sha получен
- Journal: `update_answer` ✓ → `submit` ✓ → status `ready_for_review` ✓

**Журнал на момент демо:**
- 18 todo (4 rework + 14 новых)
- 11 done (**все на 100/100**)
- После прогона: +1 `ready_for_review`

---

## 🚀 Что дальше (Roadmap)

- [ ] Передача `reworkComment` в reviewer (сейчас видит только coder)
- [ ] Retry с фидбэком LLM-оценщика (прошлый `score_text` → новая coder-итерация)
- [ ] HITL-aware stdin генератор (понимает `interrupt`/`Command(resume=...)`)
- [ ] `task_comment` при сдаче — постить summary исправлений
- [ ] **Batch-режим**: `run --batch` прогоняет ВСЕ rework последовательно
- [ ] Кеш Mintlify-доков (TTL 24h)
- [ ] Регрессионный набор задач для smoke-теста при изменениях промптов

---

## 🎬 Финальный слайд

> **CucumbersSWAGents** — это не «ещё один AI-помощник для кодинга».
>
> Это **полный жизненный цикл сдачи задания** в одной команде. С учётом фидбэка препода, с реальным запуском кода, с правильным `commitData` в журнале, с устойчивостью к слабой LLM.
>
> Six nodes. One graph. Zero clicks. Ready for review.

```powershell
python -m orchestrator.main run --auto
```

🥒 *Cucumbers don't sleep. Agents don't either.*
