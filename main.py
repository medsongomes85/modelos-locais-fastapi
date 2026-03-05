# =============================================================================
# Dev B — Orquestrador LangChain com Memória por Sessão
# =============================================================================
# Arquivo: main.py
# Fase 2: Adiciona RunnableWithMessageHistory para manter contexto por sessão.
# O session_id do Dev C agora é usado de verdade para isolar conversas.
# =============================================================================

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.language_models import BaseLLM
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import Generation, LLMResult
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from pydantic import BaseModel, Field


# =============================================================================
# 1. CUSTOM LLM — igual à Fase 1, sem alterações
# =============================================================================

class QwenCustomLLM(BaseLLM):
    """
    Custom LLM que bate exatamente em POST /generate do Dev A.
    Contrato: {"prompt": str, "model": str, "stream": bool}
    """

    base_url: str = Field(default="http://10.10.1.2:9010")
    model_name: str = Field(default="qwen2.5-coder:7b")
    timeout: float = Field(default=60.0)
    response_key: str = Field(default="response")

    @property
    def _llm_type(self) -> str:
        return "qwen-custom"

    def _generate(
        self, prompts: List[str], stop: Optional[List[str]] = None, **kwargs: Any
    ) -> LLMResult:
        generations = [[Generation(text=self._call_dev_a(p))] for p in prompts]
        return LLMResult(generations=generations)

    async def _agenerate(
        self, prompts: List[str], stop: Optional[List[str]] = None, **kwargs: Any
    ) -> LLMResult:
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
            resp = await client.post(
                f"{self.base_url}/generate", json=self._build_payload(prompt)
            )
            resp.raise_for_status()
            return self._extract_text(resp.json())


# =============================================================================
# 2. STORE DE MEMÓRIA — guarda histórico por session_id
# =============================================================================

class InMemoryChatHistory(BaseChatMessageHistory):
    """
    Histórico de mensagens em memória para uma única sessão.
    Implementa a interface que o RunnableWithMessageHistory exige.
    """

    def __init__(self) -> None:
        self.messages: List[BaseMessage] = []

    def add_messages(self, messages: List[BaseMessage]) -> None:
        self.messages.extend(messages)

    def clear(self) -> None:
        self.messages = []


# Dicionário global: session_id → InMemoryChatHistory
# Em produção, substitua por Redis ou banco de dados.
_session_store: dict[str, InMemoryChatHistory] = {}


def get_session_history(session_id: str) -> InMemoryChatHistory:
    """
    Retorna o histórico da sessão, criando um novo se não existir.
    Esta função é passada ao RunnableWithMessageHistory.
    """
    if session_id not in _session_store:
        _session_store[session_id] = InMemoryChatHistory()
    return _session_store[session_id]


# =============================================================================
# 3. CHAIN COM MEMÓRIA (LCEL + RunnableWithMessageHistory)
# =============================================================================

llm = QwenCustomLLM(
    base_url="http://10.10.1.2:9010",
    model_name="qwen2.5-coder:7b",
    timeout=60.0,
    response_key="response",
)

# ChatPromptTemplate com placeholder para o histórico de mensagens.
# O LangChain injeta automaticamente as mensagens anteriores no lugar de
# {history} antes de cada chamada ao LLM.
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Você é um assistente especialista em programação. "
        "Responda de forma clara e objetiva. "
        "Quando o usuário pedir alterações, use o contexto da conversa anterior.",
    ),
    MessagesPlaceholder(variable_name="history"),  # histórico injetado aqui
    ("human", "{task}"),                           # mensagem atual
])

# Chain base: prompt → LLM
base_chain = prompt | llm

# Chain com memória: gerencia o histórico automaticamente por session_id
chain_with_memory = RunnableWithMessageHistory(
    base_chain,
    get_session_history,
    input_messages_key="task",
    history_messages_key="history",
)


# =============================================================================
# 4. FASTAPI
# =============================================================================

app = FastAPI(
    title="Dev B — Orquestrador LangChain",
    description="Orquestrador com memória por sessão via RunnableWithMessageHistory.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="ID da sessão — isola o histórico por usuário.")
    task: str = Field(..., description="Mensagem atual do usuário.")


class ChatResponse(BaseModel):
    session_id: str
    code: str
    history_length: int = Field(description="Quantas mensagens existem no histórico desta sessão.")


@app.get("/health", summary="Healthcheck")
async def health():
    return {
        "status": "online",
        "mode": "langchain-memory",
        "active_sessions": len(_session_store),
    }


@app.post("/v1/chat", response_model=ChatResponse, summary="Chat com memória")
async def chat_endpoint(request: ChatRequest):
    """
    Recebe task + session_id.
    O LangChain recupera o histórico da sessão, monta o prompt completo
    (sistema + histórico + mensagem atual) e envia ao Dev A.
    """
    try:
        result: str = await chain_with_memory.ainvoke(
            {"task": request.task},
            config={"configurable": {"session_id": request.session_id}},
        )

        history = get_session_history(request.session_id)

        return ChatResponse(
            session_id=request.session_id,
            code=result,
            history_length=len(history.messages),
        )

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Dev A retornou erro HTTP {exc.response.status_code}: {exc.response.text}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Falha na conexão com Dev A: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/v1/chat/{session_id}", summary="Limpar histórico de uma sessão")
async def clear_session(session_id: str):
    """Apaga o histórico de uma sessão (útil para botão 'Nova conversa' no Dev C)."""
    if session_id in _session_store:
        _session_store[session_id].clear()
        return {"status": "cleared", "session_id": session_id}
    return {"status": "not_found", "session_id": session_id}


@app.get("/v1/chat/{session_id}/history", summary="Ver histórico de uma sessão")
async def get_history(session_id: str):
    """Retorna o histórico de mensagens de uma sessão para debug."""
    history = get_session_history(session_id)
    return {
        "session_id": session_id,
        "history_length": len(history.messages),
        "messages": [
            {"role": type(m).__name__, "content": m.content}
            for m in history.messages
        ],
    }


# =============================================================================
# 5. ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
