from flask import Flask, request, jsonify
import pika
import json
import threading
import os
import time
import sys

sys.stdout.reconfigure(line_buffering=True)

app = Flask(__name__)

# Almacenar respuestas de microservicios
import threading

responses = {}
responses_lock = threading.Lock()
current_request_id = 0


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
            print("[VALIDADOR] Conectado a RabbitMQ")
            return connection
        except Exception as e:
            print(
                f"Failed to connect to RabbitMQ (attempt {attempt+1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise


def setup_rabbitmq_consumer():
    """Configurar consumidor para respuestas de microservicios"""

    def callback(ch, method, properties, body):
        try:
            print(f"[VALIDADOR] Mensaje recibido de RabbitMQ")
            data = json.loads(body)
            request_id = str(data["request_id"])
            microservice_id = data["microservice_id"]
            response_data = data["response"]
            print(
                f"[VALIDADOR] Respuesta recibida de microservicio {microservice_id} para request {request_id}"
            )
            with responses_lock:
                if request_id not in responses:
                    responses[request_id] = []
                responses[request_id].append(
                    {"microservice_id": microservice_id, "response": response_data}
                )
                print(
                    f"[VALIDADOR] Respuesta almacenada para request {request_id}. Total: {len(responses[request_id])}"
                )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except json.JSONDecodeError as e:
            print(f"[VALIDADOR] ERROR decodificando JSON: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            print(f"[VALIDADOR] ERROR procesando mensaje: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    # Reconexión en caso de fallo
    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()

            # Declarar exchange y cola para respuestas
            channel.exchange_declare(
                exchange="responses", exchange_type="direct", durable=True
            )
            channel.queue_declare(queue="validador_responses", durable=True)
            channel.queue_bind(
                exchange="responses",
                queue="validador_responses",
                routing_key="validador",
            )

            channel.basic_consume(
                queue="validador_responses", on_message_callback=callback
            )

            print("Waiting for responses from microservices...")
            channel.start_consuming()
        except Exception as e:
            print(f"RabbitMQ connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)


@app.route("/process", methods=["POST"])
def process_request():
    proc_id = os.getpid()
    thread_id = threading.get_ident()
    """Endpoint para procesar solicitudes"""
    global current_request_id

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        # Generar ID único para esta solicitud
        global current_request_id
        current_request_id += 1
        request_id = str(current_request_id)
        # Determinar a qué microservicios enviar
        target_microservices = determine_target_microservices(data)
        # Enviar solicitud a RabbitMQ
        send_to_rabbitmq(request_id, target_microservices, data)
        # ESPERAR PROPAGACIÓN DE MENSAJES
        time.sleep(0.3)  # 300ms para que RabbitMQ procese
        # Esperar respuestas con timeout mejorado
        max_wait_time = 8  # 8 segundos máximo
        wait_interval = 0.1  # verificar cada 100ms
        start_time = time.time()
        print(
            f"[VALIDADOR] Esperando {len(target_microservices)} respuestas para request {request_id}"
        )
        while time.time() - start_time < max_wait_time:
            with responses_lock:
                current_responses = len(responses.get(request_id, []))
            if current_responses >= len(target_microservices):
                break
            time.sleep(wait_interval)
        # Recuperar respuestas
        with responses_lock:
            request_responses = responses.get(request_id, [])
            # Limpiar respuestas procesadas
            if request_id in responses:
                del responses[request_id]
        final_wait_time = time.time() - start_time
        print(
            f"[VALIDADOR] Request {request_id} completado con {len(request_responses)} respuestas en {final_wait_time:.2f}s"
        )
        return jsonify(
            {
                "request_id": request_id,
                "target_microservices": target_microservices,
                "responses": request_responses,
                "wait_time": f"{final_wait_time:.2f}s",
            }
        )
    except Exception as e:
        print(f"[VALIDADOR] ERROR en process_request: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Endpoint para health checks"""
    return jsonify(
        {"status": "healthy", "service": "validador", "timestamp": time.time()}
    )


def determine_target_microservices(data):
    """Lógica simple para determinar a qué microservicios enviar la solicitud"""
    target_microservices = []

    # Si la solicitud contiene un campo 'product_id', enviar a todos los microservicios
    if "product_id" in data:
        target_microservices = [1, 2, 3]
    # Si contiene 'category', enviar solo a los microservicios 1 y 2
    elif "category" in data:
        target_microservices = [1, 2]
    # Por defecto, enviar solo al microservicio 1
    else:
        target_microservices = [1]

    return target_microservices


def send_to_rabbitmq(request_id, target_microservices, data):
    """Enviar solicitud a RabbitMQ para los microservicios objetivo"""
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()

        # Declarar exchange para solicitudes
        channel.exchange_declare(
            exchange="requests", exchange_type="direct", durable=True
        )

        # Enviar mensaje a cada microservicio objetivo
        for microservice_id in target_microservices:
            message = {
                "request_id": request_id,
                "data": data,
                "response_routing_key": "validador",
            }

            channel.basic_publish(
                exchange="requests",
                routing_key=f"microservice_{microservice_id}",
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Hacer el mensaje persistente
                    content_type="application/json",
                ),
            )
            print(
                f"[VALIDADOR] Solicitud enviada {request_id} a microservicio {microservice_id}"
            )

        connection.close()

    except Exception as e:
        print(f"Error sending to RabbitMQ: {e}")
        raise


if __name__ == "__main__":
    # Iniciar consumidor de RabbitMQ en un hilo separado
    rabbitmq_thread = threading.Thread(target=setup_rabbitmq_consumer, daemon=True)
    rabbitmq_thread.start()

    # Iniciar servidor Flask en modo producción (sin debug ni recarga automática)
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
