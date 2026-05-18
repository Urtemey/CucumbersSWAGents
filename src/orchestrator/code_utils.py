"""
Детерминированные утилиты обработки сгенерированного кода.

Принцип робастности: всё что можно сделать кодом — делаем кодом, а не промптом.
Чем меньше ответственности у LLM, тем стабильнее работают слабые модели.
"""
from __future__ import annotations

import ast
import re
from typing import Optional

from orchestrator.config import cfg

# Плейсхолдеры, которые coder вставляет вместо реальных параметров LLM.
# Python подставляет реальные значения детерминированно после генерации.
PH_BASE_URL = "__LLM_BASE_URL__"
PH_API_KEY = "__LLM_API_KEY__"
PH_MODEL = "__LLM_MODEL__"


def extract_code_block(text: str) -> str:
    """
    Достаёт Python-код из ответа LLM максимально устойчиво.

    Порядок попыток:
      1. Полный ```python ... ``` блок (закрытый)
      2. Открытый ```python без закрытия (модель оборвалась/забыла ```)
      3. Любой ``` ... ``` блок
      4. Эвристика: с первой строки, похожей на код (import/from/def/class/#)
      5. Фоллбэк: текст как есть
    """
    if not text:
        return ""

    # 1. Закрытый python-блок
    m = re.search(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # 2. Открытый python-блок без закрывающих ```
    m = re.search(r"```(?:python|py)?[ \t]*\r?\n(.*)", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # 3. Любой fenced-блок
    m = re.search(r"```[ \t]*\r?\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # 4. Эвристика: ищем первую строку, похожую на Python-код
    lines = text.splitlines()
    code_start_re = re.compile(r"^\s*(import |from |def |class |@|#!|if __name__)")
    for i, line in enumerate(lines):
        if code_start_re.match(line):
            candidate = "\n".join(lines[i:]).strip()
            # убираем хвостовую болтовню после кода (markdown-абзацы)
            return candidate

    # 5. Как есть
    return text.strip()


def looks_like_python(code: str) -> bool:
    """Грубая проверка что строка похожа на Python-решение, а не на прозу."""
    if not code or len(code.strip()) < 20:
        return False
    signals = ("import ", "from ", "def ", "class ", "print(", "=", "(")
    hits = sum(1 for s in signals if s in code)
    # хотя бы 2 сигнала и есть перевод строки (не однострочная фраза)
    return hits >= 2 and "\n" in code


def syntax_error(code: str) -> Optional[str]:
    """
    Детерминированная проверка синтаксиса через ast.parse.
    Возвращает строку с описанием ошибки (строка/позиция/текст) или None если OK.
    Это in-process и мгновенно — слабые модели часто рвут синтаксис.
    """
    if not code or not code.strip():
        return "пустой код"
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        loc = f"строка {e.lineno}"
        if e.offset:
            loc += f", позиция {e.offset}"
        bad_line = ""
        if e.lineno:
            lines = code.splitlines()
            if 0 < e.lineno <= len(lines):
                bad_line = lines[e.lineno - 1].strip()
        msg = f"{e.msg} ({loc})"
        if bad_line:
            msg += f": {bad_line!r}"
        return msg
    except Exception as e:  # ValueError на null-байтах и т.п.
        return f"{type(e).__name__}: {e}"


def inject_llm_params(code: str) -> str:
    """
    Детерминированно подставляет реальные параметры LLM.

    Два слоя защиты:
      1. Заменяем явные плейсхолдеры (если coder следовал инструкции)
      2. Регекс-сеть для типовых заглушек из условий заданий
         (localhost:1234, api_key='fake', '<название модели>' и т.п.)
    """
    if not code:
        return code

    # Слой 1: наши плейсхолдеры
    code = code.replace(PH_BASE_URL, cfg.lm_base_url)
    code = code.replace(PH_API_KEY, cfg.openai_api_key)
    code = code.replace(PH_MODEL, cfg.lm_model)

    # Слой 2: типовые заглушки из условий заданий
    # base_url -> наш
    code = re.sub(
        r"""(base_url\s*=\s*)['"]https?://localhost:1234(?:/v1)?['"]""",
        rf"\1'{cfg.lm_base_url}'",
        code,
    )
    # api_key='fake' / SecretStr('fake') / "fake-key" -> наш
    code = re.sub(
        r"""(api_key\s*=\s*(?:SecretStr\()?)['"](?:fake|fake-key|sk-fake|your-api-key|test)['"]""",
        rf"\1'{cfg.openai_api_key}'",
        code,
    )
    # model='<название модели в LM Studio>' / '<model>' -> наш
    code = re.sub(
        r"""(model\s*=\s*)['"]<[^'"]*>['"]""",
        rf"\1'{cfg.lm_model}'",
        code,
    )

    return code
