FROM python:3.11-slim

WORKDIR /app

# Removemos o apt-get update e build-essential que estão falhando
# Se algum pacote precisar de compilação, o pip avisará, 
# mas para LangChain e FastAPI o slim puro costuma bastar.

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
