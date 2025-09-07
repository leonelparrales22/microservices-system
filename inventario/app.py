import os
import json
import pika
import time
from flask import Flask
import random

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Product

# Conexión a SQLite (archivo dentro del contenedor)
DATABASE_URL = os.getenv("DB_URL", "sqlite:///./inventario.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = Flask(__name__)

# Obtener número de instancia
instance_number = os.getenv("INSTANCE_NUMBER", "1")

# Leer configuración para override_quantity
import pathlib

config_path = pathlib.Path(__file__).parent / "inventario_config.json"
try:
    with open(config_path, "r") as f:
        config = json.load(f)
    override_quantity = config.get("override_quantity", False)
except Exception as e:
    print(f"[INVENTARIO {instance_number}] [CONFIG] Error loading config: {e}")
    override_quantity = False


def get_rabbitmq_connection():
    """Obtener conexión a RabbitMQ con reintentos"""
    max_retries = 5
    retry_delay = 3  # segundos

    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host="rabbitmq", connection_attempts=5, retry_delay=3
                )
            )
            print(f"Microservice {instance_number} connected to RabbitMQ")
            return connection
        except Exception as e:
            print(
                f"Microservice {instance_number} failed to connect to RabbitMQ (attempt {attempt+1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise


def process_requests():
    """Procesar solicitudes de RabbitMQ"""

    def callback(ch, method, properties, body):
        try:
            print(f"[INVENTARIO {instance_number}] [RECEIVED] Raw message: {body}")
            print(
                f"[INVENTARIO {instance_number}] [PROPERTIES] Content-Type: {getattr(properties, 'content_type', None)} Headers: {getattr(properties, 'headers', None)}"
            )
            data = json.loads(body)
            request_id = data.get("request_id")
            request_data = data.get("data")
            response_routing_key = data.get("response_routing_key")
            print(
                f"[INVENTARIO {instance_number}] [PROCESSING] Request ID: {request_id}, Data: {request_data}, Routing Key: {response_routing_key}"
            )
            # Simular procesamiento
            processing_time = 1  # 1 segundo de procesamiento simulado
            time.sleep(processing_time)
            # Leer config en cada ciclo para asegurar que cada instancia la lea correctamente
            import pathlib

            config_path = pathlib.Path(__file__).parent / "inventario_config.json"
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                override_quantity = config.get("override_quantity", False)
            except Exception as e:
                print(
                    f"[INVENTARIO {instance_number}] [CONFIG] Error loading config: {e}"
                )
                override_quantity = False

            # quantity = 100
            # Abrir sesión de DB
            db = SessionLocal()

            product_id = request_data.get("product_id", "unknown")
            product = db.query(Product).filter_by(product_id=product_id).first()

            if product:
                # Producto encontrado en BD
                quantity = product.quantity
                in_stock = product.in_stock
            else:
                # Si no existe, puedes decidir retornarlo con stock=0
                quantity = 0
                in_stock = False

                db.close()

            # Determinar override_quantity por probabilidad (70% false, 30% true)
            override_quantity = random.random() < 0.3     

            try:
                inst_num = int(instance_number)
            except Exception:
                inst_num = instance_number
            if override_quantity and inst_num == 2:
                quantity = 500
            elif override_quantity and inst_num == 3:
                quantity = 300

            print(
                f"[INVENTARIO {instance_number}] [OVERRIDE] {override_quantity}"
            )

            response = {
                "microservice_id": int(instance_number),
                "request_id": request_id,
                "status": "processed",
                "processing_time": processing_time,
                "data": {
                    "product_id": product_id,
                    "in_stock": in_stock,
                    "quantity": quantity,
                    "instance": instance_number,
                    "timestamp": time.time(),
                },
            }
            print(
                f"[INVENTARIO {instance_number}] [RESPONSE] Ready to send: {response}"
            )
            # Enviar respuesta
            send_response(response_routing_key, response)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(
                f"[INVENTARIO {instance_number}] [COMPLETE] Request {request_id} processed and acknowledged."
            )
        except json.JSONDecodeError as e:
            print(
                f"[INVENTARIO {instance_number}] [ERROR] JSON decode error: {e} | Body: {body}"
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            print(
                f"[INVENTARIO {instance_number}] [ERROR] Exception processing request: {e}"
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    # Reconexión en caso de fallo
    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()

            # Declarar exchange para solicitudes
            channel.exchange_declare(
                exchange="requests", exchange_type="direct", durable=True
            )

            # Declarar cola para este microservicio
            queue_name = f"microservice_{instance_number}_queue"
            channel.queue_declare(queue=queue_name, durable=True)
            channel.queue_bind(
                exchange="requests",
                queue=queue_name,
                routing_key=f"microservice_{instance_number}",
            )

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue_name, on_message_callback=callback)

            print(f"Microservice {instance_number} waiting for requests...")
            channel.start_consuming()
        except Exception as e:
            print(f"RabbitMQ connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)


def send_response(routing_key, response_data):
    """Enviar respuesta a través de RabbitMQ"""
    try:
        print(
            f"[INVENTARIO {instance_number}] [SEND_RESPONSE] Connecting to RabbitMQ to send response..."
        )
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        # Declarar exchange para respuestas (asegurarse de que existe)
        channel.exchange_declare(
            exchange="responses", exchange_type="direct", durable=True
        )
        # Crear el mensaje con la estructura correcta que espera el validador
        message = {
            "request_id": response_data["request_id"],
            "microservice_id": response_data["microservice_id"],
            "response": response_data,  # Enviar todo el objeto de respuesta
        }
        print(
            f"[INVENTARIO {instance_number}] [SEND_RESPONSE] Publishing to exchange 'responses' with routing_key '{routing_key}': {message}"
        )
        channel.basic_publish(
            exchange="responses",
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2, content_type="application/json"  # Mensaje persistente
            ),
        )
        print(
            f"[INVENTARIO {instance_number}] [SEND_RESPONSE] Response sent and connection closed."
        )
        connection.close()
    except Exception as e:
        print(f"[INVENTARIO {instance_number}] [ERROR] Error sending response: {e}")


if __name__ == "__main__":
    # Iniciar consumidor de RabbitMQ en un hilo separado
    import threading

    rabbitmq_thread = threading.Thread(target=process_requests, daemon=True)
    rabbitmq_thread.start()

    # Iniciar servidor Flask (para health checks)
    @app.route("/health")
    def health():
        return {
            "status": "healthy",
            "instance": instance_number,
            "service": "inventario",
            "timestamp": time.time(),
        }

    port = 5000 + int(instance_number)
    app.run(host="0.0.0.0", port=port, debug=False)
