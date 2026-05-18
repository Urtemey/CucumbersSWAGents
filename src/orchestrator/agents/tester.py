"""
tester: тестирует сгенерированный код перед сдачей.

Фазы:
  1. Синтаксис (py_compile)
  2. Статический анализ (AST — нужные паттерны)
  3. Subprocess-запуск (real LLM из .env, timeout=20s)
  4. LLM-оценка по критериям задания (стриминг в визуализатор)
"""
from __future__ import annotations

import ast
import os
import py_compile
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from orchestrator.common import OrchestratorState, make_llm
from orchestrator import visualizer as viz
from orchestrator.visualizer import update_streaming_code, clear_streaming_code
from orchestrator.code_utils import extract_code_block as _extract_code


# ── Фаза 1: синтаксис ─────────────────────────────────────────────────────────

def _check_syntax(code: str) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        py_compile.compile(path, doraise=True)
        return True, "OK"
    except py_compile.PyCompileError as e:
        return False, str(e)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ── Фаза 2: статический анализ ────────────────────────────────────────────────

_PATTERNS = {
    "langchain_import":   ["from langchain", "import langchain"],
    "langgraph_import":   ["from langgraph", "import langgraph"],
    "tool_decorator":     ["@tool"],
    "stategraph":         ["StateGraph"],
    "interrupt":          ["interrupt("],
    "checkpointer":       ["checkpointer", "InMemorySaver", "MemorySaver"],
    "create_react_agent": ["create_react_agent", "create_agent"],
    "stream_mode":        ["stream(", "astream(", ".stream("],
    "llm_init":           ["ChatOpenAI", "ChatAnthropic", "ChatOllama"],
    "thread_id":          ["thread_id"],
}


def _static_analysis(code: str) -> dict[str, bool]:
    found: dict[str, bool] = {}
    code_lower = code.lower()
    for key, patterns in _PATTERNS.items():
        found[key] = any(p.lower() in code_lower for p in patterns)
    return found


# ── Фаза 3: subprocess-запуск ─────────────────────────────────────────────────

def _venv_python() -> str:
    """
    Путь к Python проектного .venv. Сюда ставятся зависимости и им же
    запускается решение (deps и рантайм ДОЛЖНЫ быть один интерпретатор).

    Приоритет:
      1. <project_root>/.venv/(Scripts|bin)/python — явно проектный venv
      2. sys.executable — если запущены уже из него
    Никогда не ставим в глобальный Python.
    """
    # tester.py = <root>/src/orchestrator/agents/tester.py → parents[3] = <root>
    root = Path(__file__).resolve().parents[3]
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",   # Windows
        root / ".venv" / "bin" / "python",            # POSIX
        root / ".venv" / "bin" / "python3",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return sys.executable


# Резолвим один раз при импорте
VENV_PYTHON = _venv_python()


def _make_test_env() -> dict[str, str]:
    """Среда для subprocess: проектный venv + .env переменные."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


# pip-имя -> import-имя (для проверки уже-установленности, где отличаются)
_PKG_IMPORT_ALIAS = {
    "langchain-openai": "langchain_openai",
    "langchain-core": "langchain_core",
    "langchain-community": "langchain_community",
    "langchain-mcp-adapters": "langchain_mcp_adapters",
    "python-dotenv": "dotenv",
    "beautifulsoup4": "bs4",
    "pillow": "PIL",
    "pyyaml": "yaml",
    "opencv-python": "cv2",
    "scikit-learn": "sklearn",
}

# import-имя -> pip-имя (только исключения; по умолчанию совпадают)
_IMPORT_TO_PKG = {
    "langchain_openai": "langchain-openai",
    "langchain_core": "langchain-core",
    "langchain_community": "langchain-community",
    "langchain_mcp_adapters": "langchain-mcp-adapters",
    "dotenv": "python-dotenv",
    "bs4": "beautifulsoup4",
    "PIL": "pillow",
    "yaml": "pyyaml",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
}

_STDLIB = set(sys.stdlib_module_names)


def _imports_from_code(code: str) -> list[str]:
    """
    Достаёт top-level импорты из кода через AST → список pip-имён.
    Это надёжнее чем 'pip install' из задания: ставим ровно то, что
    скрипт реально импортирует (LLM мог добавить либу не из условия).
    Stdlib и относительные импорты отбрасываем.
    """
    import ast
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return []
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:   # 0 = не относительный (не from .x)
                mods.add(node.module.split(".")[0])
    pkgs: list[str] = []
    for m in sorted(mods):
        if not m or m in _STDLIB or m.startswith("_"):
            continue
        pkgs.append(_IMPORT_TO_PKG.get(m, m))
    return pkgs


def _merge_deps(task_pkgs: list[str], code_pkgs: list[str]) -> list[str]:
    """
    Объединяет пакеты из 'pip install' задания и из импортов кода.
    Версии из задания (langchain==1.2.10) приоритетнее голого имени из кода.
    """
    def base(spec: str) -> str:
        import re as _re
        return _re.split(r"[<>=!\[;]", spec)[0].strip().lower().replace("_", "-")

    merged: list[str] = list(task_pkgs)
    covered = {base(p) for p in task_pkgs}
    for cp in code_pkgs:
        if base(cp) not in covered:
            merged.append(cp)
            covered.add(base(cp))
    return merged


def _parse_pip_packages(task: str) -> list[str]:
    """
    Достаёт имена пакетов из строк 'pip install ...' в тексте задания.
    Берём только явно указанное автором задания — ничего произвольного.
    """
    import re
    pkgs: list[str] = []
    for m in re.finditer(r"pip\s+install\s+([^\n`]+)", task, re.IGNORECASE):
        chunk = m.group(1).strip().strip("`").strip()
        for tok in chunk.split():
            if tok.startswith("-"):          # флаги (-U, --upgrade) пропускаем
                continue
            # имя пакета (с возможным ==версия), без мусора
            name = re.split(r"[<>=!;]", tok)[0].strip()
            if re.fullmatch(r"[A-Za-z0-9_.\-\[\]]+", name) and name not in pkgs:
                pkgs.append(tok)
    return pkgs


def _missing_packages(pkgs: list[str]) -> list[str]:
    """Фильтрует уже установленные — ставим только реально отсутствующие."""
    import importlib.util
    missing = []
    for spec in pkgs:
        import re as _re
        base = _re.split(r"[<>=!\[;]", spec)[0].strip().lower()
        mod = _PKG_IMPORT_ALIAS.get(base, base.replace("-", "_"))
        try:
            if importlib.util.find_spec(mod) is None:
                missing.append(spec)
        except (ImportError, ValueError, ModuleNotFoundError):
            missing.append(spec)
    return missing


async def _install_task_deps(task: str, code: str = "") -> str:
    """
    Ставит зависимости ПЕРЕД запуском решения. Два источника:
      1. 'pip install ...' из текста задания (с версиями)
      2. реальные import-ы из сгенерированного кода (через AST)
    Без этого скрипт падает на ModuleNotFoundError и тест бессмыслен.
    """
    import asyncio

    task_pkgs = _parse_pip_packages(task)
    code_pkgs = _imports_from_code(code) if code else []
    pkgs = _merge_deps(task_pkgs, code_pkgs)
    if not pkgs:
        return "зависимости не найдены"

    missing = _missing_packages(pkgs)
    if not missing:
        return f"все уже стоят ({len(pkgs)})"

    viz.notify("tester", f"pip install {' '.join(missing)[:40]}", "sub_step")
    try:
        proc = await asyncio.create_subprocess_exec(
            VENV_PYTHON, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
            *missing,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_make_test_env(),
        )
        try:
            _, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            return f"таймаут pip install ({', '.join(missing)})"
        if proc.returncode == 0:
            return f"установлено: {', '.join(missing)}"
        err = stderr_b.decode("utf-8", errors="replace")[-200:]
        return f"pip fail ({', '.join(missing)}): {err}"
    except Exception as e:
        return f"pip ошибка: {type(e).__name__}: {e}"


_SCENARIO_SYSTEM = """Ты анализируешь Python-скрипт и генерируешь тестовые входные данные (stdin).

Найди все вызовы input() и интерактивные циклы в коде. Сгенерируй реалистичный набор строк ввода:
- Используй примеры из задания если они есть (названия продуктов, города, вопросы и т.п.)
- Для chat-циклов (while True: input(...)) — добавь "exit" или "выход" последней строкой
- Для confirm-вопросов (Y/n) — отвечай "y"
- Для questionary.select или подобных — отвечай Enter (пустая строка)

Отвечай ТОЛЬКО строками stdin — одна строка = один вызов input().
НИКАКОГО другого текста, объяснений или форматирования. Только сами строки."""


async def _generate_test_inputs(code: str, task: str, llm) -> bytes:
    """LLM генерирует stdin-строки для тест-прогона. Возвращает bytes для subprocess."""
    import re
    # Быстро проверим — есть ли вообще input() в коде
    has_input = bool(re.search(r"\binput\s*\(", code))
    if not has_input:
        return b""

    messages = [
        SystemMessage(content=_SCENARIO_SYSTEM),
        HumanMessage(content=f"ЗАДАНИЕ:\n{task}\n\nКОД:\n{code}"),
    ]
    response = await llm.ainvoke(messages)
    lines = response.content.strip()
    # Добавляем финальный перевод строки чтобы последний input() получил данные
    return (lines + "\n").encode("utf-8")


async def _run_subprocess_full(code: str, stdin_data: bytes, timeout: int = 60) -> dict:
    """
    Запускает скрипт с реальными тестовыми инпутами.
    Стримит stdout построчно в визуализатор по мере выполнения.
    """
    import asyncio

    clean = _extract_code(code)
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False, prefix="swagents_test_"
    ) as f:
        f.write(clean)
        path = f.name

    stdout_lines: list[str] = []
    stderr_buf: list[bytes] = []
    timed_out = False

    try:
        proc = await asyncio.create_subprocess_exec(
            VENV_PYTHON, path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_make_test_env(),
        )

        # Пишем stdin и одновременно читаем stdout построчно
        async def _write_stdin():
            try:
                if stdin_data:
                    proc.stdin.write(stdin_data)
                    await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                try:
                    proc.stdin.close()
                except Exception:
                    pass

        async def _read_stdout():
            while True:
                line_b = await proc.stdout.readline()
                if not line_b:
                    break
                line = line_b.decode("utf-8", errors="replace")
                stdout_lines.append(line)
                # Стримим в визуализатор построчно
                update_streaming_code("".join(stdout_lines), "запуск")

        async def _read_stderr():
            data = await proc.stderr.read()
            if data:
                stderr_buf.append(data)

        try:
            await asyncio.wait_for(
                asyncio.gather(_write_stdin(), _read_stdout(), _read_stderr()),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            timed_out = True
            proc.kill()
            # Дочитываем что осталось
            try:
                rem_out, rem_err = await asyncio.wait_for(proc.communicate(), timeout=5)
                if rem_out:
                    stdout_lines.append(rem_out.decode("utf-8", errors="replace"))
                if rem_err:
                    stderr_buf.append(rem_err)
            except asyncio.TimeoutError:
                pass

        await proc.wait()
        returncode = proc.returncode if not timed_out else -1

        # НЕ вызываем clear_streaming_code() — вывод остаётся видимым в панели
        # пока не начнётся фаза "оценка"
        return {
            "ok": returncode == 0 and not timed_out,
            "timed_out": timed_out,
            "returncode": returncode,
            "stdout": "".join(stdout_lines)[:3000],
            "stderr": b"".join(stderr_buf).decode("utf-8", errors="replace")[:1500],
            "stdin_sent": stdin_data.decode("utf-8", errors="replace") if stdin_data else "(нет)",
        }
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ── Фаза 4: LLM-оценка (стриминг) ────────────────────────────────────────────

_SCORER_SYSTEM = """Ты — строгий технический эксперт, оценивающий решения учебных заданий по Python.

Получишь:
  ЗАДАНИЕ: — текст задания с критериями оценки
  КОД: — решение студента

КРИТИЧЕСКИ ВАЖНО — НЕ ШТРАФУЙ за следующее:
  - Использование OpenRouter, реального API-ключа, или любого base_url вместо 'http://localhost:1234' и api_key='fake'.
    Причина: оркестратор автоматически подставляет реальные параметры LLM из конфигурации. Структура подключения верна — только адрес и ключ заменены.
  - Отсутствие заглушек вроде '<название модели>' — они намеренно заменены реальными значениями.
  Оценивай СТРУКТУРУ и ЛОГИКУ кода, а не конкретные значения параметров подключения к LLM.

Твоя задача — оценить решение по критериям из задания (если есть явные баллы — используй их).
Если явных критериев нет, выбери 4-6 разумных метрик сам.

Формат ответа — СТРОГО такой (не отступай от него):

ОЦЕНКА:
| Критерий | Баллы | Макс | Комментарий |
|----------|-------|------|-------------|
| <критерий> | <X> | <N> | <коротко> |
...
| ИТОГО | <сумма> | <макс> | |

ПРОБЛЕМЫ:
- <конкретная проблема или "Проблем не обнаружено">

ВЕРДИКТ: ОТЛИЧНО / ХОРОШО / ТРЕБУЕТ ДОРАБОТКИ / ПРОВАЛ
ПРОЦЕНТ: <число>%
"""


async def _llm_score(code: str, task: str, llm) -> str:
    """Стримит LLM-оценку в визуализатор, возвращает итоговый текст."""
    messages = [
        SystemMessage(content=_SCORER_SYSTEM),
        HumanMessage(content=f"ЗАДАНИЕ:\n{task}\n\nКОД:\n{code}"),
    ]
    accumulated = ""
    async for chunk in llm.astream(messages):
        accumulated += chunk.content
        update_streaming_code(accumulated, "оценка")
    clear_streaming_code()
    return accumulated


# ── Форматирование отчёта ─────────────────────────────────────────────────────

def _format_report(syntax: tuple, static: dict, run: dict, score: str) -> str:
    lines = []

    # Синтаксис
    ok_str = "✓ OK" if syntax[0] else f"✗ ОШИБКА: {syntax[1]}"
    lines.append(f"[СИНТАКСИС] {ok_str}")

    # Статический анализ
    found = [k for k, v in static.items() if v]
    missing = [k for k, v in static.items() if not v]
    if found:
        lines.append(f"[ПАТТЕРНЫ] найдено: {', '.join(found)}")
    if missing:
        lines.append(f"[ПАТТЕРНЫ] не найдено: {', '.join(missing)}")

    # Зависимости
    deps_status = run.get("deps_status", "")
    if deps_status:
        lines.append(f"[DEPS] {deps_status}")

    # Stdin который был отправлен
    stdin_sent = run.get("stdin_sent", "")
    if stdin_sent and stdin_sent != "(нет)":
        stdin_preview = " | ".join(stdin_sent.strip().splitlines())
        lines.append(f"[STDIN] {stdin_preview[:120]}")

    # Subprocess
    if run["timed_out"]:
        lines.append("[ЗАПУСК] ⏱ Таймаут 60s (LLM-вызовы выполнялись — это нормально)")
    elif run["ok"]:
        lines.append("[ЗАПУСК] ✓ Завершился успешно")
    else:
        lines.append(f"[ЗАПУСК] ✗ Exit code {run['returncode']}")

    if run["stdout"]:
        lines.append(f"[STDOUT]\n{run['stdout']}")
    if run["stderr"]:
        err_lines = [
            l for l in run["stderr"].splitlines()
            if l.strip() and ("Error" in l or "Traceback" in l or "Warning" in l or "Exception" in l)
        ]
        if err_lines:
            lines.append(f"[STDERR]\n" + "\n".join(err_lines[:20]))

    # LLM-оценка
    lines.append("\n" + score)

    return "\n".join(lines)


# ── Нода графа ────────────────────────────────────────────────────────────────

def make_tester_node():
    llm = make_llm(temperature=0.0).with_retry(stop_after_attempt=2)

    async def node(state: OrchestratorState) -> dict:
        code = state.get("generated_code", "")
        task = state.get("task_description", "")
        clean_code = _extract_code(code)

        # 1. Синтаксис
        viz.notify("tester", "Проверяю синтаксис...", "sub_step")
        syntax = _check_syntax(clean_code)

        # 2. Статический анализ
        viz.notify("tester", "Статический анализ...", "sub_step")
        static = _static_analysis(clean_code)

        # 3. Установка зависимостей: pip install из задания + import-ы из кода
        viz.notify("tester", "Проверяю зависимости...", "sub_step")
        deps_status = await _install_task_deps(task, clean_code)
        viz.notify("tester", f"deps: {deps_status[:45]}", "sub_step")

        # 4. LLM генерирует тест-сценарий (stdin)
        viz.notify("tester", "Генерирую тест-сценарий...", "sub_step")
        stdin_data = await _generate_test_inputs(clean_code, task, llm)
        if stdin_data:
            preview = " | ".join(stdin_data.decode("utf-8", errors="replace").strip().splitlines())
            viz.notify("tester", f"stdin: {preview[:40]}", "sub_step")

        # 5. Полноценный запуск с реальными LLM-вызовами (стримит stdout)
        viz.notify("tester", "Запускаю скрипт (до 60s)...", "sub_step")
        run = await _run_subprocess_full(clean_code, stdin_data, timeout=60)
        run["deps_status"] = deps_status

        # Переключаем метку на "вывод" — контент остаётся в панели как статичный вывод
        # пока не начнётся следующая фаза (оценка заменит его)
        if run["stdout"]:
            update_streaming_code(run["stdout"], "вывод")
            status = f"stdout {len(run['stdout'])} симв"
        elif run["stderr"]:
            update_streaming_code(run["stderr"], "вывод")
            status = "только stderr"
        else:
            status = "нет вывода"

        if run["timed_out"]:
            viz.notify("tester", f"Таймаут 60s — {status}", "sub_step")
        elif run["ok"]:
            viz.notify("tester", f"✓ Завершился — {status}", "sub_step")
        else:
            viz.notify("tester", f"✗ Exit {run['returncode']} — {status}", "sub_step")

        # 6. LLM оценка по критериям задания (стримит оценку, заменяет вывод в панели)
        viz.notify("tester", "LLM оценивает...", "sub_step")
        # Передаём stdout в оценщик — он видит реальный вывод и оценивает его тоже
        task_with_output = task
        if run["stdout"]:
            task_with_output += f"\n\n--- РЕАЛЬНЫЙ ВЫВОД СКРИПТА ПРИ ТЕСТОВОМ ЗАПУСКЕ ---\n{run['stdout'][:2000]}"
        if run["stderr"] and ("Error" in run["stderr"] or "Traceback" in run["stderr"]):
            task_with_output += f"\n\n--- STDERR (ОШИБКИ) ---\n{run['stderr'][:800]}"
        score_text = await _llm_score(code, task_with_output, llm)

        report = _format_report(syntax, static, run, score_text)
        viz.notify("tester", "Тестирование завершено", "node_done")
        return {"test_results": report}

    return node
