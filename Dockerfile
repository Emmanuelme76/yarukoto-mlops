FROM python:3.11-slim

WORKDIR /app

# Evitar archivos .pyc y habilitar logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código fuente del proyecto
COPY src/ ./src/
COPY api/ ./api/
COPY frontend/ ./frontend/
COPY dags/ ./dags/

# Crear directorios de trabajo y entrenar modelo base en el build
RUN mkdir -p data/raw data/processed models reports && \
    python src/generate_data.py && \
    python src/train.py && \
    python src/monitor.py

EXPOSE 8000

# Usar variable $PORT si la nube (Render/Railway) la asigna, o 8000 por defecto
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]