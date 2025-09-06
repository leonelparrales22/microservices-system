FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt


COPY app.py .
COPY inventario_config.json .

CMD ["python", "app.py"]