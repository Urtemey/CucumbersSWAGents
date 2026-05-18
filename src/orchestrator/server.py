"""
FastAPI SSE-сервер оркестратора.

  uvicorn orchestrator.server:app --port 8765 --reload

Эндпоинты:
  GET  /                    → index.html
  POST /api/run             → запустить задачу, вернуть run_id
  GET  /api/stream/{run_id} → SSE-поток событий
  GET  /api/result/{run_id} → финальный результат (код + ссылка)
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

# ─── Модели ────────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    task_id: str = "task-001"
    task_text: str
    dry_run: bool = False


@dataclass
class RunState:
    run_id:  str
    queue:   asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=512))
    done:    bool = False
    code:    str = ""
    result:  str = ""


# ─── Хранилище запусков ────────────────────────────────────────────────────────

_runs: dict[str, RunState] = {}

# ─── Приложение ────────────────────────────────────────────────────────────────

app = FastAPI(title="CucumbersSWAGents", docs_url=None, redoc_url=None)

WEB_DIR = Path(__file__).parent.parent / "web"


@app.get("/", response_class=HTMLResponse)
async def root():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.post("/api/run")
async def start_run(req: RunRequest):
    run_id = uuid.uuid4().hex[:8]
    state  = RunState(run_id=run_id)
    _runs[run_id] = state
    asyncio.create_task(_run_orchestrator(state, req))
    return {"run_id": run_id}


@app.get("/api/stream/{run_id}")
async def stream(run_id: str):
    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="run not found")
    return StreamingResponse(
        _sse_generator(state),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/result/{run_id}")
async def get_result(run_id: str):
    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="run not found")
    return {"code": state.code, "result": state.result, "done": state.done}


# ─── SSE-генератор ─────────────────────────────────────────────────────────────

async def _sse_generator(state: RunState) -> AsyncIterator[str]:
    while True:
        try:
            event = await asyncio.wait_for(state.queue.get(), timeout=15)
        except asyncio.TimeoutError:
            yield "data: {\"type\":\"ping\"}\n\n"
            continue

        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        if event.get("type") == "done":
            break


# ─── Оркестратор ───────────────────────────────────────────────────────────────

async def _emit(state: RunState, event: dict) -> None:
    try:
        state.queue.put_nowait(event)
    except asyncio.QueueFull:
        pass


async def _run_orchestrator(state: RunState, req: RunRequest) -> None:
    from langchain_core.messages import HumanMessage
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from orchestrator.config import cfg
    from orchestrator.graph import build_graph
    from orchestrator.mcp_client import build_gitea_server_config
    from orchestrator import visualizer as viz_mod

    # Notify-события от агентов → SSE
    notify_q: asyncio.Queue = asyncio.Queue(maxsize=256)
    viz_mod.set_event_queue(notify_q)

    async def _drain_notify() -> None:
        while not state.done:
            try:
                ev = await asyncio.wait_for(notify_q.get(), timeout=0.3)
                await _emit(state, ev)
            except asyncio.TimeoutError:
                pass

    drain_task = asyncio.create_task(_drain_notify())

    try:
        # MCP
        servers: dict = {}
        try:
            servers["gitea"] = build_gitea_server_config()
        except ValueError:
            pass

        gitea_tools: list = []
        if servers:
            client = MultiServerMCPClient(servers)
            all_tools = await client.get_tools()
            gitea_tools = [
                t for t in all_tools
                if "gitea" in (getattr(t, "metadata", None) or {}).get("server", "").lower()
                   or "gitea" in t.name.lower()
            ] or all_tools

        graph = build_graph([], gitea_tools)

        initial = {
            "messages": [HumanMessage(content=f"Реши задачу {req.task_id}")],
            "task_description": req.task_text,
            "task_id":          req.task_id,
            "generated_code":   "",
            "submission_result": "",
            "next_agent":       "",
            "dry_run":          req.dry_run,
        }

        await _emit(state, {"type": "node_start", "node": "supervisor"})

        async for step in graph.astream(initial):
            node_name = list(step.keys())[0] if step else "?"
            node_data  = step.get(node_name, {})

            if node_name == "supervisor":
                await _emit(state, {"type": "node_done", "node": "supervisor"})
                nxt = node_data.get("next_agent", "")
                if nxt and nxt not in ("FINISH", "__end__", ""):
                    await _emit(state, {"type": "node_start", "node": nxt})
                else:
                    await _emit(state, {"type": "node_skip", "nodes": ["task_fetcher", "coder", "submitter"]})

            elif node_name == "coder":
                code = node_data.get("generated_code", "")
                if code:
                    state.code = code
                    await _emit(state, {"type": "code", "data": code})
                await _emit(state, {"type": "node_done", "node": "coder"})
                await _emit(state, {"type": "node_start", "node": "supervisor"})

            elif node_name == "submitter":
                result = node_data.get("submission_result", "")
                if result:
                    state.result = result
                    await _emit(state, {"type": "result", "data": result})
                await _emit(state, {"type": "node_done", "node": "submitter"})
                await _emit(state, {"type": "node_start", "node": "supervisor"})

            else:
                await _emit(state, {"type": "node_done", "node": node_name})
                await _emit(state, {"type": "node_start", "node": "supervisor"})

    except Exception as exc:
        await _emit(state, {"type": "error", "message": str(exc)})

    finally:
        state.done = True
        drain_task.cancel()
        viz_mod.clear_event_queue()
        await _emit(state, {"type": "done"})
