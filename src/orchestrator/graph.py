"""
LangGraph-граф оркестратора.

Паттерн: supervisor маршрутизирует задачи между суб-агентами.
  supervisor → task_fetcher  (получить задание с платформы)
             → coder          (написать решение)
             → submitter      (сдать через gitea-mcp)
             → FINISH
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from orchestrator.common import OrchestratorState


def supervisor_node(state: OrchestratorState) -> dict:
    """
    Supervisor детерминированно маршрутизирует по этапам пайплайна.
    Порядок: task_fetcher → coder → tester → submitter → FINISH
    dry_run=True: останавливается после tester (тест выполняется, сдача нет).
    """
    prepared = bool(state.get("prepared", False))
    has_code = bool(state.get("generated_code", "").strip())
    has_tests = bool(state.get("test_results", "").strip())
    has_result = bool(state.get("submission_result", "").strip())
    dry_run = state.get("dry_run", False)

    # task_fetcher всегда прогоняется первым (один раз): фетч задания при
    # необходимости + обогащение документацией из ссылок. Скип невозможен,
    # иначе доки из ссылок задания никогда не подгрузятся (задание из файла).
    if not prepared:
        next_node = "task_fetcher"
    elif not has_code:
        next_node = "coder"
    elif not has_tests:
        next_node = "tester"
    elif dry_run:
        next_node = "FINISH"
    elif not has_result:
        next_node = "submitter"
    else:
        next_node = "FINISH"

    return {"next_agent": next_node}


def route_supervisor(state: OrchestratorState) -> Literal["task_fetcher", "coder", "tester", "submitter", "__end__"]:
    nxt = state.get("next_agent", "FINISH")
    if nxt == "FINISH":
        return END
    return nxt  # type: ignore[return-value]


def build_graph(platform_tools: list, gitea_tools: list):
    # Деferred импорт — разрываем цикл
    from orchestrator.agents.task_fetcher import make_task_fetcher_node
    from orchestrator.agents.coder import make_coder_node
    from orchestrator.agents.tester import make_tester_node
    from orchestrator.agents.submitter import make_submitter_node

    graph = StateGraph(OrchestratorState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("task_fetcher", make_task_fetcher_node(platform_tools))
    graph.add_node("coder", make_coder_node())
    graph.add_node("tester", make_tester_node())
    graph.add_node("submitter", make_submitter_node(gitea_tools))

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", route_supervisor)
    graph.add_edge("task_fetcher", "supervisor")
    graph.add_edge("coder", "supervisor")
    graph.add_edge("tester", "supervisor")
    graph.add_edge("submitter", "supervisor")

    return graph.compile()
