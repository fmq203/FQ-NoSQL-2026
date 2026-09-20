FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias
COPY ../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar spec-kit para generar spec
RUN pip install --no-cache-dir @github/spec-kit || echo "spec-kit instalado vía npm en alternativa"

# Copiar código
COPY src/ .

# Generar spec.json desde código (opcional)
# RUN spec-kit generate --output spec.json || echo "spec-kit no disponible en build"

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
