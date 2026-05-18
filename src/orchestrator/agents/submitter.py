"""
submitter: публикует решение в Gitea напрямую через REST API.

Без LLM — детерминированная логика:
1. Проверить/создать репозиторий
2. Создать/обновить файл с кодом (base64)
3. Вернуть URL файла
"""
from __future__ import annotations

import base64
from pathlib import Path

import httpx

from orchestrator.config import cfg
from orchestrator.common import OrchestratorState
from orchestrator import visualizer as viz


def _detect_extension(code: str) -> str:
    if "```python" in code or "def " in code or "import " in code:
        return "py"
    if "```javascript" in code or "```js" in code or "function " in code:
        return "js"
    if "```typescript" in code or "```ts" in code:
        return "ts"
    if "```java" in code or "public class" in code:
        return "java"
    if "```go" in code or "func main()" in code:
        return "go"
    return "txt"


def _strip_markdown_fences(code: str) -> str:
    """Убираем ```python ... ``` если модель обернула код в блок."""
    lines = code.splitlines()
    result = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        result.append(line)
    return "\n".join(result).strip()


def make_submitter_node(gitea_tools: list):

    async def node(state: OrchestratorState) -> dict:
        task_id = state.get("task_id") or "unknown"
        code = state.get("generated_code", "")
        ext = _detect_extension(code)
        clean_code = _strip_markdown_fences(code)
        file_path = f"solutions/{task_id}/solution.{ext}"

        if not cfg.gitea_token or not cfg.gitea_owner:
            viz.notify("submitter", "Сохраняю локально...", "sub_step")
            return _save_local(task_id, clean_code, ext)

        base = cfg.gitea_url.rstrip("/")
        owner = cfg.gitea_owner
        repo = cfg.solutions_repo
        headers = {
            "Authorization": f"token {cfg.gitea_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            # 1. Проверяем/создаём репозиторий
            viz.notify("submitter", "Проверяю репозиторий...", "sub_step")
            r = await client.get(f"{base}/api/v1/repos/{owner}/{repo}", headers=headers)
            if r.status_code == 404:
                viz.notify("submitter", "Создаю репозиторий...", "sub_step")
                await client.post(
                    f"{base}/api/v1/user/repos",
                    headers=headers,
                    json={"name": repo, "private": False, "auto_init": True},
                )

            # 2. Проверяем существует ли файл (нужен SHA для обновления)
            viz.notify("submitter", "Проверяю файл...", "sub_step")
            r_file = await client.get(
                f"{base}/api/v1/repos/{owner}/{repo}/contents/{file_path}",
                headers=headers,
            )
            sha = r_file.json().get("sha") if r_file.status_code == 200 else None

            # 3. Создаём или обновляем файл
            viz.notify("submitter", "Пушу решение...", "sub_step")
            content_b64 = base64.b64encode(clean_code.encode("utf-8")).decode()
            payload = {
                "message": f"feat: solution for {task_id}",
                "content": content_b64,
            }
            if sha:
                payload["sha"] = sha

            r_put = await client.put(
                f"{base}/api/v1/repos/{owner}/{repo}/contents/{file_path}",
                headers=headers,
                json=payload,
            )

            if r_put.status_code in (200, 201):
                html_url = r_put.json().get("content", {}).get("html_url", "")
                result = f"OK: {html_url or f'{base}/{owner}/{repo}/src/branch/main/{file_path}'}"
            else:
                result = f"Gitea ошибка {r_put.status_code}: {r_put.text[:200]}"

        viz.notify("submitter", "Готово", "node_done")
        return {"submission_result": result}

    return node


def _save_local(task_id: str, code: str, ext: str) -> dict:
    out_dir = Path("solutions") / task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"solution.{ext}"
    out_file.write_text(code, encoding="utf-8")
    return {"submission_result": f"[LOCAL] {out_file}"}
