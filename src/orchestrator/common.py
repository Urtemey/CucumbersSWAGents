"""Общие типы и утилиты — без круговых импортов."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from orchestrator.config import cfg


class OrchestratorState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    task_description: str
    task_id: str
    prepared: bool          # task_fetcher отработал (фетч + обогащение доками)
    generated_code: str
    test_results: str
    submission_result: str
    next_agent: str
    dry_run: bool
    retry_count: int


def make_llm(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=cfg.lm_base_url,
        api_key=SecretStr(cfg.openai_api_key),
        model=cfg.lm_model,
        temperature=temperature,
    )
