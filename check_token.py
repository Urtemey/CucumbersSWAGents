import httpx, os
from dotenv import load_dotenv
load_dotenv(override=True)

key = os.environ["OPENAI_API_KEY"]
base = os.environ["LM_STUDIO_BASE_URL"]
model = os.environ["LM_STUDIO_MODEL"]

print(f"Key: {key[:20]}...")
print(f"Base: {base}")
print(f"Model: {model}")

r = httpx.post(
    f"{base}/chat/completions",
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    json={"model": model, "messages": [{"role": "user", "content": "Say hi"}], "max_tokens": 20},
    timeout=30,
)
print(f"\nStatus: {r.status_code}")
print(r.text[:500])
