"""
coder: генерирует код решения задачи.

Робастность для слабых моделей:
  - LLM пишет код с ПЛЕЙСХОЛДЕРАМИ для параметров подключения.
    Реальные base_url/api_key/model подставляет Python детерминированно
    (inject_llm_params) — модель не должна помнить и копировать длинные значения.
  - Извлечение кода из ответа — устойчивый регекс (extract_code_block),
    а не "ответь APPROVED или верни код".
  - Reviewer только ИСПРАВЛЯЕТ код; если он вернул прозу без кода —
    откатываемся на черновик coder'а (не сохраняем болтовню как решение).
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from orchestrator.common import OrchestratorState, make_llm
from orchestrator import visualizer as viz
from orchestrator.visualizer import update_streaming_code, clear_streaming_code
from orchestrator.code_utils import (
    extract_code_block,
    looks_like_python,
    inject_llm_params,
    syntax_error,
    fix_legacy_api,
    strip_prose_prefix,
    PH_BASE_URL,
    PH_API_KEY,
    PH_MODEL,
)


# Системный промпт сделан максимально простым и однозначным.
# Самое важное правило (формат вывода) — в начале И в конце (primacy + recency),
# т.к. слабые модели "теряют" инструкции из середины контекста.
_CODER_SYSTEM = f"""Ты — Python-разработчик. Пиши рабочий код для учебного задания.

ГЛАВНОЕ ПРАВИЛО: ответь ОДНИМ блоком ```python ... ``` и больше ничем.
Без вступлений, без объяснений до или после кода.

═══ КРИТИЧНО: ТОЧНОЕ СОБЛЮДЕНИЕ ТРЕБОВАНИЙ ЗАДАНИЯ ═══
Если в задании ЯВНО указан конкретный LLM-фреймворк, модель, провайдер или
конкретные значения параметров — ИСПОЛЬЗУЙ ИМЕННО ИХ ДОСЛОВНО. Не заменяй
на плейсхолдеры, не подставляй свои значения. Преподаватель проверяет код
визуально и завернёт сдачу за несоответствие.

Примеры:
  • Задание говорит «использовать Ollama, модель llama3» →
      from langchain_ollama import ChatOllama
      llm = ChatOllama(model="llama3", temperature=0.7)
  • Задание говорит «использовать Anthropic Claude» →
      from langchain_anthropic import ChatAnthropic
      llm = ChatAnthropic(model="claude-3-5-sonnet-latest")
  • Задание говорит «chunk_size=500, chunk_overlap=50» →
      RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
  • Задание говорит «температура 0.2» → temperature=0.2 (а не 0.7)
  • Задание показывает конкретный импорт → копируй ровно его

ТОЛЬКО ЕСЛИ задание НЕ называет конкретный LLM-фреймворк (просто «подключи
LLM», без указания провайдера) — используй ChatOpenAI с плейсхолдерами:

```python
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

llm = ChatOpenAI(
    model="{PH_MODEL}",
    base_url="{PH_BASE_URL}",
    api_key=SecretStr("{PH_API_KEY}"),
    temperature=0.7,
)
```

Плейсхолдеры {PH_MODEL}, {PH_BASE_URL}, {PH_API_KEY} — ТОЛЬКО для этого случая.
Не пиши localhost:1234 / 'fake' / реальные ключи. Если задание называет
конкретный фреймворк (Ollama, Anthropic и т.п.) — плейсхолдеры НЕ ИСПОЛЬЗУЙ,
пиши параметры так, как указано в задании.

═══ API-КОНТРАКТ (установлено: langchain 1.3.x, langgraph 0.x) ═══
Используй ТОЛЬКО современный API. Старый API НЕ установлен и даст ImportError.

ПРАВИЛЬНО (langchain 1.x):
  from langchain.agents import create_agent
  from langchain.tools import tool
  agent = create_agent(model=llm, tools=[...], system_prompt="...")
  result = agent.invoke({{"messages": [{{"role": "human", "content": "..."}}]}})

ЗАПРЕЩЕНО (старый langchain 0.x — НЕ существует, ImportError):
  ✗ from langchain.agents import AgentExecutor
  ✗ create_openai_functions_agent / create_react_agent / initialize_agent
  ✗ from langchain.chains import LLMChain
  ✗ from langchain.llms import OpenAI

LangGraph: from langgraph.graph import StateGraph, START, END
           from langgraph.checkpoint.memory import InMemorySaver
           interrupt/Command — из langgraph.types

═══ MESSAGES API ═══
result = agent.invoke({{"messages": [...]}}) возвращает dict с ключом "messages",
где каждое сообщение — Pydantic-объект (HumanMessage/AIMessage/ToolMessage),
НЕ python-dict! Обращайся через АТРИБУТЫ:
  ✓ msg.content                          — текст сообщения
  ✓ msg.type / msg.__class__.__name__    — тип (human/ai/tool)
  ✓ getattr(msg, "tool_calls", None)     — для AIMessage
  ✗ msg.get("content")                   — AttributeError!
  ✗ msg["content"]                       — TypeError!

Если в задании показан импорт — копируй ИМЕННО его, не заменяй на знакомый из памяти.

Шаги:
1. Прочитай задание и требования к формату вывода.
2. Напиши полный рабочий скрипт, который запускается командой python.
3. Используй плейсхолдеры для параметров LLM (см. выше).
4. Используй ТОЛЬКО современный API из контракта выше.

═══ ПРИМЕР ИДЕАЛЬНОГО ОТВЕТА (повтори стиль) ═══
Задание: "Напиши простой чат с LLM в цикле."
Ответ:
```python
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

llm = ChatOpenAI(
    model="{PH_MODEL}",
    base_url="{PH_BASE_URL}",
    api_key=SecretStr("{PH_API_KEY}"),
    temperature=0.7,
)

while True:
    q = input("Ты: ").strip()
    if not q or q.lower() in ("exit", "quit", "выход"):
        break
    print("Бот:", llm.invoke(q).content)
```

ПОВТОРЯЮ ГЛАВНОЕ: весь ответ — ОДИН блок ```python ... ```. Ничего вне блока."""


_REVIEWER_SYSTEM = f"""Ты — код-ревьюер. На входе задание и черновик решения.

Проверь:
1. Решает ли код задачу и нет ли синтаксических ошибок.
2. Соответствует ли вывод требуемому в задании формату.
3. ТОЧНОЕ соответствие требованиям задания. ЕСЛИ задание ЯВНО называет:
   • конкретный LLM-фреймворк/провайдер (Ollama, Anthropic, langchain_ollama
     и т.п.) — код ДОЛЖЕН использовать ИМЕННО его. Не «подменяй» на ChatOpenAI.
   • конкретные значения параметров (chunk_size, chunk_overlap, temperature,
     model, top_k и т.п.) — числа в коде ДОЛЖНЫ совпадать с теми, что в задании.
   Если видишь несоответствие — ИСПРАВЬ. Преподаватель завернёт сдачу.
   ТОЛЬКО если задание не указывает провайдера явно — должны стоять
   плейсхолдеры {PH_MODEL}, {PH_BASE_URL}, {PH_API_KEY} для ChatOpenAI.
4. УСТАРЕВШИЙ API langchain 0.x = ImportError (установлен 1.3.x). Если видишь —
   ОБЯЗАТЕЛЬНО замени:
     ✗ AgentExecutor / create_openai_functions_agent / create_react_agent
       / initialize_agent / LLMChain / from langchain.llms import OpenAI
     ✓ from langchain.agents import create_agent
       from langchain.tools import tool
       agent = create_agent(model=llm, tools=[...], system_prompt="...")
5. Сообщения в result["messages"] — Pydantic-объекты, не dict.
   Если видишь msg.get("content") или msg["content"] — ЗАМЕНИ на msg.content.
   Если видишь msg.get("tool_calls") — ЗАМЕНИ на getattr(msg, "tool_calls", None).
6. ЕСЛИ в задании есть блок «КОММЕНТАРИЙ ПРЕПОДАВАТЕЛЯ ПО ВОЗВРАЩЁННОЙ СДАЧЕ»
   (это пересдача rework) — ОБЯЗАТЕЛЬНО проверь что замечание устранено.
   Это самое важное правило для rework: если код снова не учитывает фидбэк
   препода — он снова получит rework. Если видишь что замечание не отработано
   (например требуется FastMCP, а в коде его нет) — добавь / исправь сам.
7. ЕСЛИ в задании есть блок «ФИДБЭК ЛЛМ-ОЦЕНЩИКА ПРОШЛОЙ ИТЕРАЦИИ» —
   это значит предыдущая генерация уже была оценена и provалила какие-то
   критерии. Прицельно устрани перечисленные ПРОБЛЕМЫ. Не повторяй ошибки.

ФОРМАТ ОТВЕТА — строго один блок ```python ... ``` с финальным кодом.
Если код уже хороший — верни его без изменений в том же блоке.
Если есть проблемы — верни ИСПРАВЛЕННЫЙ полный код в блоке.
Никакого текста вне блока ```python ... ```."""


_REPAIR_SYSTEM = f"""Ты — Python-разработчик. В коде синтаксическая ошибка.

Тебе дадут код и ТОЧНОЕ сообщение об ошибке (номер строки и текст).
Исправь ТОЛЬКО эту ошибку, не переписывая логику. Верни ПОЛНЫЙ исправленный код.

ФОРМАТ ОТВЕТА: строго один блок ```python ... ``` и больше ничего.
Сохрани плейсхолдеры {PH_MODEL}, {PH_BASE_URL}, {PH_API_KEY} если они есть."""


async def _repair_syntax(llm, code: str, err: str, max_passes: int = 2) -> str:
    """
    Детерминированный цикл: пока есть SyntaxError — точечный фикс.
    Каждый проход даёт модели ТОЧНОЕ сообщение об ошибке (не "что-то не так").
    Это резко поднимает успех слабых моделей — у них узкая, понятная задача.
    """
    for i in range(max_passes):
        viz.notify("coder", f"Чиню синтаксис (проход {i + 1})...", "sub_step")
        messages = [
            SystemMessage(content=_REPAIR_SYSTEM),
            HumanMessage(content=f"ОШИБКА: {err}\n\nКОД:\n```python\n{code}\n```"),
        ]
        raw = ""
        async for chunk in llm.astream(messages):
            raw += chunk.content
            update_streaming_code(raw, "ремонт")
        clear_streaming_code()

        fixed = extract_code_block(raw)
        if not looks_like_python(fixed):
            return code  # модель не вернула код — оставляем что было
        err2 = syntax_error(fixed)
        code = fixed
        if err2 is None:
            return code
        err = err2
    return code


def make_coder_node():
    coder_llm = make_llm(temperature=0.1).with_retry(stop_after_attempt=3, wait_exponential_jitter=True)
    reviewer_llm = make_llm(temperature=0.0).with_retry(stop_after_attempt=3, wait_exponential_jitter=True)

    async def node(state: OrchestratorState) -> dict:
        task = state.get("task_description", "")

        # Если это regenerate — вклеиваем фидбэк прошлой оценки В НАЧАЛО task'а
        # (primacy effect для слабой модели). Это работает в паре с правилом №7
        # reviewer'а и системным напоминанием в coder'е.
        prev_feedback = state.get("previous_score_feedback", "").strip()
        if prev_feedback:
            task = (
                "═══ ФИДБЭК ЛЛМ-ОЦЕНЩИКА ПРОШЛОЙ ИТЕРАЦИИ ═══\n"
                "Предыдущая генерация была оценена и провалила критерии. "
                "ОБЯЗАТЕЛЬНО устрани перечисленные проблемы:\n\n"
                f"{prev_feedback}\n\n"
                "═══ САМО ЗАДАНИЕ (НЕ ПОВТОРЯЙ ОШИБКИ ВЫШЕ) ═══\n\n"
                + task
            )

        # ── Шаг 1: генерация (стриминг) с авто-регеном если короткий вывод ──
        # Слабая модель часто плюёт "Конечно!" или 3 строки. Регенерируем со
        # строгим напоминанием — это эквивалент "ты не понял, попробуй ещё".
        MIN_CODE_CHARS = 120
        draft_code = ""
        raw = ""
        for attempt in range(2):
            label = "генерация" if attempt == 0 else "регенерация"
            viz.notify("coder", f"{'Генерирую' if attempt == 0 else 'Регенерирую'} решение...", "sub_step")
            extra = ""
            if attempt > 0:
                extra = (
                    "\n\nВНИМАНИЕ: предыдущий ответ был слишком коротким или не содержал кода. "
                    "Верни ПОЛНОЕ рабочее решение одним блоком ```python ... ```. Никакого текста вне блока."
                )
            coder_messages = [
                SystemMessage(content=_CODER_SYSTEM),
                HumanMessage(content=f"Задание:\n\n{task}{extra}"),
            ]
            raw = ""
            async for chunk in coder_llm.astream(coder_messages):
                raw += chunk.content
                update_streaming_code(raw, label)
            clear_streaming_code()

            draft_code = extract_code_block(strip_prose_prefix(raw))
            if len(draft_code) >= MIN_CODE_CHARS and looks_like_python(draft_code):
                break
            viz.notify("coder", f"Ответ слишком короткий ({len(draft_code)} симв) — повтор", "sub_step")

        # ── Шаг 1.5: детерминированный фикс legacy API ──
        # Слабая модель пишет langchain 0.x по памяти — чиним кодом, не промптом.
        draft_code, applied = fix_legacy_api(draft_code)
        if applied:
            viz.notify("coder", f"Авто-фикс legacy API: {len(applied)} замен", "sub_step")

        # ── Шаг 2: детерминированный синтаксис-гейт ──
        # ast.parse мгновенно ловит оборванный/битый вывод слабой модели.
        # Чиним ТОЧЕЧНО с конкретным сообщением об ошибке.
        err = syntax_error(draft_code)
        if err is not None:
            viz.notify("coder", f"Синтаксис: {err[:40]}", "sub_step")
            draft_code = await _repair_syntax(coder_llm, draft_code, err)

        # ── Шаг 3: ревью (стриминг) ──
        viz.notify("coder", "Ревьюю код...", "sub_step")
        review_messages = [
            SystemMessage(content=_REVIEWER_SYSTEM),
            HumanMessage(content=f"Задание:\n{task}\n\nЧерновик решения:\n```python\n{draft_code}\n```"),
        ]
        review_raw = ""
        async for chunk in reviewer_llm.astream(review_messages):
            review_raw += chunk.content
            update_streaming_code(review_raw, "ревью")
        clear_streaming_code()

        # Reviewer безопасен: его вывод принимается ТОЛЬКО если это валидный
        # Python И он компилируется. Иначе слабый reviewer мог сломать
        # рабочий черновик — откатываемся на draft.
        reviewed_code = extract_code_block(strip_prose_prefix(review_raw))
        reviewed_code, _ = fix_legacy_api(reviewed_code)
        if looks_like_python(reviewed_code) and syntax_error(reviewed_code) is None:
            final_code = reviewed_code
        else:
            reason = "не код" if not looks_like_python(reviewed_code) else "битый синтаксис"
            viz.notify("coder", f"Ревью отклонено ({reason}) — беру черновик", "sub_step")
            final_code = draft_code

        # ── Шаг 4: финальный синтаксис-гейт + подстановка параметров ──
        err = syntax_error(final_code)
        if err is not None:
            viz.notify("coder", f"Финальный фикс: {err[:35]}", "sub_step")
            final_code = await _repair_syntax(coder_llm, final_code, err)

        final_code = inject_llm_params(final_code)

        viz.notify("coder", "Готово", "node_done")
        return {
            "generated_code": final_code,
            "messages": [],
        }

    return node
