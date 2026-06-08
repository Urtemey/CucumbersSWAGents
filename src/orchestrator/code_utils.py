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
    code_end_re = re.compile(r"^[А-ЯA-ZЁ][\wа-я ,.\-—:]+[.!?]\s*$")   # «Готово.», «Этот код делает...»
    for i, line in enumerate(lines):
        if code_start_re.match(line):
            tail_lines = lines[i:]
            # Обрезаем хвост: первая строка, похожая на естественный язык (заглавная буква + точка/!?)
            for j, tl in enumerate(tail_lines):
                if j > 5 and code_end_re.match(tl) and not tl.lstrip().startswith(("#", "from ", "import ", "def ", "class ")):
                    tail_lines = tail_lines[:j]
                    break
            return "\n".join(tail_lines).strip()

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


def _uses_non_openai_llm(code: str) -> bool:
    """
    Эвристика: задание требует НЕ ChatOpenAI (Ollama, Anthropic, Mistral, и т.п.).
    В таких случаях не подменяем base_url/api_key/model на jrnl-туннель — это
    другой провайдер, наши значения сломают задание.
    """
    markers = (
        "ChatOllama", "langchain_ollama", "from langchain_community.llms import Ollama",
        "ChatAnthropic", "langchain_anthropic",
        "ChatMistralAI", "langchain_mistralai",
        "ChatGoogleGenerativeAI", "langchain_google_genai",
        "ChatCohere", "langchain_cohere",
    )
    return any(m in code for m in markers)


def inject_llm_params(code: str) -> str:
    """
    Детерминированно подставляет реальные параметры LLM.

    Два слоя защиты:
      1. Заменяем явные плейсхолдеры (если coder следовал инструкции)
      2. Регекс-сеть для типовых заглушек из условий заданий
         (localhost:1234, api_key='fake', '<название модели>' и т.п.)

    Если в коде использован НЕ ChatOpenAI (Ollama/Anthropic/...) — слои 1 и 2
    пропускаются: задание требует конкретный провайдер, мы не должны его ломать.
    """
    if not code:
        return code

    # Задание требует конкретный не-OpenAI провайдер — ничего не подменяем.
    if _uses_non_openai_llm(code):
        return code

    # Слой 1: наши плейсхолдеры — ГАРАНТИРУЕМ кавычки.
    # Слабая модель часто пишет model=__LLM_MODEL__ без кавычек → SyntaxError.
    # Поэтому сначала меняем варианты В кавычках (сохраняя их), потом
    # любые ОСТАВШИЕСЯ голые плейсхолдеры заворачиваем в одинарные кавычки.
    for ph, val in [(PH_BASE_URL, cfg.lm_base_url),
                    (PH_API_KEY, cfg.openai_api_key),
                    (PH_MODEL, cfg.lm_model)]:
        safe_val = val.replace("'", "\\'")
        for q in ('"', "'"):
            code = code.replace(f"{q}{ph}{q}", f"{q}{safe_val}{q}")
        # Голый плейсхолдер (вне кавычек) → оборачиваем
        code = code.replace(ph, f"'{safe_val}'")

    # Слой 2: типовые заглушки из условий заданий
    # base_url -> наш (localhost, openrouter, старый platform path)
    code = re.sub(
        r"""(base_url\s*=\s*)['"]https?://(?:localhost:1234|127\.0\.0\.1:1234|openrouter\.ai|platform\.brojs\.ru)[^'"]*['"]""",
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


# ── Детерминированный фикс устаревшего API ────────────────────────────────────
# Слабые модели любят писать langchain 0.x по памяти. Зачем спорить с моделью,
# если можно прямо в исходнике заменить запретные конструкции на современные.

_LEGACY_REPLACEMENTS: list[tuple[str, str]] = [
    # Импорты-агенты 0.x → 1.x
    (r"from\s+langchain\.agents\s+import\s+AgentExecutor[^\n]*",
     "from langchain.agents import create_agent"),
    (r"from\s+langchain\.agents\s+import\s+create_openai_functions_agent[^\n]*",
     "from langchain.agents import create_agent"),
    (r"from\s+langchain\.agents\s+import\s+create_react_agent[^\n]*",
     "from langchain.agents import create_agent"),
    (r"from\s+langchain\.agents\s+import\s+initialize_agent[^\n]*",
     "from langchain.agents import create_agent"),
    # LLMChain → прямой вызов LLM (заглушка-замена импорта)
    (r"from\s+langchain\.chains\s+import\s+LLMChain[^\n]*", ""),
    (r"from\s+langchain\.llms\s+import\s+OpenAI[^\n]*",
     "from langchain_openai import ChatOpenAI"),
    # Вызовы конструкторов
    (r"\bcreate_openai_functions_agent\b", "create_agent"),
    (r"\bcreate_react_agent\b(?!\s*=)", "create_agent"),
    (r"\binitialize_agent\b", "create_agent"),
]


def fix_legacy_api(code: str) -> tuple[str, list[str]]:
    """
    Детерминированно меняет langchain 0.x на 1.x.
    Возвращает (исправленный_код, список_что_было_заменено).
    """
    if not code:
        return code, []
    applied: list[str] = []
    for pattern, replacement in _LEGACY_REPLACEMENTS:
        new_code, n = re.subn(pattern, replacement, code)
        if n > 0:
            applied.append(f"{pattern.split(chr(92))[0][:30]}×{n}")
            code = new_code
    return code, applied


def strip_prose_prefix(text: str) -> str:
    """
    Слабые модели часто пишут 'Вот решение:' / 'Конечно!' перед блоком кода.
    Это безвредно, но иногда модель забывает закрывающие ``` — тогда
    extract_code_block ловит ВСЁ от первого ``` до конца, включая мусор.
    Эта функция отрезает явно нерелевантный пролог до первой ```.
    """
    if not text or "```" not in text:
        return text
    idx = text.find("```")
    if idx == 0:
        return text
    # Если до ``` меньше 400 символов — это пролог, отрезаем
    if idx < 400:
        return text[idx:]
    return text
