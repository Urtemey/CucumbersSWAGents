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
    """
    Извлекает URL'ы для подгрузки документации, отфильтровывая:
      - localhost / 127.0.0.1 (примеры конфига LM Studio в условиях задания)
      - example.com / your-domain.com / *.local (заглушки)
      - URL'ы на платформу/Gitea/нашу инфру (это не доки)
      - URL'ы внутри блоков кода (примеры подключения, не доки)
    Слабые модели и без того тонут в контексте — лишних доков не нужно.
    """
    # Убираем содержимое блоков ```...``` чтобы не цеплять примерные URL'ы
    code_stripped = re.sub(r"```[\s\S]*?```", " ", text)
    urls = re.findall(r"https?://[^\s\)\]\"'<>]+", code_stripped)

    SKIP_HOSTS = (
        "localhost", "127.0.0.1", "0.0.0.0", "example.com", "example.org",
        "your-domain", "platform.brojs.ru", "git.brojs.ru", "bro-js.ru",
    )
    filtered: list[str] = []
    for u in urls:
        low = u.lower()
        if any(h in low for h in SKIP_HOSTS):
            continue
        if low.endswith((".local", ".test")):
            continue
        filtered.append(u.rstrip(".,;"))   # убираем хвостовую пунктуацию
    return filtered


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


async def _journal_fetch(
    platform_tools: list,
    task_id: str,
    include_new: bool = False,
) -> tuple[str, str]:
    """
    Детерминированный фетч задания через Journal MCP (без LLM!).
    Слабая модель в react-loop зависает на 30+ итерациях — обходим её полностью.

    Семантика по умолчанию: ПЕРЕсдача — берём только задания,
    которые преподаватель вернул на доработку (rework). Это сдачи в
    status='todo' с непустым reworkComment.

    Если include_new=True — fallback на новые todo-задания (без rework).

    Возвращает (description, resolved_task_id) или ("", "") если не удалось.

    Алгоритм:
      1. tasks_list(status="todo") → JSON со списком сдач
      2. Если task_id передан и совпадает — берём именно её (без фильтра rework)
      3. Иначе фильтруем по reworkComment != "" → первая
      4. Если rework нет и include_new — берём первую todo
      5. Текст: task.description из tasks_list; короткий — добиваем task_text(taskId)
    """
    import json

    by_name = {t.name: t for t in platform_tools}
    tasks_list_tool = by_name.get("tasks_list")
    task_text_tool = by_name.get("task_text")
    if not tasks_list_tool:
        return "", ""

    # 1. tasks_list
    viz.notify("task_fetcher", "Запрашиваю tasks_list (todo)...", "sub_step")
    try:
        raw = await tasks_list_tool.ainvoke({"status": "todo"})
    except Exception as e:
        viz.notify("task_fetcher", f"tasks_list ошибка: {type(e).__name__}", "sub_step")
        return "", ""

    # MCP-tools отдают list[{type:'text', text:'...json...'}]
    json_text = ""
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "text" in raw[0]:
        json_text = raw[0]["text"]
    elif isinstance(raw, str):
        json_text = raw
    if not json_text:
        return "", ""

    try:
        data = json.loads(json_text)
        tasks = data.get("tasks", []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, AttributeError):
        return "", ""

    if not tasks:
        viz.notify("task_fetcher", "Нет todo-заданий в журнале", "sub_step")
        return "", ""

    def _is_rework(t: dict) -> bool:
        """Сдача возвращена преподавателем на доработку."""
        return bool((t.get("reworkComment") or "").strip())

    # 2. Явный task_id — точное совпадение (rework-фильтр не применяем)
    chosen = None
    if task_id:
        for t in tasks:
            candidate_ids = (
                str(t.get("taskId", "")),
                str(t.get("_id", "")),
                str(t.get("submissionId", "")),
                str(t.get("task", {}).get("_id", "")),
            )
            if task_id in candidate_ids:
                chosen = t
                break
        if chosen is None:
            viz.notify("task_fetcher", "taskId не найден в журнале", "sub_step")

    # 3. Приоритет — rework (возвращённые на доработку), иначе новая todo.
    # Параметр include_new оставлен для обратной совместимости, но больше
    # не блокирует новые задания — без них агент простаивает.
    if chosen is None:
        rework = [t for t in tasks if _is_rework(t)]
        if rework:
            chosen = rework[0]
            viz.notify("task_fetcher", f"Rework: {len(rework)} — беру первую", "sub_step")
        else:
            chosen = tasks[0]
            viz.notify("task_fetcher", f"Rework нет — беру новую todo ({len(tasks)} доступно)", "sub_step")

    real_task_id = str(chosen.get("taskId") or chosen.get("task", {}).get("_id") or "")
    title = chosen.get("task", {}).get("title", "")
    description = chosen.get("task", {}).get("description", "")
    rework_comment = (chosen.get("reworkComment") or "").strip()
    prev_answer = ""
    answer_obj = chosen.get("answer") or {}
    if isinstance(answer_obj, dict):
        prev_answer = (answer_obj.get("content") or "").strip()

    viz.notify("task_fetcher", f"Задание: {title[:50]}", "sub_step")
    if rework_comment:
        viz.notify("task_fetcher", f"⚠ REWORK: {rework_comment[:60]}", "sub_step")

    # 3. Если description короткий — добиваем task_text
    if task_text_tool and len(description) < 500 and real_task_id:
        try:
            tx_raw = await task_text_tool.ainvoke({"taskId": real_task_id})
            tx = tx_raw[0]["text"] if isinstance(tx_raw, list) and tx_raw else (
                tx_raw if isinstance(tx_raw, str) else ""
            )
            if tx and len(tx) > len(description):
                description = tx
        except Exception:
            pass

    # 4. Собираем финальный текст. Для rework — феедбэк препода ПЕРВЫМ блоком,
    # чтобы дауньская модель его точно прочитала (primacy — самое важное в начале).
    parts: list[str] = []
    if title:
        parts.append(f"# {title}")
    if rework_comment:
        parts.append(
            "═══ КОММЕНТАРИЙ ПРЕПОДАВАТЕЛЯ ПО ВОЗВРАЩЁННОЙ СДАЧЕ ═══\n"
            "Это ПЕРЕсдача. Преподаватель вернул предыдущее решение со следующим замечанием:\n\n"
            f"{rework_comment}\n\n"
            "ОБЯЗАТЕЛЬНО устрани это замечание в новом решении. Игнорировать комментарий нельзя."
        )
    parts.append(description)
    if prev_answer and len(prev_answer) < 4000:
        parts.append(
            "═══ ТВОЯ ПРЕДЫДУЩАЯ СДАЧА (которую вернули) ═══\n"
            f"{prev_answer}\n\n"
            "Учти что именно ЭТО решение было отклонено по замечанию выше — не повторяй ту же ошибку."
        )

    full = "\n\n".join(parts)
    return full, real_task_id


def make_task_fetcher_node(platform_tools: list):
    llm = make_llm()

    if platform_tools:
        async def node(state: OrchestratorState) -> dict:
            task_id = state.get("task_id", "")
            existing_desc = state.get("task_description", "").strip()

            # Если описание УЖЕ передано (из файла через run_task.py) — используем его,
            # MCP не дёргаем
            if existing_desc:
                viz.notify("task_fetcher", "Описание передано — пропускаю MCP", "sub_step")
                enriched = await _enrich_with_docs(existing_desc)
                return {"task_description": enriched, "prepared": True}

            # ── Детерминированный путь (быстрый, без LLM) ──
            # include_new больше не блокирует — фетчим rework и новые задания одинаково.
            viz.notify("task_fetcher", "Journal MCP (rework + новые)...", "sub_step")
            desc, resolved_id = await _journal_fetch(platform_tools, task_id, include_new=True)
            if desc and resolved_id:
                viz.notify("task_fetcher", f"Получено {len(desc)} симв, task_id={resolved_id[:12]}", "sub_step")
                viz.notify("task_fetcher", "Фетчу документацию из ссылок...", "sub_step")
                enriched = await _enrich_with_docs(desc)
                return {
                    "task_description": enriched,
                    "task_id": resolved_id,
                    "prepared": True,
                }

            # MCP отдал пусто или без task_id — react-fallback УБРАН: он терял
            # привязку к taskId и журналу всё равно нельзя было сдать. Лучше
            # явно остановиться, чем писать «unknown» в Gitea без сдачи.
            viz.notify(
                "task_fetcher",
                "MCP вернул пусто / без task_id — нечего решать, останавливаюсь",
                "sub_step",
            )
            return {
                "task_description": "",
                "task_id": "",
                "prepared": True,
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
