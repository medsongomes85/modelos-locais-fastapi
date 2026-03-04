from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel

app = FastAPI()

# Libera o acesso para o Dev C (Front-end)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    session_id: str
    task: str

@app.get("/health")
async def health():
    return {"status": "online", "mode": "direct-bridge"}

@app.post("/v1/chat")
async def chat_endpoint(request: ChatRequest):
    # 1. Monta o payload exatamente como o Dev A exige
    payload = {
        "prompt": request.task,
        "model": "qwen2.5-coder:7b",
        "stream": False
    }

    try:
        async with httpx.AsyncClient() as client:
            # 2. Bate na rota real do Dev A
            response = await client.post(
                "http://10.10.1.2:9010/generate",
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()

            # 3. Retorna a resposta para o Dev C
            # Nota: Verifique se o Dev A usa a chave 'response'. 
            # Se não, o data.get retornará o JSON inteiro para debug.
            return {
                "session_id": request.session_id,
                "code": data.get("response", data) 
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
