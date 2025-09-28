import os
import json
import pika
import time
from flask import Flask, request, jsonify
import random
import requests

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Product, Order

# Conexión a SQLite (archivo dentro del contenedor)
DATABASE_URL = os.getenv("DB_URL", "sqlite:///./pedidos.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = Flask(__name__)

# Obtener número de instancia
instance_number = os.getenv("INSTANCE_NUMBER", "1")

# Leer configuración para override_quantity
import pathlib

config_path = pathlib.Path(__file__).parent / "pedidos_config.json"
try:
    with open(config_path, "r") as f:
        config = json.load(f)
    override_quantity = config.get("override_quantity", False)
except Exception as e:
    print(f"[PEDIDOS {instance_number}] [CONFIG] Error loading config: {e}")
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
            print(f"[PEDIDOS {instance_number}] [RECEIVED] Raw message: {body}")
            print(
                f"[PEDIDOS {instance_number}] [PROPERTIES] Content-Type: {getattr(properties, 'content_type', None)} Headers: {getattr(properties, 'headers', None)}"
            )
            data = json.loads(body)
            request_id = data.get("request_id")
            request_data = data.get("data")
            response_routing_key = data.get("response_routing_key")
            print(
                f"[PEDIDOS {instance_number}] [PROCESSING] Request ID: {request_id}, Data: {request_data}, Routing Key: {response_routing_key}"
            )
            # Simular procesamiento
            processing_time = 1  # 1 segundo de procesamiento simulado
            time.sleep(processing_time)
            # Leer config en cada ciclo para asegurar que cada instancia la lea correctamente
            import pathlib

            config_path = pathlib.Path(__file__).parent / "pedidos_config.json"
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                override_quantity = config.get("override_quantity", False)
            except Exception as e:
                print(f"[PEDIDOS {instance_number}] [CONFIG] Error loading config: {e}")
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

            print(f"[PEDIDOS {instance_number}] [OVERRIDE] {override_quantity}")

            # Insertar orden en BD
            new_order = Order(
                order_id=request_id,
                product_id=product_id,
                quantity_ordered=quantity,
                status="processed",
            )
            db.add(new_order)
            db.commit()
            db.close()

            response = {
                "microservice_id": int(instance_number),
                "request_id": request_id,
                "status": "processed",
                "processing_time": processing_time,
                "data": {
                    "order_id": f"ORD-{request_id}-{instance_number}",
                    "customer_id": f"CUST-{random.randint(1000, 9999)}",
                    "product_id": product_id,
                    "order_status": "confirmed" if in_stock else "pending",
                    "total_items": quantity,
                    "order_date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    "estimated_delivery": time.strftime(
                        "%Y-%m-%d", time.localtime(time.time() + 86400)
                    ),  # +1 día
                    "instance": instance_number,
                    "timestamp": time.time(),
                },
            }
            print(f"[PEDIDOS {instance_number}] [RESPONSE] Ready to send: {response}")
            # Enviar respuesta
            send_response(response_routing_key, response)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(
                f"[PEDIDOS {instance_number}] [COMPLETE] Request {request_id} processed and acknowledged."
            )
        except json.JSONDecodeError as e:
            print(
                f"[PEDIDOS {instance_number}] [ERROR] JSON decode error: {e} | Body: {body}"
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            print(
                f"[PEDIDOS {instance_number}] [ERROR] Exception processing request: {e}"
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
            f"[PEDIDOS {instance_number}] [SEND_RESPONSE] Connecting to RabbitMQ to send response..."
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
            f"[PEDIDOS {instance_number}] [SEND_RESPONSE] Publishing to exchange 'responses' with routing_key '{routing_key}': {message}"
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
            f"[PEDIDOS {instance_number}] [SEND_RESPONSE] Response sent and connection closed."
        )
        connection.close()
    except Exception as e:
        print(f"[PEDIDOS {instance_number}] [ERROR] Error sending response: {e}")


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
            "service": "pedidos",
            "timestamp": time.time(),
        }

    @app.route("/orders")
    def get_orders():
        db = SessionLocal()
        try:
            orders = db.query(Order).all()
            orders_list = [
                {
                    "id": order.id,
                    "order_id": order.order_id,
                    "product_id": order.product_id,
                    "quantity_ordered": order.quantity_ordered,
                    "status": order.status,
                    "timestamp": (
                        order.timestamp.isoformat() if order.timestamp else None
                    ),
                }
                for order in orders
            ]
            return {"orders": orders_list}
        finally:
            db.close()

    @app.route("/create_order", methods=["POST"])
    def create_order():
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token missing"}), 401

        # Validar JWT con autorizador
        try:
            response = requests.post(
                "http://autorizador:5005/validate", headers={"Authorization": token}
            )
            if response.status_code != 200:
                return jsonify({"error": "Invalid token"}), 401
            user_data = response.json()
        except:
            return jsonify({"error": "Authorization service unavailable"}), 500

        data = request.get_json()
        product_id = data.get("product_id")
        quantity = data.get("quantity", 50)

        # Crear pedido en BD
        db = SessionLocal()
        try:
            new_order = Order(
                order_id=f"{user_data['username']}-{int(time.time())}",
                product_id=product_id,
                quantity_ordered=quantity,
                status="confirmed",
            )
            db.add(new_order)
            db.commit()

            # Solicitar certificado
            cert_response = requests.post(
                "http://certificador:5006/certificate",
                json={"order_id": new_order.order_id, "user": user_data["username"]},
            )
            certificate = (
                cert_response.json() if cert_response.status_code == 200 else None
            )

            return (
                jsonify(
                    {
                        "message": "Order created",
                        "order_id": new_order.order_id,
                        "certificate": certificate,
                    }
                ),
                201,
            )
        finally:
            db.close()

    @app.route("/history", methods=["GET"])
    def history():
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Token missing"}), 401

        # Validar JWT con autorizador
        try:
            response = requests.post(
                "http://autorizador:5005/validate", headers={"Authorization": token}
            )
            if response.status_code != 200:
                return jsonify({"error": "Invalid token"}), 401
            user_data = response.json()
        except:
            return jsonify({"error": "Authorization service unavailable"}), 500

        # Consultar historial en todas las instancias
        all_orders = []
        for i in range(1, 4):
            try:
                response = requests.get(f"http://pedidos{i}:{5000+i}/orders")
                if response.status_code == 200:
                    instance_orders = response.json().get("orders", [])
                    user_orders = [
                        o
                        for o in instance_orders
                        if o["order_id"].startswith(f"{user_data['username']}-")
                    ]
                    all_orders.extend(user_orders)
            except:
                pass  # Si una instancia no responde, continuar con las demás

        # Remover duplicados si los hay (por order_id)
        seen = set()
        unique_orders = []
        for order in all_orders:
            if order["order_id"] not in seen:
                seen.add(order["order_id"])
                unique_orders.append(order)

        # Solicitar certificado
        cert_response = requests.post(
            "http://certificador:5006/certificate",
            json={"user": user_data["username"], "action": "history"},
        )
        certificate = cert_response.json() if cert_response.status_code == 200 else None

        return jsonify({"orders": unique_orders, "certificate": certificate}), 200

    port = 5000 + int(instance_number)
    app.run(host="0.0.0.0", port=port, debug=False)
