"""
task_fetcher: суб-агент, который получает задание с платформы через MCP.
Если MCP платформы недоступен — работает в ручном режиме (task_id передан напрямую).
В обоих случаях фетчит документацию по ссылкам из задания и передаёт coder'у как контекст.
"""
from __future__ import annotations

import html
import re
from typing import Optional

import httpx
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from orchestrator.config import cfg
from orchestrator.common import OrchestratorState, make_llm
from orchestrator import visualizer as viz


# ── Фетчинг документации ──────────────────────────────────────────────────────

def _extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s\)\]\"'<>]+", text)


def _strip_html(raw: str) -> str:
    """
    Извлекает ОСМЫСЛЕННЫЙ контент из HTML без внешних зависимостей.

    Ключевая идея: на доках типа docs.langchain.com первые ~1500 символов —
    чистая навигация ("Skip to main content, Search, Navigation..."), а
    реальный API и примеры кода — глубже. Поэтому:
      1. вырезаем <main>/<article> (убирает меню/шапку/футер целиком)
      2. СОХРАНЯЕМ блоки кода (<pre>/<code>) — для LLM это самое ценное
      3. только потом снимаем остальные теги
    """
    fl = re.DOTALL | re.IGNORECASE

    # 1. полностью выкинуть скрипты/стили/svg
    raw = re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", raw, flags=fl)

    # 2. изолировать основной контент (убирает nav/header/footer/sidebar разом)
    m = re.search(r"<(main|article)\b[^>]*>(.*?)</\1>", raw, flags=fl)
    if m:
        raw = m.group(2)
    else:
        raw = re.sub(r"<(nav|header|footer|aside)[^>]*>.*?</\1>", " ", raw, flags=fl)

    # 3. сохранить код: <pre> → ```...```, <code> → `...`
    def _pre(mm: "re.Match") -> str:
        inner = html.unescape(re.sub(r"<[^>]+>", "", mm.group(1))).strip()
        return f"\n```\n{inner}\n```\n" if inner else " "

    def _code(mm: "re.Match") -> str:
        inner = html.unescape(re.sub(r"<[^>]+>", "", mm.group(1))).strip()
        return f"`{inner}`" if inner else " "

    raw = re.sub(r"<pre[^>]*>(.*?)</pre>", _pre, raw, flags=fl)
    raw = re.sub(r"<code[^>]*>(.*?)</code>", _code, raw, flags=fl)

    # 4. блочные теги → перевод строки (сохраняем структуру)
    raw = re.sub(r"</(p|div|li|h[1-6]|tr|section|ul|ol)>", "\n", raw, flags=re.IGNORECASE)

    # 5. снять остальные теги, декодировать entities, схлопнуть пробелы
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n[ \t]+", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


async def _fetch_doc(url: str, client: httpx.AsyncClient, max_chars: int = 6000) -> Optional[str]:
    """
    Достаёт документацию максимально чистой.

    Docs-сайты на Mintlify (docs.langchain.com и др.) отдают ЧИСТЫЙ markdown
    по <url>.md — без навигации, с примерами кода. Это идеально для LLM,
    поэтому пробуем .md ПЕРВЫМ. Фоллбэк — скрейпинг HTML (_strip_html).
    """
    # Кандидаты в порядке предпочтения
    candidates: list[str] = []
    if not url.endswith((".md", ".txt", ".rst")):
        candidates.append(url.rstrip("/") + ".md")   # Mintlify markdown
    candidates.append(url)

    for u in candidates:
        try:
            resp = await client.get(u, timeout=12.0, follow_redirects=True)
            if resp.status_code != 200:
                continue
            ct = resp.headers.get("content-type", "")
            body = resp.text
            if "markdown" in ct or (u.endswith(".md") and "html" not in ct):
                # уже чистый markdown — не трогаем, это лучший случай
                if len(body.strip()) > 200:
                    return body[:max_chars]
            elif "html" in ct:
                stripped = _strip_html(body)
                if len(stripped.strip()) > 100:
                    return stripped[:max_chars]
            else:
                if len(body.strip()) > 100:
                    return body[:max_chars]
        except Exception:
            continue
    return None


async def _enrich_with_docs(task_description: str) -> str:
    """
    Находит URL-ы в тексте задания, фетчит их содержимое и добавляет
    в конец описания как раздел ДОКУМЕНТАЦИЯ.
    """
    urls = _extract_urls(task_description)
    if not urls:
        return task_description

    # дедупликация, не больше 2 ссылок (слабые модели деградируют на длинном контексте)
    urls = list(dict.fromkeys(urls))[:2]

    docs_sections: list[str] = []
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 SWAGents/1.0"}) as client:
        for url in urls:
            viz.notify("task_fetcher", f"Фетчу: {url[:50]}", "sub_step")
            content = await _fetch_doc(url, client)
            if content and len(content.strip()) > 100:
                docs_sections.append(f"=== Документация: {url} ===\n{content}")

    if not docs_sections:
        return task_description

    enriched = task_description.rstrip()
    enriched += "\n\n\n--- ДОКУМЕНТАЦИЯ ИЗ ССЫЛОК В ЗАДАНИИ ---\n"
    enriched += "\n\n".join(docs_sections)
    return enriched


# ── Нода графа ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Ты — агент получения заданий с учебной платформы platform.brojs.ru.

Твои инструменты позволяют обращаться к платформе по MCP.
Используй доступные инструменты чтобы:
1. Найти задание по task_id (если передан) или получить список всех заданий
2. Прочитать полное описание задания: что нужно сделать, какой язык программирования, какой формат ответа
3. Вернуть ПОЛНЫЙ текст задания

Если инструменты платформы недоступны — попроси пользователя скопировать текст задания вручную.
Верни текст задания в поле task_description.
"""


def make_task_fetcher_node(platform_tools: list):
    llm = make_llm()

    if platform_tools:
        agent = create_react_agent(llm, platform_tools, prompt=SYSTEM_PROMPT)

        async def node(state: OrchestratorState) -> dict:
            task_id = state.get("task_id", "")
            user_msg = (
                f"Получи задание с ID: {task_id}" if task_id
                else "Получи список доступных заданий и выбери первое непройденное"
            )
            result = await agent.ainvoke({"messages": [HumanMessage(content=user_msg)]})
            desc = result["messages"][-1].content

            viz.notify("task_fetcher", "Фетчу документацию из ссылок...", "sub_step")
            enriched = await _enrich_with_docs(desc)
            return {
                "task_description": enriched,
                "prepared": True,
                "messages": result["messages"],
            }

    else:
        # Платформа недоступна — читаем task_description из state напрямую
        async def node(state: OrchestratorState) -> dict:
            desc = state.get("task_description", "")
            if not desc:
                return {
                    "prepared": True,
                    "task_description": (
                        "ВНИМАНИЕ: MCP платформы недоступен. "
                        "Запустите оркестратор с флагом --task-text 'текст задания'"
                    ),
                }
            viz.notify("task_fetcher", "Фетчу документацию из ссылок...", "sub_step")
            enriched = await _enrich_with_docs(desc)
            if enriched != desc:
                n_docs = enriched.count("=== Документация:")
                viz.notify("task_fetcher", f"Загружено {n_docs} доков", "sub_step")
            return {"task_description": enriched, "prepared": True}

    return node
