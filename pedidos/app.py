import os
import json
import pika
import time
from flask import Flask, request, jsonify, g
import random
import requests
import jwt
from functools import wraps

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Product, Order
import uuid
# ======================
# MÉTRICAS EN CSV
# ======================
import csv
import datetime

METRICS_FILE = "metrics_log.csv"
REQUEST_COUNTER = 0  # contador global incremental

def get_request_id():
    """Genera un request_id único si aún no existe en g"""
    if not hasattr(g, "request_id"):
        g.request_id = str(uuid.uuid4())  # UUID único
    return g.request_id

def log_metric(event_type, user=None, status="success", details=""):
    """Registrar métrica en CSV con request_id persistente"""
    file_exists = os.path.isfile(METRICS_FILE)
    with open(METRICS_FILE, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["request_id", "timestamp", "event_type", "user", "status", "details"])
        writer.writerow([
            get_request_id(),  # siempre el mismo para la request completa
            datetime.datetime.utcnow().isoformat(),
            event_type,
            user if user else "",
            status,
            details
        ])

# 🔐 Seguridad
SECRET_KEY = os.getenv("SECRET_KEY", "mysecretkey")
JWT_ALGORITHM = "HS256"

def jwt_required(f):
    """Decorator para validar token y exponer claims en flask.g"""

    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", None)
        if not auth:
            log_metric("jwt_validation", status="failed", details="missing_token")
            return jsonify({"error": "authorization required"}), 401
        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            log_metric("jwt_validation", status="failed", details="invalid_header")
            return jsonify({"error": "invalid authorization header"}), 401
        token = parts[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            g.current_user = payload.get("sub")
            g.current_org = payload.get("org")
            g.current_roles = payload.get("roles", [])
            log_metric("jwt_validation", user=g.current_user, status="success", details="token_valid")
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            log_metric("jwt_validation", status="failed", details="token_expired")
            return jsonify({"error": "token expired"}), 401
        except jwt.InvalidTokenError:
            log_metric("jwt_validation", status="failed", details="invalid_token")
            return jsonify({"error": "invalid token"}), 401

    return wrapper

# ======================
# BASE DE DATOS
# ======================
DATABASE_URL = os.getenv("DB_URL", "sqlite:///./pedidos.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = Flask(__name__)
instance_number = os.getenv("INSTANCE_NUMBER", "1")

# ======================
# CONFIG
# ======================
import pathlib
config_path = pathlib.Path(__file__).parent / "pedidos_config.json"
try:
    with open(config_path, "r") as f:
        config = json.load(f)
    override_quantity = config.get("override_quantity", False)
except Exception as e:
    print(f"[PEDIDOS {instance_number}] [CONFIG] Error loading config: {e}")
    override_quantity = False

# ======================
# RABBITMQ
# ======================
def get_rabbitmq_connection():
    max_retries = 5
    retry_delay = 3
    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host="rabbitmq", connection_attempts=5, retry_delay=3)
            )
            print(f"Microservice {instance_number} connected to RabbitMQ")
            return connection
        except Exception as e:
            print(f"Microservice {instance_number} failed to connect to RabbitMQ (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise

def process_requests():
    def callback(ch, method, properties, body):
        try:
            print(f"[PEDIDOS {instance_number}] [RECEIVED] Raw message: {body}")
            data = json.loads(body)
            request_id = data.get("request_id")
            request_data = data.get("data")
            response_routing_key = data.get("response_routing_key")

            time.sleep(1)  # simulación procesamiento

            db = SessionLocal()
            product_id = request_data.get("product_id", "unknown")
            product = db.query(Product).filter_by(product_id=product_id).first()

            if product:
                quantity = product.quantity
                in_stock = product.in_stock
            else:
                quantity = 0
                in_stock = False

            override_quantity = random.random() < 0.3
            try:
                inst_num = int(instance_number)
            except Exception:
                inst_num = instance_number
            if override_quantity and inst_num == 2:
                quantity = 500
            elif override_quantity and inst_num == 3:
                quantity = 300

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
                "processing_time": 1,
                "data": {
                    "order_id": f"ORD-{request_id}-{instance_number}",
                    "customer_id": f"CUST-{random.randint(1000, 9999)}",
                    "product_id": product_id,
                    "order_status": "confirmed" if in_stock else "pending",
                    "total_items": quantity,
                    "order_date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    "estimated_delivery": time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400)),
                    "instance": instance_number,
                    "timestamp": time.time(),
                },
            }
            send_response(response_routing_key, response)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"[PEDIDOS {instance_number}] [ERROR] {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            channel.exchange_declare(exchange="requests", exchange_type="direct", durable=True)
            queue_name = f"microservice_{instance_number}_queue"
            channel.queue_declare(queue=queue_name, durable=True)
            channel.queue_bind(exchange="requests", queue=queue_name, routing_key=f"microservice_{instance_number}")
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            channel.start_consuming()
        except Exception as e:
            print(f"RabbitMQ connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def send_response(routing_key, response_data):
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.exchange_declare(exchange="responses", exchange_type="direct", durable=True)
        message = {
            "request_id": response_data["request_id"],
            "microservice_id": response_data["microservice_id"],
            "response": response_data,
        }
        channel.basic_publish(
            exchange="responses",
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
        connection.close()
    except Exception as e:
        print(f"[PEDIDOS {instance_number}] [ERROR] Error sending response: {e}")

# ======================
# ENDPOINTS FLASK
# ======================
if __name__ == "__main__":
    import threading
    rabbitmq_thread = threading.Thread(target=process_requests, daemon=True)
    rabbitmq_thread.start()

    @app.route("/health")
    def health():
        return {"status": "healthy", "instance": instance_number, "service": "pedidos", "timestamp": time.time()}

    @app.route("/orders")
    def get_orders():
        db = SessionLocal()
        try:
            orders = db.query(Order).all()
            orders_list = [
                {"id": o.id, "order_id": o.order_id, "product_id": o.product_id,
                 "quantity_ordered": o.quantity_ordered, "status": o.status,
                 "timestamp": o.timestamp.isoformat() if o.timestamp else None}
                for o in orders
            ]
            return {"orders": orders_list}
        finally:
            db.close()

    @app.route("/create_order", methods=["POST"])
    @jwt_required
    def create_order():
        token = request.headers.get("Authorization")
        if not token:
            log_metric("authorization", status="failed", details="missing_token")
            return jsonify({"error": "Token missing"}), 401
        try:
            response = requests.post("http://autorizador:5005/validate", headers={"Authorization": token})
            if response.status_code != 200:
                log_metric("authorization", status="failed", details="invalid_token")
                return jsonify({"error": "Invalid token"}), 401
            user_data = response.json()
            log_metric("authorization", user=user_data["username"], status="success", details="access_granted")
        except:
            return jsonify({"error": "Authorization service unavailable"}), 500

        data = request.get_json()
        product_id = data.get("product_id")
        quantity = data.get("quantity", 50)

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

            cert_response = requests.post("http://certificador:5006/certificate",
                                          json={"order_id": new_order.order_id, "user": user_data["username"]})
            if cert_response.status_code == 200:
                certificate = cert_response.json()
                log_metric("order", user=user_data["username"], status="success", details="cert_ok")
            else:
                certificate = None
                log_metric("order", user=user_data["username"], status="failed", details="cert_request_failed")

            return jsonify({"message": "Order created", "order_id": new_order.order_id, "certificate": certificate}), 201
        finally:
            db.close()

    @app.route("/history", methods=["GET"])
    @jwt_required
    def history():
        token = request.headers.get("Authorization")
        if not token:
            log_metric("authorization", status="failed", details="missing_token")
            return jsonify({"error": "Token missing"}), 401
        try:
            response = requests.post("http://autorizador:5005/validate", headers={"Authorization": token})
            if response.status_code != 200:
                log_metric("authorization", status="failed", details="invalid_token")
                return jsonify({"error": "Invalid token"}), 401
            user_data = response.json()
            log_metric("authorization", user=user_data["username"], status="success", details="access_granted")
        except:
            return jsonify({"error": "Authorization service unavailable"}), 500

        all_orders = []
        for i in range(1, 4):
            try:
                resp = requests.get(f"http://pedidos{i}:{5000+i}/orders")
                if resp.status_code == 200:
                    instance_orders = resp.json().get("orders", [])
                    user_orders = [o for o in instance_orders if o["order_id"].startswith(f"{user_data['username']}-")]
                    all_orders.extend(user_orders)
            except:
                pass

        seen, unique_orders = set(), []
        for o in all_orders:
            if o["order_id"] not in seen:
                seen.add(o["order_id"])
                unique_orders.append(o)

        cert_response = requests.post("http://certificador:5006/certificate",
                                      json={"user": user_data["username"], "action": "history"})
        if cert_response.status_code == 200:
            certificate = cert_response.json()
            log_metric("history", user=user_data["username"], status="success", details="cert_ok")
        else:
            certificate = None
            log_metric("history", user=user_data["username"], status="failed", details="cert_request_failed")

        return jsonify({"orders": unique_orders, "certificate": certificate}), 200

    port = 5000 + int(instance_number)
    app.run(host="0.0.0.0", port=port, debug=False)
