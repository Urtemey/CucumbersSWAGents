import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# override=True — перезаписывает системные переменные значениями из .env
load_dotenv(override=True)


@dataclass
class Config:
    # LLM (OpenRouter / LM Studio)
    lm_base_url: str = field(default_factory=lambda: os.environ.get("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"))
    lm_model: str = field(default_factory=lambda: os.environ.get("LM_STUDIO_MODEL", "gpt-oss:20b"))
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", "lm-studio"))

    # Gitea
    gitea_url: str = field(default_factory=lambda: os.environ.get("GITEA_URL", "https://git.brojs.ru"))
    gitea_token: str = field(default_factory=lambda: os.environ.get("GITEA_TOKEN", ""))
    gitea_owner: str = field(default_factory=lambda: os.environ.get("GITEA_OWNER", ""))

    # Platform
    platform_mcp_url: str = field(default_factory=lambda: os.environ.get("PLATFORM_MCP_URL", ""))
    platform_token: str = field(default_factory=lambda: os.environ.get("PLATFORM_TOKEN", ""))

    # Solutions repo
    solutions_repo: str = field(default_factory=lambda: os.environ.get("SOLUTIONS_REPO", "cucumbers-solutions"))
    auto_create_repo: bool = field(default_factory=lambda: os.environ.get("AUTO_CREATE_REPO", "true").lower() == "true")


cfg = Config()

# Принудительно выставляем в os.environ — langchain-openai читает его напрямую
os.environ["OPENAI_API_KEY"] = cfg.openai_api_key
os.environ["OPENAI_BASE_URL"] = cfg.lm_base_url
