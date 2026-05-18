"""
MCP-клиент: подключается к gitea-mcp и platform-mcp,
возвращает инструменты как LangChain Tool-объекты.

langchain-mcp-adapters >= 0.1.0: MultiServerMCPClient не context manager,
нужно вызывать await client.get_tools() напрямую.
"""
import os
import shutil
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from orchestrator.config import cfg


def _uvx_path() -> str:
    path = shutil.which("uvx")
    if path is None:
        raise RuntimeError("uvx не найден в PATH. Установи uv: https://docs.astral.sh/uv/")
    return path


def build_gitea_server_config() -> dict[str, Any]:
    if not cfg.gitea_token:
        raise ValueError("GITEA_TOKEN не задан в .env")
    return {
        "transport": "stdio",
        "command": _uvx_path(),
        "args": [
            "--python", "3.11",
            "--extra-index-url",
            "https://nikitatsym.github.io/gitea-mcp/simple",
            "gitea-mcp",
        ],
        "env": {
            **os.environ,
            "GITEA_URL": cfg.gitea_url,
            "GITEA_TOKEN": cfg.gitea_token,
        },
    }


def build_platform_server_config() -> dict[str, Any]:
    headers = {}
    if cfg.platform_token:
        headers["Authorization"] = f"Bearer {cfg.platform_token}"
    return {
        "transport": "streamable_http",
        "url": cfg.platform_mcp_url,
        "headers": headers,
    }


async def get_gitea_tools() -> list:
    client = MultiServerMCPClient({"gitea": build_gitea_server_config()})
    return await client.get_tools()


async def get_platform_tools() -> list:
    client = MultiServerMCPClient({"platform": build_platform_server_config()})
    return await client.get_tools()


async def get_all_tools() -> list:
    servers: dict[str, Any] = {"gitea": build_gitea_server_config()}
    if cfg.platform_mcp_url:
        servers["platform"] = build_platform_server_config()
    client = MultiServerMCPClient(servers)
    return await client.get_tools()
