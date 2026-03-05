# =============================================================================
# Dev B — Orquestrador LangChain | Fase 3 — Passo 1b: Persistência SQLite
# =============================================================================
# Mudança: JsonFileChatHistory → SQLChatMessageHistory (LangChain nativo)
# Um único arquivo /data/sessions.db guarda todas as sessões em tabelas SQL.
# Append-only, sem race condition, sem reescrever arquivo inteiro.
# Dependência nova: langchain-community + aiosqlite
# =============================================================================

from __future__ import annotations

import asyncio
import logging
from typing import Any, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.language_models import BaseLLM
from langchain_core.outputs import Generation, LLMResult
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from pydantic import BaseModel, Field

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("dev-b")

# =============================================================================
# 1. CUSTOM LLM — sem alterações
# =============================================================================

class QwenCustomLLM(BaseLLM):
    base_url: str = Field(default="http://10.10.1.2:9010")
    model_name: str = Field(default="qwen2.5-coder:7b")
    timeout: float = Field(default=60.0)
    response_key: str = Field(default="response")

    @property
    def _llm_type(self) -> str:
        return "qwen-custom"

    def _generate(self, prompts: List[str], stop: Optional[List[str]] = None, **kwargs: Any) -> LLMResult:
        generations = [[Generation(text=self._call_dev_a(p))] for p in prompts]
        return LLMResult(generations=generations)

    async def _agenerate(self, prompts: List[str], stop: Optional[List[str]] = None, **kwargs: Any) -> LLMResult:
        texts = await asyncio.gather(*[self._acall_dev_a(p) for p in prompts])
        return LLMResult(generations=[[Generation(text=t)] for t in texts])

    def _build_payload(self, prompt: str) -> dict:
        return {"prompt": prompt, "model": self.model_name, "stream": False}

    def _extract_text(self, data: dict) -> str:
        return data.get(self.response_key, str(data))

    def _call_dev_a(self, prompt: str) -> str:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/generate", json=self._build_payload(prompt))
            resp.raise_for_status()
            return self._extract_text(resp.json())

    async def _acall_dev_a(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/generate", json=self._build_payload(prompt))
            resp.raise_for_status()
            return self._extract_text(resp.json())


# =============================================================================
# 2. PERSISTÊNCIA SQLite — 4 linhas substituem toda a classe JSON anterior
# =============================================================================

DB_PATH = "sqlite:///data/sessions.db"
# No Docker, mapeie o diretório /data para um volume:
#   -v /seu/host/data:/data


def get_session_history(session_id: str) -> SQLChatMessageHistory:
    """
    Retorna o histórico da sessão direto do SQLite.
    O LangChain cria a tabela automaticamente na primeira execução.
    Cada sessão é uma partição isolada por session_id dentro do mesmo .db.
    """
    return SQLChatMessageHistory(
        session_id=session_id,
        connection_string=DB_PATH,
    )


# =============================================================================
# 3. CHAIN COM MEMÓRIA — sem alterações
# =============================================================================

llm = QwenCustomLLM(
    base_url="http://10.10.1.2:9010",
    model_name="qwen2.5-coder:7b",
    timeout=60.0,
    response_key="response",
)

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Você é um assistente especialista em programação. "
        "Responda de forma clara e objetiva. "
        "Quando o usuário pedir alterações, use o contexto da conversa anterior.",
    ),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{task}"),
])

chain_with_memory = RunnableWithMessageHistory(
    prompt | llm,
    get_session_history,
    input_messages_key="task",
    history_messages_key="history",
)


# =============================================================================
# 4. FASTAPI
# =============================================================================

app = FastAPI(
    title="Dev B — Orquestrador LangChain",
    description="Fase 3 — Persistência SQLite: histórico salvo em banco por sessão.",
    version="5.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="ID da sessão.")
    task: str = Field(..., description="Mensagem atual do usuário.")


class ChatResponse(BaseModel):
    session_id: str
    code: str
    history_length: int


@app.get("/health")
async def health():
    return {
        "status": "online",
        "mode": "sqlite-persistence",
        "db": DB_PATH,
    }


@app.post("/v1/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    log.info("Nova mensagem — sessão=%s | task=%s", request.session_id, request.task[:60])
    try:
        result: str = await chain_with_memory.ainvoke(
            {"task": request.task},
            config={"configurable": {"session_id": request.session_id}},
        )
        history = get_session_history(request.session_id)
        msgs = history.messages
        log.info("Resposta gerada — sessão=%s | histórico=%d msgs", request.session_id, len(msgs))
        return ChatResponse(
            session_id=request.session_id,
            code=result,
            history_length=len(msgs),
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Dev A retornou {exc.response.status_code}: {exc.response.text}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Falha na conexão com Dev A: {exc}")
    except Exception as exc:
        log.exception("Erro inesperado na sessão %s", request.session_id)
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/v1/chat/{session_id}")
async def clear_session(session_id: str):
    """Apaga o histórico de uma sessão do banco — botão 'Nova conversa'."""
    get_session_history(session_id).clear()
    return {"status": "cleared", "session_id": session_id}


@app.get("/v1/chat/{session_id}/history")
async def get_history(session_id: str):
    """Retorna o histórico completo de uma sessão."""
    history = get_session_history(session_id)
    msgs = history.messages
    return {
        "session_id": session_id,
        "history_length": len(msgs),
        "messages": [
            {"role": type(m).__name__, "content": m.content}
            for m in msgs
        ],
    }


@app.get("/v1/sessions")
async def list_sessions():
    """Lista todas as sessões existentes no banco."""
    import sqlite3, re
    # Extrai o caminho do arquivo do connection string
    db_file = DB_PATH.replace("sqlite:///", "")
    try:
        conn = sqlite3.connect(db_file)
        rows = conn.execute(
            "SELECT DISTINCT session_id, COUNT(*) as msgs "
            "FROM message_store GROUP BY session_id"
        ).fetchall()
        conn.close()
        return {
            "total": len(rows),
            "sessions": [{"session_id": r[0], "messages": r[1]} for r in rows],
        }
    except Exception as exc:
        return {"total": 0, "sessions": [], "detail": str(exc)}


# =============================================================================
# 5. ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
