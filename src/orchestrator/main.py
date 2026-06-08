"""
CLI-точка входа оркестратора.

  swagents run                          # fetch -> code -> submit
  swagents run --task-id 42             # решить конкретную задачу
  swagents run --task-text "..."        # передать текст задачи напрямую
  swagents tools                        # показать MCP-инструменты
  swagents list                         # список задач с платформы
"""
from __future__ import annotations

import asyncio
import io
import sys
from typing import Optional

# Принудительно UTF-8 для Windows-консоли
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(help="CucumbersSWAGents - deep-agent оркестратор для platform.brojs.ru")
console = Console()


def _explain_llm_error(exc: BaseException) -> Optional[str]:
    """
    Распознаёт ошибки LLM-провайдера в обёртке LangGraph и возвращает
    понятное сообщение. None — если ошибка не про LLM (пробросить дальше).
    """
    import re
    from datetime import datetime

    # Собираем всю цепочку (LangGraph оборачивает оригинал в __cause__/__context__)
    chain: list[str] = []
    seen: set[int] = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        chain.append(f"{type(cur).__name__}: {cur}")
        for grp in getattr(cur, "exceptions", []) or []:   # ExceptionGroup
            chain.append(f"{type(grp).__name__}: {grp}")
        cur = cur.__cause__ or cur.__context__
    full = "\n".join(chain)

    is_rate = (
        "RateLimitError" in full
        or "429" in full
        or "Rate limit exceeded" in full
        or "free-models-per-day" in full
    )
    if is_rate:
        reset_hint = ""
        m = re.search(r"RateLimit-Reset['\"]?\s*:\s*['\"]?(\d{10,13})", full)
        if m:
            ts = int(m.group(1))
            if ts > 1_000_000_000_000:   # миллисекунды
                ts //= 1000
            try:
                reset_hint = f"\nЛимит сбросится примерно: {datetime.fromtimestamp(ts):%Y-%m-%d %H:%M}"
            except (ValueError, OSError):
                pass
        return (
            "[bold]Лимит запросов OpenRouter исчерпан[/] (HTTP 429, free-models-per-day).\n"
            "Бесплатная модель ограничена ~50 запросами в день, и они закончились."
            f"{reset_hint}\n\n"
            "Что делать:\n"
            "  • Подождать сброса суточного лимита\n"
            "  • Сменить [bold]LM_STUDIO_MODEL[/] в .env на другую бесплатную модель\n"
            "  • Добавить кредиты на OpenRouter (10$ → 1000 запросов/день)\n"
            "  • Гонять реже: один прогон = несколько LLM-вызовов "
            "(coder + ревью + tester + сам тестируемый скрипт)"
        )

    if "APIConnectionError" in full or "APITimeoutError" in full:
        return f"[bold]Нет связи с LLM API[/].\n{chain[-1][:300]}"
    if "AuthenticationError" in full or "401" in full:
        return "[bold]Неверный API-ключ[/] (HTTP 401). Проверь OPENAI_API_KEY в .env."

    return None


def _extract_score_feedback(test_results: str) -> str:
    """
    Достаёт из отчёта tester'а только содержательные секции для coder-retry:
    ОЦЕНКА:, ПРОБЛЕМЫ:, ВЕРДИКТ:, ПРОЦЕНТ: и [STDERR].
    Stdout и meta-строки (СИНТАКСИС/ПАТТЕРНЫ/DEPS) опускаем — это шум для нового coder'а.
    """
    if not test_results:
        return ""
    sections: list[str] = []
    keep = False
    buf: list[str] = []
    for line in test_results.splitlines():
        ls = line.strip()
        # Старт смысловой секции
        if ls.startswith(("ОЦЕНКА:", "ПРОБЛЕМЫ:", "ВЕРДИКТ:", "ПРОЦЕНТ:")):
            if buf:
                sections.append("\n".join(buf).strip())
                buf = []
            keep = True
            buf.append(line)
        elif ls.startswith("[STDERR]"):
            if buf:
                sections.append("\n".join(buf).strip())
                buf = []
            keep = True
            buf.append(line)
        elif ls.startswith("["):
            # Любая другая [МЕТА] — закрываем текущую секцию
            if buf:
                sections.append("\n".join(buf).strip())
                buf = []
            keep = False
        elif keep:
            buf.append(line)
    if buf:
        sections.append("\n".join(buf).strip())
    out = "\n\n".join(s for s in sections if s).strip()
    return out[:4000]   # cap чтобы не раздувать coder-промпт


async def _run_async(task_id: str, task_text: str, dry_run: bool, review: bool = False, auto: bool = False, include_new: bool = False) -> None:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from orchestrator.config import cfg
    from orchestrator.graph import build_graph
    from orchestrator.mcp_client import build_gitea_server_config, build_platform_server_config
    from langchain_core.messages import HumanMessage
    from orchestrator.common import OrchestratorState

    console.print(Panel("[bold cyan]CucumbersSWAGents[/] - запуск оркестратора", expand=False))

    servers: dict = {}
    try:
        servers["gitea"] = build_gitea_server_config()
    except ValueError as e:
        console.print(f"[yellow]Gitea MCP недоступен: {e}[/]")

    if cfg.platform_mcp_url:
        servers["platform"] = build_platform_server_config()

    platform_tools: list = []
    gitea_tools: list = []

    async def _exec(p_tools, g_tools):
        import traceback as _tb
        from orchestrator import runlog
        log_path = runlog.start(task_id or "task")
        if log_path:
            console.print(f"[dim]Лог прогона: {log_path}[/]")
        try:
            await _execute_graph(p_tools, g_tools, task_id, task_text, dry_run, review, auto, include_new)
        except BaseException as exc:  # noqa: BLE001 — нужно поймать всё для чистого вывода
            runlog.block("ERROR", _tb.format_exc())
            explained = _explain_llm_error(exc)
            if explained is None:
                raise
            # Live-дисплей уже свёрнут (async with __aexit__), терминал чист
            console.print(Panel(explained, title="[bold red]  LLM НЕДОСТУПЕН  [/bold red]",
                                border_style="red", expand=False))
            return
        finally:
            runlog.stop()

    if servers:
        # MCP-туннель brojs регулярно отдаёт 504 — без него journal_publisher
        # не работает, поэтому ждём подключения до 5 минут с retry каждые 5с.
        MCP_TOTAL_TIMEOUT = 300   # 5 минут суммарно
        MCP_RETRY_INTERVAL = 5    # каждые 5с
        MCP_ATTEMPT_TIMEOUT = 25  # один get_tools — не более 25с

        console.print(
            f"[dim]Подключаемся к MCP: {list(servers.keys())}... "
            f"(до {MCP_TOTAL_TIMEOUT}с, retry каждые {MCP_RETRY_INTERVAL}с)[/]"
        )
        all_tools: list = []
        deadline = asyncio.get_event_loop().time() + MCP_TOTAL_TIMEOUT
        attempt = 0
        last_err: str = ""
        while True:
            attempt += 1
            client = MultiServerMCPClient(servers)
            try:
                all_tools = await asyncio.wait_for(
                    client.get_tools(), timeout=MCP_ATTEMPT_TIMEOUT
                )
                break  # успех
            except asyncio.TimeoutError:
                last_err = f"таймаут {MCP_ATTEMPT_TIMEOUT}с"
            except Exception as e:  # noqa: BLE001
                last_err = f"{type(e).__name__}: {str(e)[:120]}"

            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                console.print(
                    f"[red]MCP недоступен после {attempt} попыток "
                    f"({MCP_TOTAL_TIMEOUT}с): {last_err}.[/]"
                )
                console.print(
                    "[red]Без MCP прогон бессмысленен (journal_publisher не сработает). "
                    "Прерываемся.[/]"
                )
                return
            console.print(
                f"[yellow]Попытка {attempt} провалилась ({last_err}). "
                f"Жду {MCP_RETRY_INTERVAL}с (осталось ~{int(remaining)}с)...[/]"
            )
            await asyncio.sleep(MCP_RETRY_INTERVAL)

        for t in all_tools:
            server_name = (getattr(t, "metadata", None) or {}).get("server", "") or ""
            if "gitea" in server_name.lower() or "gitea" in t.name.lower():
                gitea_tools.append(t)
            else:
                platform_tools.append(t)

        if not gitea_tools and all_tools:
            gitea_tools = all_tools  # fallback

        console.print(
            f"[green]OK[/] Инструментов: {len(all_tools)} "
            f"(platform: {len(platform_tools)}, gitea: {len(gitea_tools)})"
        )
        await _exec(platform_tools, gitea_tools)
    else:
        console.print("[yellow]MCP не настроен - работаем локально[/]")
        await _exec([], [])





async def _execute_graph(
    platform_tools: list,
    gitea_tools: list,
    task_id: str,
    task_text: str,
    dry_run: bool,
    review: bool = False,
    auto: bool = False,
    include_new: bool = False,
) -> None:
    from orchestrator.graph import build_graph
    from orchestrator.common import OrchestratorState
    from langchain_core.messages import HumanMessage
    from orchestrator.visualizer import AgentVisualizer
    from orchestrator import visualizer as viz_mod
    from orchestrator import runlog

    graph = build_graph(platform_tools, gitea_tools)

    base_initial: OrchestratorState = {
        "messages": [HumanMessage(content=f"Реши задачу {task_id}".strip())],
        "task_description": task_text or "",
        "task_id": task_id or "",
        "prepared": False,
        "generated_code": "",
        "test_results": "",
        "submission_result": "",
        "next_agent": "",
        "dry_run": dry_run,
        "retry_count": 0,
        "include_new": include_new,
    }

    event_queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    viz_mod.set_event_queue(event_queue)

    MAX_RETRIES = 10

    async with AgentVisualizer(task_id=task_id or "task", queue=event_queue) as viz:
        current_state = dict(base_initial)
        viz.node_start("supervisor")

        while True:
            should_retry = False

            async for step in graph.astream(current_state):
                node_name = list(step.keys())[0] if step else "?"
                node_data  = step.get(node_name, {})

                if node_name == "supervisor":
                    viz.node_done("supervisor")
                    next_node = node_data.get("next_agent", "")
                    if next_node and next_node not in ("FINISH", "__end__", ""):
                        runlog.log("supervisor", f"-> {next_node}", "route")
                        viz.node_start(next_node)
                    else:
                        runlog.log("supervisor", "FINISH", "route")
                        for n in ("task_fetcher", "coder", "tester", "submitter", "journal_publisher"):
                            viz.node_skip(n)

                elif node_name == "coder":
                    code = node_data.get("generated_code", "")
                    viz.set_code(code)
                    viz.node_done("coder")
                    runlog.block("GENERATED CODE", code)
                    current_state = {**current_state, **node_data}
                    viz.node_start("supervisor")

                elif node_name == "tester":
                    test_results = node_data.get("test_results", "")
                    viz.set_test_results(test_results)
                    viz.node_done("tester")
                    runlog.block("TEST RESULTS", test_results)
                    current_state = {**current_state, **node_data}

                    # Пауза — показываем результаты и спрашиваем пользователя
                    viz.pause_display()
                    retry_count = current_state.get("retry_count", 0)

                    console.print("\n[bold bright_magenta]━━━ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО ━━━[/]")
                    # Краткий вердикт
                    for line in test_results.splitlines():
                        if "ВЕРДИКТ:" in line or "ПРОЦЕНТ:" in line:
                            console.print(f"  {line}")

                    console.print()
                    if auto:
                        # Авто-режим: dry-run → завершаем, иначе → сдаём
                        choice = "s"
                        console.print("  [dim]AUTO режим — продолжаем без подтверждения[/dim]")
                    elif retry_count < MAX_RETRIES:
                        console.print(
                            f"  [bold](r)[/bold] Регенерировать код (retry {retry_count + 1}/{MAX_RETRIES})\n"
                            f"  [bold](s)[/bold] Сдать как есть\n"
                            f"  [bold](q)[/bold] Выйти"
                        )
                        try:
                            choice = input("  Выбор [r/s/q]: ").strip().lower()
                        except (KeyboardInterrupt, EOFError):
                            choice = "q"
                    else:
                        console.print(f"  [dim]Исчерпаны все попытки ({MAX_RETRIES}). Сдаём как есть.[/dim]")
                        console.print("  [bold](s)[/bold] Сдать / [bold](q)[/bold] Выйти")
                        try:
                            choice = input("  Выбор [s/q]: ").strip().lower()
                        except (KeyboardInterrupt, EOFError):
                            choice = "q"

                    runlog.log("user", f"выбор: {choice or '?'}", "input")
                    if choice == "q":
                        console.print("[yellow]Отменено.[/]")
                        return

                    if choice == "r" and retry_count < MAX_RETRIES:
                        should_retry = True
                        # Вытаскиваем секции ОЦЕНКА:/ПРОБЛЕМЫ:/ВЕРДИКТ:/ПРОЦЕНТ:
                        # из отчёта тестера, чтобы coder увидел их в следующей итерации.
                        feedback = _extract_score_feedback(test_results)
                        current_state = {
                            **current_state,
                            "generated_code": "",
                            "test_results": "",
                            "retry_count": retry_count + 1,
                            "previous_score_feedback": feedback,
                        }
                        runlog.log("retry", f"feedback {len(feedback)} симв", "input")
                        viz.resume_display()
                        viz.reset_for_retry()
                        viz.node_start("supervisor")
                        break  # выходим из astream, перезапускаем граф

                    # submit — продолжаем
                    if review and not dry_run:
                        console.print("\n[dim]Нажмите Enter для продолжения к сдаче...[/dim]")
                        try:
                            input()
                        except KeyboardInterrupt:
                            console.print("[yellow]Отменено.[/]")
                            return

                    viz.resume_display()
                    viz.node_start("supervisor")

                elif node_name == "submitter":
                    sub_res = node_data.get("submission_result", "")
                    viz.set_result(sub_res)
                    viz.node_done("submitter")
                    runlog.log("submitter", sub_res or "(пусто)", "result")
                    current_state = {**current_state, **node_data}
                    viz.node_start("supervisor")

                elif node_name == "journal_publisher":
                    js = node_data.get("journal_status", "")
                    viz.set_journal_status(js)
                    viz.node_done("journal_publisher")
                    runlog.log("journal_publisher", js or "(пусто)", "result")
                    current_state = {**current_state, **node_data}
                    viz.node_start("supervisor")

                else:
                    viz.node_done(node_name)
                    current_state = {**current_state, **node_data}
                    viz.node_start("supervisor")

            if not should_retry:
                break

    viz_mod.clear_event_queue()

    if dry_run:
        console.print("\n[yellow]DRY RUN: код не отправлялся[/]")
    console.print(Panel("[bold green]Готово![/]", expand=False))


@app.command()
def run(
    task_id: Optional[str] = typer.Option(None, "--task-id", "-i", help="ID задачи на платформе"),
    task_text: Optional[str] = typer.Option(None, "--task-text", "-t", help="Текст задачи напрямую"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Генерировать код но не сдавать"),
    review: bool = typer.Option(False, "--review", "-r", help="Пауза после генерации для просмотра кода"),
    auto: bool = typer.Option(False, "--auto", "-a", help="Без интерактива: авто-сдача после теста"),
    include_new: bool = typer.Option(False, "--include-new", help="Включить новые todo (по умолчанию только rework — возвращённые на доработку)"),
) -> None:
    """Запустить полный цикл: fetch -> code -> submit.

    По умолчанию выбирает только задания, возвращённые преподавателем на доработку
    (status=todo + reworkComment != ''). Для новых непройденных задач — --include-new.
    """
    asyncio.run(_run_async(task_id or "", task_text or "", dry_run, review, auto, include_new))


@app.command()
def tools() -> None:
    """Показать все MCP-инструменты (gitea + platform)."""
    async def _show():
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from orchestrator.config import cfg
        from orchestrator.mcp_client import build_gitea_server_config, build_platform_server_config

        servers: dict = {}
        try:
            servers["gitea"] = build_gitea_server_config()
        except ValueError as e:
            console.print(f"[yellow]Gitea: {e}[/]")

        if cfg.platform_mcp_url:
            servers["platform"] = build_platform_server_config()

        if not servers:
            console.print("[red]Нет доступных MCP серверов[/]")
            return

        client = MultiServerMCPClient(servers)
        all_tools = await client.get_tools()
        console.print(f"\n[bold]Инструменты ({len(all_tools)}):[/]\n")
        for t in all_tools:
            desc = (getattr(t, "description", "") or "")[:80]
            console.print(f"  [cyan]{t.name}[/] - {desc}")

    asyncio.run(_show())


@app.command(name="list")
def list_tasks() -> None:
    """Получить список заданий с платформы."""
    async def _list():
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from orchestrator.config import cfg
        from orchestrator.mcp_client import build_platform_server_config
        from orchestrator.common import make_llm
        from langchain_core.messages import HumanMessage
        from langgraph.prebuilt import create_react_agent

        if not cfg.platform_mcp_url:
            console.print("[red]PLATFORM_MCP_URL не задан в .env[/]")
            return

        client = MultiServerMCPClient({"platform": build_platform_server_config()})
        t = await client.get_tools()
        agent = create_react_agent(make_llm(), t)
        result = agent.invoke({
            "messages": [HumanMessage(content="Получи список всех доступных заданий с кратким описанием")]
        })
        console.print(result["messages"][-1].content)

    asyncio.run(_list())


if __name__ == "__main__":
    app()
