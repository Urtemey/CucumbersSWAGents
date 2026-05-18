"""
Файловый лог прогона — развязан от Live-рендера.

Live-дисплей эфемерный (перерисовки затирают друг друга), поэтому пишем
плоский append-лог в logs/run_<task>_<ts>.log. Переживает краши: каждая
строка флашится сразу, файл закрывается даже при исключении.
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Optional

_fp: Optional[io.TextIOWrapper] = None
_path: Optional[Path] = None


def start(task_id: str) -> Optional[Path]:
    """Открывает новый лог-файл прогона. Возвращает путь (или None при ошибке)."""
    global _fp, _path
    stop()  # закрыть предыдущий, если был
    try:
        root = Path(__file__).resolve().parents[2]   # <root>/src/orchestrator/runlog.py
        logs_dir = root / "logs"
        logs_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in (task_id or "task"))
        _path = logs_dir / f"run_{safe_id}_{ts}.log"
        _fp = open(_path, "w", encoding="utf-8", buffering=1)  # line-buffered
        _raw(f"=== RUN {task_id} @ {datetime.now():%Y-%m-%d %H:%M:%S} ===")
        return _path
    except OSError:
        _fp = None
        _path = None
        return None


def stop() -> None:
    global _fp, _path
    if _fp is not None:
        try:
            _raw(f"=== END @ {datetime.now():%Y-%m-%d %H:%M:%S} ===")
            _fp.flush()
            _fp.close()
        except (OSError, ValueError):
            pass
    _fp = None
    _path = None


def path() -> Optional[Path]:
    return _path


def _raw(line: str) -> None:
    if _fp is None:
        return
    try:
        _fp.write(line + "\n")
        _fp.flush()
    except (OSError, ValueError):
        pass


def log(node: str, message: str, etype: str = "info") -> None:
    """Одна событийная строка: время · тип · нода · сообщение."""
    ts = datetime.now().strftime("%H:%M:%S")
    one_line = " ".join(str(message).split())
    _raw(f"{ts}  [{etype:<10}] {node:<13} {one_line}")


def block(title: str, content: str) -> None:
    """Многострочный блок (код, результаты тестов, traceback)."""
    if _fp is None or not content:
        return
    _raw(f"\n----- {title} -----")
    _raw(content.rstrip())
    _raw(f"----- /{title} -----\n")
