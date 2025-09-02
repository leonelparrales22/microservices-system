import os
import json
import pika
import time
from flask import Flask

app = Flask(__name__)

# Obtener número de instancia
instance_number = os.getenv('INSTANCE_NUMBER', '1')

def get_rabbitmq_connection():
    """Obtener conexión a RabbitMQ con reintentos"""
    max_retries = 5
    retry_delay = 3  # segundos
    
    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host='rabbitmq',
                    connection_attempts=5,
                    retry_delay=3
                ))
            print(f"Microservice {instance_number} connected to RabbitMQ")
            return connection
        except Exception as e:
            print(f"Microservice {instance_number} failed to connect to RabbitMQ (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise

def process_requests():
    """Procesar solicitudes de RabbitMQ"""
    def callback(ch, method, properties, body):
        try:
            print(f"Microservice {instance_number} received message: {body}")
            data = json.loads(body)
            request_id = data.get('request_id')
            request_data = data.get('data')
            response_routing_key = data.get('response_routing_key')
            
            print(f"Microservice {instance_number} processing request {request_id}: {request_data}")
            
            # Simular procesamiento
            processing_time = 1  # 1 segundo de procesamiento simulado
            time.sleep(processing_time)
            
            # Generar respuesta (JSON simulado)
            response = {
                'microservice_id': int(instance_number),
                'request_id': request_id,
                'status': 'processed',
                'processing_time': processing_time,
                'data': {
                    'product_id': request_data.get('product_id', 'unknown'),
                    'in_stock': True,
                    'quantity': 100,
                    'instance': instance_number,
                    'timestamp': time.time()
                }
            }
            
            # Enviar respuesta
            send_response(response_routing_key, response)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"Microservice {instance_number} completed request {request_id}")
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            print(f"Error processing request: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    # Reconexión en caso de fallo
    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            
            # Declarar exchange para solicitudes
            channel.exchange_declare(exchange='requests', exchange_type='direct', durable=True)
            
            # Declarar cola para este microservicio
            queue_name = f'microservice_{instance_number}_queue'
            channel.queue_declare(queue=queue_name, durable=True)
            channel.queue_bind(exchange='requests', queue=queue_name, 
                              routing_key=f'microservice_{instance_number}')
            
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            
            print(f'Microservice {instance_number} waiting for requests...')
            channel.start_consuming()
        except Exception as e:
            print(f"RabbitMQ connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def send_response(routing_key, response_data):
    """Enviar respuesta a través de RabbitMQ"""
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        
        # Declarar exchange para respuestas (asegurarse de que existe)
        channel.exchange_declare(exchange='responses', exchange_type='direct', durable=True)
        
        # Crear el mensaje con la estructura correcta que espera el validador
        message = {
            'request_id': response_data['request_id'],
            'microservice_id': response_data['microservice_id'],
            'response': response_data  # Enviar todo el objeto de respuesta
        }
        
        channel.basic_publish(
            exchange='responses',
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Mensaje persistente
                content_type='application/json'
            )
        )
        
        print(f"Microservice {instance_number} sent response to {routing_key}: {message}")
        connection.close()
        
    except Exception as e:
        print(f"Error sending response: {e}")

if __name__ == '__main__':
    # Iniciar consumidor de RabbitMQ en un hilo separado
    import threading
    rabbitmq_thread = threading.Thread(target=process_requests, daemon=True)
    rabbitmq_thread.start()
    
    # Iniciar servidor Flask (para health checks)
    @app.route('/health')
    def health():
        return {
            'status': 'healthy', 
            'instance': instance_number,
            'service': 'inventario',
            'timestamp': time.time()
        }
    
    app.run(host='0.0.0.0', port=5000, debug=False)