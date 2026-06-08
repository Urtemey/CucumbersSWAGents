import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# override=True — перезаписывает системные переменные значениями из .env
load_dotenv(override=True)

_PLATFORM_INFERENCE_URL = "https://platform.brojs.ru/jrnl-bh/api/inference/v1"
# MCP-сервер журнала: инструменты tasks_list / task_get / task_text / task_submit и т.д.
# Транспорт http, Bearer auth с jrnl-токеном.
_JOURNAL_MCP_URL = "https://platform.brojs.ru/jrnl-bh/api/mcp"
_PLACEHOLDER_API_KEYS = frozenset({"", "lm-studio", "fake", "fake-key", "your-api-key", "test"})
# LM Studio: в UI «gpt-oss:20b», в API — openai/gpt-oss-20b
_MODEL_ALIASES = {
    "gpt-oss:20b": "openai/gpt-oss-20b",
    "gpt-oss-20b": "openai/gpt-oss-20b",
}


def _env_first(*names: str, default: str = "") -> str:
    """Берёт первое непустое значение из перечисленных env-переменных."""
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return default


def _default_lm_base_url() -> str:
    # LLM_BASE_URL — новое каноническое имя; LM_STUDIO_BASE_URL — legacy-алиас
    return _env_first("LLM_BASE_URL", "LM_STUDIO_BASE_URL", default=_PLATFORM_INFERENCE_URL)


def _default_lm_model() -> str:
    raw = _env_first("LLM_MODEL", "LM_STUDIO_MODEL", default="gpt-oss:20b")
    return _MODEL_ALIASES.get(raw, raw)


def _default_openai_api_key() -> str:
    """Ключ для OpenAI-compatible API: PLATFORM_TOKEN на inference платформы."""
    explicit = os.environ.get("OPENAI_API_KEY", "").strip()
    journal_token = _env_first("JOURNAL_TOKEN", "PLATFORM_TOKEN")
    base = _default_lm_base_url()
    if "platform.brojs.ru" in base and journal_token:
        if explicit.lower() in _PLACEHOLDER_API_KEYS:
            return journal_token
    return explicit or journal_token or "lm-studio"


@dataclass
class Config:
    # LLM (platform inference / OpenRouter / LM Studio)
    lm_base_url: str = field(default_factory=_default_lm_base_url)
    lm_model: str = field(default_factory=_default_lm_model)
    openai_api_key: str = field(default_factory=_default_openai_api_key)

    # Gitea
    gitea_url: str = field(default_factory=lambda: os.environ.get("GITEA_URL", "https://git.brojs.ru"))
    gitea_token: str = field(default_factory=lambda: os.environ.get("GITEA_TOKEN", ""))
    gitea_owner: str = field(default_factory=lambda: os.environ.get("GITEA_OWNER", ""))

    # Platform — Journal MCP. По умолчанию указываем рабочий endpoint;
    # PLATFORM_MCP_URL в .env может его переопределить (или поставить пустым, чтобы отключить).
    platform_mcp_url: str = field(default_factory=lambda: _env_first("PLATFORM_MCP_URL", default=_JOURNAL_MCP_URL))
    # Token для журнала. JOURNAL_TOKEN — новое каноническое имя (как у других студентов),
    # PLATFORM_TOKEN — наш legacy-алиас. Берём первое непустое.
    platform_token: str = field(default_factory=lambda: _env_first("JOURNAL_TOKEN", "PLATFORM_TOKEN", default=""))

    # Solutions repo
    solutions_repo: str = field(default_factory=lambda: os.environ.get("SOLUTIONS_REPO", "cucumbers-solutions"))
    auto_create_repo: bool = field(default_factory=lambda: os.environ.get("AUTO_CREATE_REPO", "true").lower() == "true")


cfg = Config()

# Принудительно выставляем в os.environ — langchain-openai читает его напрямую
os.environ["OPENAI_API_KEY"] = cfg.openai_api_key
os.environ["OPENAI_BASE_URL"] = cfg.lm_base_url
