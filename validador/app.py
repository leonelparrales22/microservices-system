from flask import Flask, request, jsonify
import pika
import json
import threading
import time

app = Flask(__name__)

# Almacenar respuestas de microservicios
responses = {}
current_request_id = 0

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
            print("Successfully connected to RabbitMQ")
            return connection
        except Exception as e:
            print(f"Failed to connect to RabbitMQ (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise

def setup_rabbitmq_consumer():
    """Configurar consumidor para respuestas de microservicios"""
    def callback(ch, method, properties, body):
        try:
            print(f"Validador received raw message: {body}")
            
            # Verificar el content-type
            if properties.content_type != 'application/json':
                print(f"Invalid content type: {properties.content_type}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return
                
            data = json.loads(body)
            print(f"Parsed message: {data}")
            
            # Validar la estructura del mensaje
            if 'request_id' not in data or 'microservice_id' not in data or 'response' not in data:
                print(f"Invalid message structure: {data}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return
            
            request_id = data['request_id']
            microservice_id = data['microservice_id']
            response_data = data['response']
            
            print(f"Received response from microservice {microservice_id} for request {request_id}")
            
            # Almacenar respuesta
            if request_id not in responses:
                responses[request_id] = []
            
            responses[request_id].append({
                'microservice_id': microservice_id,
                'response': response_data
            })
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"Stored response for request {request_id}. Total responses: {len(responses[request_id])}")
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}, body: {body}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            print(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    # Reconexión en caso de fallo
    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            
            # Declarar exchange y cola para respuestas
            channel.exchange_declare(exchange='responses', exchange_type='direct', durable=True)
            channel.queue_declare(queue='validador_responses', durable=True)
            channel.queue_bind(exchange='responses', queue='validador_responses', routing_key='validador')
            
            channel.basic_consume(queue='validador_responses', on_message_callback=callback)
            
            print('Waiting for responses from microservices...')
            channel.start_consuming()
        except Exception as e:
            print(f"RabbitMQ connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

@app.route('/process', methods=['POST'])
def process_request():
    """Endpoint para procesar solicitudes"""
    global current_request_id
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Generar ID único para esta solicitud
        current_request_id += 1
        request_id = current_request_id
        
        # Determinar a qué microservicios enviar (lógica de validación)
        target_microservices = determine_target_microservices(data)
        
        # Enviar solicitud a RabbitMQ
        send_to_rabbitmq(request_id, target_microservices, data)
        
        # Esperar respuestas con timeout
        max_wait_time = 10  # 10 segundos máximo de espera
        wait_interval = 0.5  # verificar cada 0.5 segundos
        waited_time = 0
        
        while waited_time < max_wait_time and len(responses.get(request_id, [])) < len(target_microservices):
            time.sleep(wait_interval)
            waited_time += wait_interval
        
        # Recuperar respuestas
        request_responses = responses.get(request_id, [])
        
        # Limpiar respuestas procesadas
        if request_id in responses:
            del responses[request_id]
        
        return jsonify({
            'request_id': request_id,
            'target_microservices': target_microservices,
            'responses': request_responses,
            'wait_time': f'{waited_time}s'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para health checks"""
    return jsonify({
        'status': 'healthy',
        'service': 'validador',
        'timestamp': time.time()
    })

def determine_target_microservices(data):
    """Lógica simple para determinar a qué microservicios enviar la solicitud"""
    target_microservices = []
    
    # Si la solicitud contiene un campo 'product_id', enviar a todos los microservicios
    if 'product_id' in data:
        target_microservices = [1, 2, 3]
    # Si contiene 'category', enviar solo a los microservicios 1 y 2
    elif 'category' in data:
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
        channel.exchange_declare(exchange='requests', exchange_type='direct', durable=True)
        
        # Enviar mensaje a cada microservicio objetivo
        for microservice_id in target_microservices:
            message = {
                'request_id': request_id,
                'data': data,
                'response_routing_key': 'validador'
            }
            
            channel.basic_publish(
                exchange='requests',
                routing_key=f'microservice_{microservice_id}',
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Hacer el mensaje persistente
                    content_type='application/json'
                )
            )
            
            print(f"Sent request {request_id} to microservice {microservice_id}")
        
        connection.close()
        
    except Exception as e:
        print(f"Error sending to RabbitMQ: {e}")
        raise

if __name__ == '__main__':
    # Iniciar consumidor de RabbitMQ en un hilo separado
    rabbitmq_thread = threading.Thread(target=setup_rabbitmq_consumer, daemon=True)
    rabbitmq_thread.start()
    
    # Iniciar servidor Flask
    app.run(host='0.0.0.0', port=5000, debug=True)