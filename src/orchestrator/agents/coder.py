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

Если задание требует подключения к языковой модели (LLM) — пиши ровно так,
используя эти три плейсхолдера ДОСЛОВНО (их подставит система, не меняй их):

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

НЕ пиши реальные адреса/ключи. НЕ пиши localhost:1234. НЕ пиши 'fake'.
Только плейсхолдеры {PH_MODEL}, {PH_BASE_URL}, {PH_API_KEY}.

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

Если в задании показан импорт — копируй ИМЕННО его, не заменяй на знакомый из памяти.

Шаги:
1. Прочитай задание и требования к формату вывода.
2. Напиши полный рабочий скрипт, который запускается командой python.
3. Используй плейсхолдеры для параметров LLM (см. выше).
4. Используй ТОЛЬКО современный API из контракта выше.

ПОВТОРЯЮ ГЛАВНОЕ: весь ответ — ОДИН блок ```python ... ```. Ничего вне блока."""


_REVIEWER_SYSTEM = f"""Ты — код-ревьюер. На входе задание и черновик решения.

Проверь:
1. Решает ли код задачу и нет ли синтаксических ошибок.
2. Соответствует ли вывод требуемому в задании формату.
3. Для LLM-подключения должны стоять плейсхолдеры {PH_MODEL}, {PH_BASE_URL}, {PH_API_KEY}
   (не localhost, не 'fake', не реальные ключи). Если нет — поставь их.
4. УСТАРЕВШИЙ API langchain 0.x = ImportError (установлен 1.3.x). Если видишь —
   ОБЯЗАТЕЛЬНО замени:
     ✗ AgentExecutor / create_openai_functions_agent / create_react_agent
       / initialize_agent / LLMChain / from langchain.llms import OpenAI
     ✓ from langchain.agents import create_agent
       from langchain.tools import tool
       agent = create_agent(model=llm, tools=[...], system_prompt="...")

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

        # ── Шаг 1: генерация (стриминг) ──
        viz.notify("coder", "Генерирую решение...", "sub_step")
        coder_messages = [
            SystemMessage(content=_CODER_SYSTEM),
            HumanMessage(content=f"Задание:\n\n{task}"),
        ]
        raw = ""
        async for chunk in coder_llm.astream(coder_messages):
            raw += chunk.content
            update_streaming_code(raw, "генерация")
        clear_streaming_code()

        draft_code = extract_code_block(raw)

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
        reviewed_code = extract_code_block(review_raw)
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
