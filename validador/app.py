from flask import Flask, request, jsonify
import pika
import json
import threading
import os
import time
import sys
import csv

sys.stdout.reconfigure(line_buffering=True)

app = Flask(__name__)

responses = {}
responses_lock = threading.Lock()
current_request_id = 0

# Para medir latencias por request
request_start_times = {}

METRICS_FILE = "metrics.csv"

if not os.path.exists(METRICS_FILE):
    with open(METRICS_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "event",
                "request_id",
                "status",
                "extra_info",
                "proc_id",
                "thread_id",
            ]
        )


def log_metric(event, request_id=None, status="", extra_info=""):
    proc_id = os.getpid()
    thread_id = threading.get_ident()
    with open(METRICS_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                time.time(),
                event,
                request_id or "-",
                status,
                extra_info,
                proc_id,
                thread_id,
            ]
        )


def get_rabbitmq_connection():
    max_retries = 5
    retry_delay = 3
    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host="rabbitmq", connection_attempts=5, retry_delay=3
                )
            )
            log_metric("rabbitmq_connect", status="success")
            return connection
        except Exception as e:
            log_metric(
                "rabbitmq_connect",
                status="failed",
                extra_info=f"attempt {attempt+1}/{max_retries}: {e}",
            )
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise


def setup_rabbitmq_consumer():
    def callback(ch, method, properties, body):
        try:
            data = json.loads(body)
            request_id = str(data["request_id"])
            microservice_id = data["microservice_id"]
            response_data = data["response"]

            with responses_lock:
                if request_id not in responses:
                    responses[request_id] = []
                responses[request_id].append(
                    {"microservice_id": microservice_id, "response": response_data}
                )

                # Latencia desde inicio del request hasta recepción
                start_time = request_start_times.get(request_id)
                latency = time.time() - start_time if start_time is not None else None

                log_metric(
                    "response_received",
                    request_id=request_id,
                    status="stored",
                    extra_info=(
                        f"from microservice {microservice_id}, total {len(responses[request_id])}, latency={latency:.3f}s"
                        if latency
                        else f"from microservice {microservice_id}, total {len(responses[request_id])}"
                    ),
                )

            ch.basic_ack(delivery_tag=method.delivery_tag)
        except json.JSONDecodeError as e:
            log_metric("response_error", status="json_decode_error", extra_info=str(e))
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            log_metric("response_error", status="processing_error", extra_info=str(e))
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
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
            log_metric("consumer_ready", status="waiting_for_responses")
            channel.start_consuming()
        except Exception as e:
            log_metric("consumer_error", status="connection_failed", extra_info=str(e))
            time.sleep(5)


@app.route("/process", methods=["POST"])
def process_request():
    global current_request_id

    try:
        data = request.get_json()
        if not data:
            log_metric(
                "process_request", status="failed", extra_info="No JSON data provided"
            )
            return jsonify({"error": "No JSON data provided"}), 400

        current_request_id += 1
        request_id = str(current_request_id)

        # Guardar inicio del request
        request_start_times[request_id] = time.time()
        log_metric("request_start", request_id=request_id, status="received")

        target_microservices = determine_target_microservices(data)
        send_to_rabbitmq(request_id, target_microservices, data)

        time.sleep(0.3)
        max_wait_time = 8
        wait_interval = 0.1
        start_time = time.time()

        log_metric(
            "process_request",
            request_id=request_id,
            status="waiting_responses",
            extra_info=f"expecting {len(target_microservices)}",
        )

        from collections import Counter

        def normalize_response(resp):
            r = resp["response"].copy()
            r.pop("microservice_id", None)
            r["data"] = r.get("data", {}).copy()
            r["data"].pop("instance", None)
            r["data"].pop("timestamp", None)
            return json.dumps(r, sort_keys=True)

        while time.time() - start_time < max_wait_time:
            with responses_lock:
                request_responses = responses.get(request_id, [])
                normalized = [normalize_response(r) for r in request_responses]
                counts = Counter(normalized)
                most_common = counts.most_common(1)
                if most_common and most_common[0][1] >= 2:
                    idx = normalized.index(most_common[0][0])
                    valid_response = request_responses[idx]
                    if request_id in responses:
                        del responses[request_id]
                    final_wait_time = time.time() - start_time

                    log_metric(
                        "process_response",
                        request_id=request_id,
                        status="valid_response",
                        extra_info=json.dumps(valid_response["response"])[
                            :200
                        ],  # truncado por seguridad
                    )

                    log_metric(
                        "process_request",
                        request_id=request_id,
                        status="consensus",
                        extra_info=f"completed in {final_wait_time:.2f}s",
                    )
                    log_metric(
                        "latency_summary",
                        request_id=request_id,
                        status="success",
                        extra_info=f"responses={len(request_responses)}, total_time={final_wait_time:.2f}s",
                    )

                    return jsonify(
                        {
                            "request_id": request_id,
                            "response": valid_response["response"],
                            "wait_time": f"{final_wait_time:.2f}s",
                        }
                    )

                current_responses = len(request_responses)
                if current_responses >= len(target_microservices):
                    break
            time.sleep(wait_interval)
        # Si no hubo consenso, devolver error
        with responses_lock:
            request_responses = responses.get(request_id, [])
            if request_id in responses:
                del responses[request_id]
        final_wait_time = time.time() - start_time

        log_metric(
            "process_request",
            request_id=request_id,
            status="no_consensus",
            extra_info=f"waited {final_wait_time:.2f}s, responses={len(request_responses)}",
        )
        log_metric(
            "latency_summary",
            request_id=request_id,
            status="failed",
            extra_info=f"responses={len(request_responses)}, total_time={final_wait_time:.2f}s",
        )

        return (
            jsonify(
                {
                    "error": "No se obtuvo consenso entre los microservicios de inventario.",
                    "request_id": request_id,
                    "responses": request_responses,
                    "wait_time": f"{final_wait_time:.2f}s",
                }
            ),
            500,
        )

    except Exception as e:
        log_metric("process_request", status="error", extra_info=str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    log_metric("health_check", status="ok")
    return jsonify(
        {"status": "healthy", "service": "validador", "timestamp": time.time()}
    )


def determine_target_microservices(data):
    if "product_id" in data:
        return [1, 2, 3]
    elif "category" in data:
        return [1, 2]
    else:
        return [1]


def send_to_rabbitmq(request_id, target_microservices, data):
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.exchange_declare(
            exchange="requests", exchange_type="direct", durable=True
        )

        for microservice_id in target_microservices:
            send_time = time.time()
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
                    delivery_mode=2, content_type="application/json"
                ),
            )
            log_metric(
                "send_to_rabbitmq",
                request_id=request_id,
                status="sent",
                extra_info=f"to microservice {microservice_id}, send_time={send_time}",
            )

        log_metric(
            "send_batch_complete",
            request_id=request_id,
            status="done",
            extra_info=f"sent {len(target_microservices)} messages",
        )
        connection.close()
    except Exception as e:
        log_metric(
            "send_to_rabbitmq", request_id=request_id, status="error", extra_info=str(e)
        )
        raise


if __name__ == "__main__":
    rabbitmq_thread = threading.Thread(target=setup_rabbitmq_consumer, daemon=True)
    rabbitmq_thread.start()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
