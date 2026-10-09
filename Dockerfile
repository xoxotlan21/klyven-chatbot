# Dockerfile de Producción para TravelSales.ai / Klyven AI Agent
FROM python:3.11-slim

# Evitar generación de bytecode y habilitar buffer de salida
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código del proyecto
COPY . .

# Exponer los puertos:
# 8000 = API Gateway, Webhooks de WhatsApp, Stripe y Widget JS
# 8501 = Dashboard SaaS en Streamlit
EXPOSE 8000
EXPOSE 8501

# Script de arranque unificado
CMD ["sh", "-c", "python server.py & streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true"]

