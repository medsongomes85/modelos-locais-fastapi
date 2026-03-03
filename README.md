# Infraestrutura Local para IA com FastAPI
Infraestrutura para rodar e servir modelos de IA localmente utilizando FastAPI. O projeto inclui configurações para executar modelos de aprendizado de máquina acelerados por GPU, disponibilizando APIs REST para interações com os modelos. O foco é oferecer um ambiente escalável e eficiente para rodar modelos de IA.
## Tecnologias Utilizadas
 - FastAPI para criação de APIs REST rápidas.
 - Python 3.x para a implementação do backend.
 - Transformers e PyTorch para manipulação e execução de modelos de IA.
 - GPU para aceleração de modelos de aprendizado de máquina.
 - Docker (opcional) para containerização do ambiente de desenvolvimento.
# Ollama (AI Gateway) — Benchmark e Observabilidade

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
```
├── api/
│ └── main.py
├── compose/
│ └── docker-compose.ollama.yml
├── logs/
│ ├── bench/
│ ├── runtime/
│ └── traces/
└── README.md
```
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
## Gateway (FastAPI)

Crie e ative a venv (exemplo):
```bash
python -m venv .venv-gateway
source .venv-gateway/bin/activate
pip install -U pip
pip install fastapi uvicorn requests
```

Executar o gateway (exemplo porta 9010):
```bash
uvicorn api.main:app --host 0.0.0.0 --port 9010
```
## Benchmark e Observabilidade
### Objetivo

Medir:
- Desempenho do modelo (tokens/s e tempos via resposta do Ollama)
- Uso de GPU/VRAM (via nvidia-smi)
- Uso de CPU/RAM/IO do container (via docker stats)

### Run padrão (gera logs em logs/bench/<run_id>/)
Dentro do projeto:
```bash
cd ~/projetos/modelos-locais-fastapi

RUN_ID=$(date +%F_%H%M%S)
RUN_DIR="logs/bench/$RUN_ID"
mkdir -p "$RUN_DIR"

# 1) GPU logger (200 ms por 30s)
timeout 30s nvidia-smi \
  --query-gpu=timestamp,utilization.gpu,utilization.memory,memory.used,power.draw,temperature.gpu \
  --format=csv -lms 200 > "$RUN_DIR/gpu.csv" &

# 2) Container logger (500 ms por ~30s)
timeout 30s bash -c '
  while true; do
    echo -n "$(date -Is),"
    docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}}" ai_ollama
    sleep 0.5
  done
' > "$RUN_DIR/docker.csv" &

# 3) Requisição (salva métricas do Ollama)
curl -s http://127.0.0.1:11434/api/generate -d '{
  "model":"mistral-nemo:latest",
  "prompt":"Explique PCM e dê 10 exemplos de uso. Seja detalhado.",
  "stream": false,
  "options": { "num_predict": 512, "temperature": 0 }
}' > "$RUN_DIR/resp.json"

echo "Saved logs in: $RUN_DIR"
ls -la "$RUN_DIR"
```
Arquivos gerados:
- gpu.csv — uso de GPU/VRAM/Power/Temp
- docker.csv — CPU/Mem/IO do container
- resp.json — resposta + métricas (durations e contagem de tokens)
