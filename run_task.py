"""Запускает оркестратор с заданием из файла."""
import asyncio
import sys
from pathlib import Path

TASK_FILE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("taskinfo/task1info.txt")
TASK_ID   = sys.argv[2] if len(sys.argv) > 2 else "task-001"
DRY_RUN     = "--dry-run" in sys.argv
REVIEW      = "--review" in sys.argv
AUTO        = "--auto" in sys.argv or "-a" in sys.argv
INCLUDE_NEW = "--include-new" in sys.argv

task_text = TASK_FILE.read_text(encoding="utf-8")

from orchestrator.main import _run_async
asyncio.run(_run_async(TASK_ID, task_text, DRY_RUN, REVIEW, AUTO, INCLUDE_NEW))
