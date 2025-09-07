FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Copiar aplicación y configuración
COPY app.py .
COPY inventario_config.json .

# Copiar script de inicialización de la BD
COPY models.py .
COPY init_db.py .

# Ejecutar primero init_db.py y luego app.py
CMD ["sh", "-c", "python init_db.py && python app.py"]
