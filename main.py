import json
import os
import re
import httpx
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field # Adicionado Field para validação
from typing import List, Optional

app = FastAPI(title="Orquestrador Seguro e Persistente - S2")

DB_FILE = "sessions_db.json"
logging.basicConfig(level=logging.INFO)

# --- DB OPS ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

sessions = load_db()

# --- MODELO COM VALIDAÇÃO (Pydantic) ---
class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=50)
    task: str = Field(..., min_length=2, max_length=2000) # Máximo 2000 chars
    language: Optional[str] = "python"

def clean_code(text: str) -> str:
    text = re.sub(r'```(?:[a-zA-Z+]*)\n?', '', text)
    text = text.replace('```', '')
    return text.strip()

@app.post("/v1/chat")
async def chat_with_persistent_context(request: ChatRequest):
    # 1. Validação de segurança extra (Manual)
    if not request.task.strip():
        raise HTTPException(status_code=400, detail="A tarefa não pode conter apenas espaços.")

    # 2. Gestão de Histórico
    if request.session_id not in sessions:
        sessions[request.session_id] = []
    
    history = sessions[request.session_id]
    context_str = "\n".join([f"User: {h['u']}\nAI: {h['a']}" for h in history[-3:]])
    
    full_prompt = (
        f"Histórico:\n{context_str}\n"
        f"[INST] Tarefa: {request.task} em {request.language}. Responda apenas o código. [/INST]"
    )
    
    url = "http://10.10.1.2:9010/generate"
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                json={
                    "model": "qwen2.5-coder:7b",
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_ctx": 4096} # Limite de contexto no Ollama
                }
            )
            
            if response.status_code != 200:
                logging.error(f"Erro no Dev A: {response.status_code}")
                raise HTTPException(status_code=502, detail="IA offline ou congestionada")

            data = response.json()
            final_code = clean_code(data.get("response", ""))
            
            # 3. Persistência
            sessions[request.session_id].append({"u": request.task, "a": final_code})
            save_db(sessions)
            
            return {
                "session_id": request.session_id,
                "code": final_code,
                "usage": {"prompt_chars": len(full_prompt)}
            }
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="O Dev A demorou muito para processar.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
