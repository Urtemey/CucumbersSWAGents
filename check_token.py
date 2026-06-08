"""Проверка LLM API (оркестратор + те же параметры попадут в solution через inject_llm_params)."""
import httpx
from orchestrator.config import cfg

print(f"Key: {cfg.openai_api_key[:12]}...")
print(f"Base: {cfg.lm_base_url}")
print(f"Model: {cfg.lm_model}")

r = httpx.post(
    f"{cfg.lm_base_url.rstrip('/')}/chat/completions",
    headers={"Authorization": f"Bearer {cfg.openai_api_key}", "Content-Type": "application/json"},
    json={"model": cfg.lm_model, "messages": [{"role": "user", "content": "Say hi"}], "max_tokens": 20},
    timeout=60,
    trust_env=False,
)
print(f"\nStatus: {r.status_code}")
print(r.text[:500])
