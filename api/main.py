import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

app = FastAPI(title="AI Gateway", version="0.1.0")

class GenerateIn(BaseModel):
    prompt: str
    model: str = "qwen2.5-coder:7b"
    stream: bool = False
    options: dict | None = None

@app.get("/health")
def health():
    return {"ok": True, "ollama": OLLAMA_BASE_URL}

@app.get("/models")
def models():
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Ollama: {e}")

@app.post("/generate")
def generate(payload: GenerateIn):
    body = {
        "model": payload.model,
        "prompt": payload.prompt,
        "stream": payload.stream,
    }
    if payload.options:
        body["options"] = payload.options

    try:
        r = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=body, timeout=300)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Ollama HTTP error: {e} | {r.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Ollama: {e}")
