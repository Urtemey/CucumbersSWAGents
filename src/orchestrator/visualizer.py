"""
CLI-визуализатор оркестратора — Rich Live + ASCII арт.
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime
from typing import Optional

from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
# Columns импортируется только если вдруг понадобится в будущем

# ── Константы ────────────────────────────────────────────────────────────────

ALL_NODES = ["supervisor", "task_fetcher", "coder", "tester", "submitter"]

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
FLOW     = ["·", "·", "▸", "·", "·", "▸", "·"]     # анимация потока данных

NODE_LABEL = {
    "supervisor":   "SUPERVISOR",
    "task_fetcher": "TASK FETCH",
    "coder":        "CODER     ",
    "tester":       "TESTER    ",
    "submitter":    "SUBMITTER ",
}
NODE_COLOR = {
    "supervisor":   "bright_cyan",
    "task_fetcher": "magenta",
    "coder":        "yellow",
    "tester":       "bright_magenta",
    "submitter":    "bright_blue",
}

BANNER = """\
  ╔══════════════════════════════════════════════════╗
  ║  ██████╗██╗   ██╗ ██████╗██╗   ██╗███╗   ███╗  ║
  ║ ██╔════╝██║   ██║██╔════╝██║   ██║████╗ ████║  ║
  ║ ██║     ██║   ██║██║     ██║   ██║██╔████╔██║  ║
  ║ ╚██████╗╚██████╔╝╚██████╗╚██████╔╝██║ ╚═╝ ██║  ║
  ║  ╚═════╝ ╚═════╝  ╚═════╝ ╚═════╝ ╚═╝     ╚═╝  ║
  ║        S  W  A  G  E  N  T  S                   ║
  ║        deep-agent orchestrator  v1.0            ║
  ╚══════════════════════════════════════════════════╝\
"""

# ── Notify-система ────────────────────────────────────────────────────────────

_queue: Optional[asyncio.Queue] = None

# Стриминг кода: глобальный буфер (asyncio single-threaded — race нет)
_streaming_code: str = ""
_streaming_label: str = ""   # "генерация" | "ревью" | ""


def set_event_queue(q: asyncio.Queue) -> None:
    global _queue
    _queue = q


def clear_event_queue() -> None:
    global _queue
    _queue = None


def update_streaming_code(text: str, label: str = "генерация") -> None:
    """Обновить буфер стримингового кода (вызывается из coder.py на каждом чанке)."""
    global _streaming_code, _streaming_label
    _streaming_code = text
    _streaming_label = label


def clear_streaming_code() -> None:
    global _streaming_code, _streaming_label
    _streaming_code = ""
    _streaming_label = ""


def notify(node: str, message: str, event_type: str = "sub_step") -> None:
    # В файл-лог пишем ВСЕГДА (даже если Live/очередь не подняты)
    from orchestrator import runlog
    runlog.log(node, message, event_type)

    if _queue is None:
        return
    try:
        _queue.put_nowait({
            "type": event_type,
            "node": node,
            "message": message,
            "ts": datetime.now().strftime("%H:%M:%S"),
        })
    except asyncio.QueueFull:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_code_block(text: str) -> str:
    """Вытащить первый ```python ... ``` блок, иначе вернуть текст как есть."""
    import re
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
    return "\n".join(lines).strip()


def _strip_partial_fence(text: str) -> str:
    """Убрать открывающий ``` для отображения незавершённого стрима."""
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    return "\n".join(lines)


# ── Визуализатор ─────────────────────────────────────────────────────────────

class AgentVisualizer:
    """
    Async context manager: Rich Live + фоновый аниматор 10fps.

    async with AgentVisualizer(task_id="t1", queue=q) as viz:
        viz.node_start("supervisor")
        async for step in graph.astream(initial):
            ...
    """

    def __init__(self, task_id: str = "", queue: Optional[asyncio.Queue] = None):
        self._task_id    = task_id
        self._queue      = queue
        self._states     = {n: "idle" for n in ALL_NODES}
        self._sub_msgs: dict[str, str] = {}
        self._log: deque = deque(maxlen=80)
        self._code       = ""
        self._result     = ""
        self._test_results = ""
        self._tick       = 0
        self._start_time = time.time()
        self._active_node= ""
        self._running    = False
        self._live: Optional[Live] = None
        self._task: Optional[asyncio.Task] = None
        # Консоль с принудительным терминальным режимом (для Windows)
        self._console    = Console(force_terminal=True, highlight=False)

    # ── Context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> "AgentVisualizer":
        self._running    = True
        self._start_time = time.time()
        # Печатаем баннер ДО Live (всегда видно)
        _banner_console = Console(highlight=False)
        _banner_console.print(Text(BANNER, style="bold cyan"))
        _banner_console.print()

        self._live = Live(
            self._make_layout(),
            console=self._console,
            refresh_per_second=10,
            screen=False,
            transient=False,
        )
        self._live.__enter__()
        self._task = asyncio.create_task(self._animate())
        return self

    async def __aexit__(self, *exc) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._live:
            self._live.update(self._make_layout())
            self._live.__exit__(*exc)

    # ── Public API ────────────────────────────────────────────────────────────

    def node_start(self, node: str) -> None:
        if node not in ALL_NODES:
            return
        self._states[node]  = "active"
        self._active_node   = node
        self._add_log(node, f"→ {NODE_LABEL.get(node, node).strip()} запущен", "node_start")

    def node_done(self, node: str) -> None:
        if node not in ALL_NODES:
            return
        self._states[node] = "done"
        self._sub_msgs.pop(node, None)
        if self._active_node == node:
            self._active_node = ""
        self._add_log(node, f"✓ {NODE_LABEL.get(node, node).strip()} завершён", "node_done")

    def node_error(self, node: str, error: str = "") -> None:
        if node not in ALL_NODES:
            return
        self._states[node] = "error"
        self._add_log(node, f"✗ {error or 'ошибка'}", "node_error")

    def node_skip(self, node: str) -> None:
        if self._states.get(node) == "idle":
            self._states[node] = "skipped"

    def set_code(self, code: str) -> None:
        if code:
            self._code = _extract_code_block(code)

    def set_test_results(self, text: str) -> None:
        if text:
            self._test_results = text

    def set_result(self, result: str) -> None:
        if result:
            self._result = result
            self._add_log("submitter", result[:80], "result")

    def reset_for_retry(self) -> None:
        """Сбросить состояние нод для повторной генерации."""
        self._states = {n: "idle" for n in ALL_NODES}
        self._sub_msgs.clear()
        self._code = ""
        self._test_results = ""
        self._active_node = ""
        self._add_log("supervisor", "↺ Повторная генерация...", "node_start")

    def pause_display(self) -> None:
        """Временно останавливает Live для интерактивного ввода."""
        if self._live:
            self._live.stop()

    def resume_display(self) -> None:
        """Возобновляет Live после паузы."""
        if self._live:
            self._live.start(refresh=True)

    # ── Внутреннее ───────────────────────────────────────────────────────────

    def _add_log(self, node: str, message: str, etype: str = "info") -> None:
        self._log.append({
            "ts":      datetime.now().strftime("%H:%M:%S"),
            "node":    node,
            "message": message,
            "type":    etype,
        })

    def _process_notify(self, event: dict) -> None:
        node    = event.get("node", "?")
        message = event.get("message", "")
        etype   = event.get("type", "sub_step")
        if node in ALL_NODES:
            self._sub_msgs[node] = message
        self._add_log(node, message, etype)

    async def _animate(self) -> None:
        while self._running:
            self._tick += 1
            if self._queue:
                for _ in range(32):
                    try:
                        self._process_notify(self._queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
            if self._live:
                try:
                    self._live.update(self._make_layout())
                except Exception:
                    pass
            await asyncio.sleep(0.1)

    # ── Рендер ───────────────────────────────────────────────────────────────

    def _spin(self) -> str:
        return SPINNERS[self._tick % len(SPINNERS)]

    def _flow(self) -> str:
        return FLOW[self._tick % len(FLOW)]

    def _node_lines(self, node: str) -> list[Text]:
        """
        Рендер ноды как 3–4 строки компактного box:
          ║ ┌──────────────┐
          ║ │ LABEL    icon│
          ║ │ sub-msg      │  (только если active)
          ║ └──────────────┘
        Всё влезает в ~18 символов — не вылезает за узкую панель.
        """
        W = 14   # ширина содержимого box (без │)
        state = self._states.get(node, "idle")
        color = NODE_COLOR.get(node, "white")
        label = NODE_LABEL.get(node, node.upper()).strip()[:10]
        sub   = self._sub_msgs.get(node, "")[:W-1]

        if state == "active":
            border_s = f"bold {color}"
            label_s  = f"bold {color}"
            icon, icon_s = self._spin(), "bold yellow"
        elif state == "done":
            border_s = label_s = "green"
            icon, icon_s = "✓", "bold green"
        elif state == "error":
            border_s = label_s = "red"
            icon, icon_s = "✗", "bold red"
        elif state == "skipped":
            border_s = label_s = icon_s = "dim"
            icon = "─"
        else:
            border_s = label_s = icon_s = "dim"
            icon = "○"

        top = Text(); top.append("  ║ ┌" + "─"*W + "┐", style=border_s)

        mid = Text()
        mid.append("  ║ │ ", style=border_s)
        mid.append(label.ljust(W - 3), style=label_s)
        mid.append(icon, style=icon_s)
        mid.append(" │", style=border_s)

        lines = [top, mid]

        if sub and state == "active":
            sm = Text()
            sm.append("  ║ │ ", style=border_s)
            sm.append(sub.ljust(W - 1), style="dim italic")
            sm.append("│", style=border_s)
            lines.append(sm)

        bot = Text(); bot.append("  ║ └" + "─"*W + "┘", style=border_s)
        lines.append(bot)
        return lines

    def _pipe(self, active: bool = False) -> Text:
        """Соединитель между нодами."""
        t = Text()
        if active:
            f = self._flow()
            t.append(f"  ║ ║              ║  {f}", style="yellow")
        else:
            t.append("  ║ ║              ║", style="dim")
        return t

    def _render_graph_panel(self) -> Panel:
        sv_state = self._states["supervisor"]
        sv_color = NODE_COLOR["supervisor"]
        sv_spin  = self._spin() if sv_state == "active" else ("✓" if sv_state == "done" else "○")
        sv_style = ("bold yellow" if sv_state == "active"
                    else "bold green" if sv_state == "done"
                    else "dim")
        sv_bs    = f"bold {sv_color}" if sv_state == "active" else ("green" if sv_state == "done" else "dim")

        lines: list = []

        # ── START ──
        t = Text(); t.append("  ║   START", style="dim"); lines.append(t)
        t = Text(); t.append("  ║     │",   style="dim"); lines.append(t)

        # ── SUPERVISOR ──
        lines.append(Text("  ║ ┌──────────────┐", style=sv_bs))
        sv_mid = Text()
        sv_mid.append("  ║ │ ", style=sv_bs)
        sv_mid.append("SUPERVISOR", style=f"bold {sv_color}" if sv_state != "idle" else "dim")
        sv_mid.append(f"  {sv_spin}", style=sv_style)
        sv_mid.append(" │", style=sv_bs)
        lines.append(sv_mid)
        lines.append(Text("  ║ └──────────────┘", style=sv_bs))

        # ── Sub-agents ──
        for node in ["task_fetcher", "coder", "tester", "submitter"]:
            active = self._states[node] == "active"
            # соединитель
            t = Text()
            t.append("  ║ │", style="dim")
            if active:
                t.append(f"  {self._flow()}", style="yellow")
            lines.append(t)
            # box ноды
            lines.extend(self._node_lines(node))

        # ── END ──
        t = Text(); t.append("  ║     │",   style="dim"); lines.append(t)
        t = Text(); t.append("  ║   END",   style="dim"); lines.append(t)

        return Panel(
            Group(*lines),
            title="[bold blue]PIPELINE[/bold blue]",
            border_style="blue",
        )

    def _render_log_panel(self) -> Panel:
        tbl = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        tbl.add_column("ts",   style="dim", width=8,  no_wrap=True)
        tbl.add_column("node", width=11, no_wrap=True)
        tbl.add_column("msg",  ratio=1)

        for entry in list(self._log)[-20:]:
            node  = entry["node"]
            etype = entry["type"]
            color = NODE_COLOR.get(node, "white")
            if etype == "node_done":       ms = "green"
            elif etype == "node_start":    ms = "yellow"
            elif etype in ("node_error",): ms = "bold red"
            elif etype == "result":        ms = "bold bright_green"
            elif etype == "sub_step":      ms = "dim"
            else:                          ms = "white"

            tbl.add_row(
                entry["ts"],
                f"[{color}]{node}[/{color}]",
                f"[{ms}]{entry['message'][:55]}[/{ms}]",
            )
        return Panel(tbl, title="[bold blue]  СОБЫТИЯ  [/bold blue]", border_style="blue")

    def _render_bottom_panel(self) -> Panel:
        if self._result:
            t = Text()
            t.append("  ✓ Сдано: ", style="bold bright_green")
            t.append(self._result, style="green")
            return Panel(t, title="[bold green]  РЕЗУЛЬТАТ  [/bold green]", border_style="green")

        # Результаты тестирования (после tester)
        if self._test_results:
            return self._render_test_panel()

        # "запуск" — live-стриминг stdout построчно пока скрипт работает
        if _streaming_label == "запуск" and _streaming_code:
            tail = _streaming_code[-3000:]
            spin = self._spin()
            return Panel(
                Text(tail, style="bright_white"),
                title=f"[bold green]  ВЫВОД СКРИПТА (live)  {spin}  [/bold green]",
                border_style="green",
            )

        # "вывод" — скрипт завершился, вывод зафиксирован, остаётся видимым
        if _streaming_label == "вывод" and _streaming_code:
            tail = _streaming_code[-3000:]
            return Panel(
                Text(tail, style="bright_white"),
                title="[bold green]  ВЫВОД СКРИПТА  [/bold green]",
                border_style="green",
            )

        # "оценка" — LLM анализирует, вывод скрипта заменяется текстом оценки
        if _streaming_label == "оценка" and _streaming_code:
            tail = _streaming_code[-3000:]
            spin = self._spin()
            return Panel(
                Text(tail, style="dim"),
                title=f"[bold bright_magenta]  ОЦЕНКА (анализ...)  {spin}  [/bold bright_magenta]",
                border_style="bright_magenta",
            )

        # Финальный код (после завершения coder)
        if self._code:
            tail = self._code[-3000:]
            return Panel(
                Syntax(tail, "python", theme="monokai", line_numbers=False),
                title="[bold yellow]  КОД (python)  [/bold yellow]",
                border_style="yellow",
            )

        # Стриминг в реальном времени (во время генерации/ревью)
        if _streaming_code:
            partial = _strip_partial_fence(_streaming_code)
            tail = partial[-3000:]
            spin = self._spin()
            label = _streaming_label or "генерация"
            return Panel(
                Syntax(tail, "python", theme="monokai", line_numbers=False),
                title=f"[bold yellow]  КОД ({label}...)  {spin}  [/bold yellow]",
                border_style="yellow",
            )

        spin = self._spin()
        return Panel(
            Align.center(Text(f"{spin}  ожидание генерации...", style="dim")),
            title="[dim]  КОД  [/dim]",
            border_style="dim",
        )

    def _render_test_panel(self) -> Panel:
        """Рендерим результаты тестирования: сначала вывод скрипта, потом оценка."""
        lines = self._test_results.splitlines()

        # Разбиваем на секции
        stdout_lines: list[str] = []
        score_lines: list[str] = []
        meta_lines: list[str] = []   # СИНТАКСИС, ПАТТЕРНЫ, ЗАПУСК, STDIN, STDERR
        verdict_line = ""
        percent_line = ""

        in_stdout = False
        in_stderr = False
        in_score = False

        for line in lines:
            ls = line.strip()
            if ls.startswith("[STDOUT]"):
                in_stdout = True
                in_stderr = False
                in_score = False
                rest = line[line.index("]") + 1:].strip()
                if rest:
                    stdout_lines.append(rest)
            elif ls.startswith("[STDERR]"):
                in_stdout = False
                in_stderr = True
                in_score = False
                rest = line[line.index("]") + 1:].strip()
                if rest:
                    meta_lines.append(f"[STDERR] {rest}")
            elif ls.startswith("[") and not in_score:
                in_stdout = False
                in_stderr = False
                meta_lines.append(line)
            elif ls.startswith("ОЦЕНКА:") or ("|" in ls and "Критерий" in ls):
                in_stdout = False
                in_stderr = False
                in_score = True
                score_lines.append(line)
            elif ls.startswith("ВЕРДИКТ:"):
                verdict_line = ls
                in_stdout = False
            elif ls.startswith("ПРОЦЕНТ:"):
                percent_line = ls
            elif in_stdout:
                stdout_lines.append(line)
            elif in_stderr:
                meta_lines.append(line)
            elif in_score:
                score_lines.append(line)

        from rich.console import Group as RGroup

        renderables = []

        # ── Мета-строки (синтаксис, паттерны, запуск, stdin) ──
        if meta_lines:
            meta_tbl = Table(show_header=False, box=None, padding=(0, 1), expand=True)
            meta_tbl.add_column("ico", width=2, no_wrap=True)
            meta_tbl.add_column("msg", ratio=1)
            for ml in meta_lines:
                ms = ml.strip()
                if ms.startswith("[СИНТАКСИС]"):
                    ok = "✓" in ms
                    meta_tbl.add_row("✓" if ok else "✗", Text(ms[12:], style="green" if ok else "red"))
                elif ms.startswith("[ПАТТЕРНЫ]"):
                    meta_tbl.add_row("◉", Text(ms[11:], style="cyan"))
                elif ms.startswith("[ЗАПУСК]"):
                    s = "green" if "✓" in ms else ("yellow" if "Таймаут" in ms or "60s" in ms else "red")
                    meta_tbl.add_row("▶", Text(ms[9:], style=s))
                elif ms.startswith("[DEPS]"):
                    s = "red" if "fail" in ms or "ошибка" in ms or "таймаут" in ms else "green"
                    meta_tbl.add_row("⬇", Text(ms[7:], style=s))
                elif ms.startswith("[STDIN]"):
                    meta_tbl.add_row("→", Text(ms[8:], style="dim cyan"))
                elif ms.startswith("[STDERR]"):
                    meta_tbl.add_row("!", Text(ms[9:], style="yellow"))
                else:
                    meta_tbl.add_row("", Text(ms, style="dim"))
            renderables.append(meta_tbl)

        # ── Вывод скрипта ──
        if stdout_lines:
            stdout_text = "\n".join(stdout_lines)
            renderables.append(
                Panel(
                    Text(stdout_text, style="bright_white"),
                    title="[bold green]  ВЫВОД СКРИПТА  [/bold green]",
                    border_style="green",
                    padding=(0, 1),
                )
            )

        # ── Оценка ──
        if score_lines:
            score_tbl = Table(show_header=False, box=None, padding=(0, 1), expand=True)
            score_tbl.add_column("row", ratio=1)
            for sl in score_lines:
                ss = sl.strip()
                if ss.startswith("|") and not all(c in "-|─ " for c in ss):
                    parts = [p.strip() for p in ss.strip("|").split("|")]
                    is_total = len(parts) > 0 and "ИТОГО" in parts[0].upper()
                    style = "bold bright_green" if is_total else ""
                    score_tbl.add_row(Text(ss, style=style))
                elif ss.startswith("ПРОБЛЕМЫ:"):
                    score_tbl.add_row(Text(ss, style="bold yellow"))
                elif ss.startswith("-"):
                    score_tbl.add_row(Text(ss, style="yellow"))
                elif ss:
                    score_tbl.add_row(Text(ss, style="dim"))
            renderables.append(score_tbl)

        # ── Вердикт ──
        if verdict_line or percent_line:
            vtext = Text()
            if verdict_line:
                vs = (
                    "bold bright_green" if "ОТЛИЧНО" in verdict_line
                    else "bold green" if "ХОРОШО" in verdict_line
                    else "bold yellow" if "ДОРАБОТКИ" in verdict_line
                    else "bold red"
                )
                vtext.append(verdict_line, style=vs)
            if percent_line:
                vtext.append(f"  {percent_line}", style="dim")
            renderables.append(vtext)

        return Panel(
            RGroup(*renderables),
            title="[bold bright_magenta]  РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ  [/bold bright_magenta]",
            border_style="bright_magenta",
        )

    def _make_layout(self) -> Layout:
        elapsed = int(time.time() - self._start_time)

        hdr = Text()
        hdr.append("  🥒 ", style="")
        hdr.append("CucumbersSWAGents", style="bold cyan")
        if self._task_id:
            hdr.append(f"  ·  {self._task_id}", style="dim")
        hdr.append(f"  ·  ⏱ {elapsed}s", style="dim")
        if self._active_node:
            hdr.append("  ·  ", style="dim")
            hdr.append(self._active_node, style="bold yellow")
            hdr.append(f" {self._spin()}", style="yellow")

        # body: фиксированный — ровно по высоте графа (5 нод = ~27 строк с рамками)
        # bottom: ratio=1 — забирает всё оставшееся место под код/результаты
        layout = Layout()
        layout.split_column(
            Layout(Panel(hdr, style="dim"), name="header", size=3),
            Layout(name="body", size=27),
            Layout(self._render_bottom_panel(), name="bottom", ratio=1),
        )
        layout["body"].split_row(
            Layout(self._render_graph_panel(), name="graph", ratio=5),
            Layout(self._render_log_panel(),   name="log",   ratio=7),
        )
        return layout
