# Infraestrutura Local para IA com FastAPI
Infraestrutura para rodar e servir modelos de IA localmente utilizando FastAPI. O projeto inclui configurações para executar modelos de aprendizado de máquina acelerados por GPU, disponibilizando APIs REST para interações com os modelos. O foco é oferecer um ambiente escalável e eficiente para rodar modelos de IA.
## Tecnologias Utilizadas
 - FastAPI para criação de APIs REST rápidas.
 - Python 3.x para a implementação do backend.
 - Transformers e PyTorch para manipulação e execução de modelos de IA.
 - GPU para aceleração de modelos de aprendizado de máquina.
 - Docker (opcional) para containerização do ambiente de desenvolvimento.
# Modelos Locais + Ollama (AI Gateway) — Benchmark e Observabilidade

Este repositório contém um **gateway FastAPI** para acesso a modelos locais via **Ollama** e um processo padronizado para **benchmark** e **monitoramento de recursos** (GPU/VRAM + container).

---

## Visão Geral

- **Ollama** roda em **Docker** (container `ai_ollama`)
- **Gateway FastAPI** expõe endpoints simples:
  - `GET /health` — status do gateway e URL base do Ollama
  - `GET /models` — lista tags/modelos disponíveis no Ollama
  - `POST /generate` — gera resposta via Ollama

---

## Estrutura do Projeto
├── api/
│ └── main.py
├── compose/
│ └── docker-compose.ollama.yml
├── logs/
│ ├── bench/
│ ├── runtime/
│ └── traces/
└── README.md

> Observação: a pasta `logs/` é **local** e está no `.gitignore` (não deve ser versionada).

---

## Stack e Execução

### Ollama (Docker)
- Porta exposta localmente: `127.0.0.1:11434`
- Volume persistente: `ollama_data:/root/.ollama`

Subir o Ollama:
```bash
docker compose -f compose/docker-compose.ollama.yml up -d
```
Ver logs do container:
```bash
docker logs -f --tail 200 ai_ollama
```
