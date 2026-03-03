# AI Orchestrator API

Esta API atua como a camada de inteligência e orquestração do projeto, gerenciando a comunicação entre a interface do usuário e os modelos de linguagem (LLMs) hospedados em servidores de inferência.

---

## Principais Funcionalidades

### Gestão de Sessões Persistente

Histórico de chat salvo em disco (`sessions_db.json`), garantindo que a memória da conversa sobreviva a reinicializações do servidor.

### Janela de Contexto Inteligente

Otimização de prompt que envia apenas as últimas interações relevantes para o modelo, evitando estouro de memória e latência excessiva.

### Segurança e Validação

Implementação de validações via Pydantic para impedir tarefas vazias ou prompts que excedam 2000 caracteres.

### Arquitetura em Containers

Totalmente configurado para Docker, facilitando o deploy e a escalabilidade.

---

## Estrutura do Repositório

```bash
.
├── main.py              # Núcleo da API FastAPI com lógica de gerenciamento de histórico
├── Dockerfile           # Configuração da imagem Docker (Python 3.11-slim)
├── requirements.txt     # Lista de dependências (FastAPI, Httpx, Pydantic, Uvicorn)
├── sessions_db.json     # Arquivo de persistência de dados (gerado automaticamente)
└── .gitignore           # Filtro para não subir arquivos temporários e ambientes virtuais
```

---

## Como Executar

### 1. Utilizando Docker (Recomendado)

Certifique-se de estar na raiz do projeto (`~/projeto-ia`):

```bash
# Construir a imagem
docker build -t orchestrator-ai:v2 .

# Rodar o container com volume para persistência
docker run -d \
  --name orchestrator_api \
  -p 8000:8000 \
  -v $(pwd)/sessions_db.json:/app/sessions_db.json \
  orchestrator-ai:v2
```

---

### 2. Instalação Manual (Desenvolvimento)

```bash
# Ativar ambiente virtual
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Iniciar servidor
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Documentação da API

### POST /v1/chat

Endpoint principal para interação com a IA.

### Exemplo de Payload

```json
{
  "session_id": "gabriel_dev",
  "task": "Crie uma função de soma em Python",
  "language": "python"
}
```
