"""
journal_publisher: связывает коммит в Gitea со сдачей в журнале brojs и
отправляет на проверку.

Без LLM — детерминированные вызовы Journal MCP по результатам submitter'а:
  1. task_update_answer(taskId, answerType='link', content=<gitea url>, commit={...})
  2. task_submit(taskId, confirmSubmit=True)
  3. task_submission_status(taskId)

Если taskId не выглядит как ID платформы (24-символьный hex ObjectId) — нода
пропускается (это локальный run без привязки к журналу).
"""
from __future__ import annotations

import json
import re

from orchestrator.common import OrchestratorState
from orchestrator import visualizer as viz


# MongoDB ObjectId — 24 hex chars
_OBJECT_ID_RE = re.compile(r"^[a-f0-9]{24}$", re.IGNORECASE)


def _looks_like_platform_id(task_id: str) -> bool:
    return bool(_OBJECT_ID_RE.match(task_id or ""))


def _extract_text(raw) -> str:
    """MCP tools отдают list[{type:'text', text:'...'}] либо строку."""
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "text" in raw[0]:
        return raw[0]["text"]
    if isinstance(raw, str):
        return raw
    return str(raw) if raw else ""


def _build_comment(state: OrchestratorState) -> str:
    """
    Краткое транспарент-сообщение для task_comment: что было сделано,
    куда смотреть код. Для rework — упоминаем что устраняли.
    """
    sha = (state.get("commit_sha") or "")[:8]
    sol_url = state.get("solution_url") or state.get("repo_url") or ""
    parts = ["🥒 Решение сгенерировано CucumbersSWAGents (auto)."]
    if sha:
        parts.append(f"Коммит: `{sha}`")
    if sol_url:
        parts.append(f"Файл: {sol_url}")

    # Если в task_description был блок rework-комментария — отметим
    desc = state.get("task_description") or ""
    if "КОММЕНТАРИЙ ПРЕПОДАВАТЕЛЯ" in desc:
        # вытащим первые ~150 симв самого замечания для контекста
        marker = "═══ КОММЕНТАРИЙ ПРЕПОДАВАТЕЛЯ ПО ВОЗВРАЩЁННОЙ СДАЧЕ ═══"
        if marker in desc:
            after = desc.split(marker, 1)[1]
            # пропускаем 2 строки шаблонного текста
            lines = [l for l in after.splitlines() if l.strip()]
            comment_preview = " ".join(lines[1:3])[:150] if len(lines) > 1 else ""
            if comment_preview:
                parts.append(f"Исправление по комментарию преподавателя: «{comment_preview}…»")

    return " ".join(parts)


def make_journal_publisher_node(platform_tools: list):
    by_name = {t.name: t for t in (platform_tools or [])}
    update_tool = by_name.get("task_update_answer")
    submit_tool = by_name.get("task_submit")
    status_tool = by_name.get("task_submission_status")
    comment_tool = by_name.get("task_comment")

    async def node(state: OrchestratorState) -> dict:
        task_id = state.get("task_id", "")
        sub_res = state.get("submission_result", "")

        # Пропускаем если: submitter упал, или нет MCP журнала, или taskId не платформенный
        if not sub_res.startswith("OK"):
            viz.notify("journal_publisher", "Submitter не сдал — пропуск", "sub_step")
            return {"journal_status": "skipped: submitter failed"}
        if not update_tool or not submit_tool:
            viz.notify("journal_publisher", "Journal MCP недоступен — пропуск", "sub_step")
            return {"journal_status": "skipped: no MCP"}
        if not _looks_like_platform_id(task_id):
            viz.notify("journal_publisher", f"taskId не из журнала ({task_id[:12]}) — пропуск", "sub_step")
            return {"journal_status": "skipped: local task_id"}

        repo_url = state.get("repo_url", "")
        branch = state.get("branch", "main")
        commit_sha = state.get("commit_sha", "")
        solution_url = state.get("solution_url", "")
        file_path = state.get("file_path", "")
        commit_message = state.get("commit_message", "")

        commit_payload = {
            "repoUrl": repo_url[:500],
            "branch": branch[:200],
            "commitSha": commit_sha[:80],
            "message": commit_message[:1000],
            "files": [{"path": file_path, "url": solution_url}] if file_path else [],
        }

        # 1. update_answer — связываем коммит со сдачей
        viz.notify("journal_publisher", "task_update_answer...", "sub_step")
        try:
            await update_tool.ainvoke({
                "taskId": task_id,
                "answerType": "link",
                "content": solution_url or repo_url,
                "commit": commit_payload,
            })
        except Exception as e:
            err = f"update_answer fail: {type(e).__name__}: {str(e)[:120]}"
            viz.notify("journal_publisher", err, "sub_step")
            return {"journal_status": err}

        # 1.5. comment — транспарентность: что сделано, ссылка на коммит, что
        # исправляли (для rework). Не критично если упадёт — не блокируем submit.
        if comment_tool:
            try:
                comment_text = _build_comment(state)
                viz.notify("journal_publisher", "task_comment (контекст)...", "sub_step")
                await comment_tool.ainvoke({"taskId": task_id, "message": comment_text})
            except Exception as e:
                viz.notify("journal_publisher", f"comment skip: {type(e).__name__}", "sub_step")

        # 2. submit — отправляем на проверку
        viz.notify("journal_publisher", "task_submit (на проверку)...", "sub_step")
        try:
            await submit_tool.ainvoke({"taskId": task_id, "confirmSubmit": True})
        except Exception as e:
            err = f"submit fail: {type(e).__name__}: {str(e)[:120]}"
            viz.notify("journal_publisher", err, "sub_step")
            return {"journal_status": err}

        # 3. status — узнаём что вернул журнал
        status_text = "submitted"
        if status_tool:
            viz.notify("journal_publisher", "task_submission_status...", "sub_step")
            try:
                raw = await status_tool.ainvoke({"taskId": task_id})
                txt = _extract_text(raw)
                try:
                    data = json.loads(txt) if txt else {}
                    s = data.get("status") or data.get("state") or "submitted"
                    grade = data.get("grade", {})
                    if isinstance(grade, dict) and grade.get("value") is not None:
                        s = f"{s} (оценка: {grade['value']})"
                    status_text = s
                except json.JSONDecodeError:
                    status_text = txt[:200] or "submitted"
            except Exception as e:
                status_text = f"submitted (status err: {type(e).__name__})"

        viz.notify("journal_publisher", f"✓ {status_text}", "sub_step")
        return {"journal_status": status_text}

    return node
