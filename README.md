# Sistema de Microservicios con RabbitMQ y Autenticación JWT

Este sistema implementa un ecosistema de microservicios para gestión de pedidos con autenticación JWT, validación distribuida y certificación de transacciones. Incluye un validador que distribuye solicitudes a múltiples microservicios de pedidos, un autorizador para manejo de usuarios y tokens, y un certificador para generar certificados de transacciones.

## Estructura del Proyecto

```text
microservices-system/
├── docker-compose.yml          # Orquestación de servicios
├── nginx.conf                  # Configuración del API Gateway
├── README.md                   # Documentación del proyecto
├── postman/                    # Colecciones de Postman exportadas
│   └── collections.json        # Ejemplos de requests
├── autorizador/                # Servicio de autenticación JWT
├── certificador/               # Servicio de certificación
├── pedidos/                    # Microservicios de pedidos (3 instancias)
├── validador/                  # Validador de consenso
└── rabbitmq/                   # Configuración de RabbitMQ
```

## Arquitectura

- **Validador**: Recibe solicitudes HTTP y las distribuye a los microservicios de pedidos para validación de consenso.
- **Pedidos (3 instancias)**: Procesan solicitudes de creación y consulta de pedidos, validan JWT y generan certificados.
- **Autorizador**: Maneja registro de usuarios, login y validación de tokens JWT.
- **Certificador**: Genera certificados digitales para transacciones y consultas.
- **RabbitMQ**: Servidor de mensajería que coordina la comunicación asíncrona.
- **Nginx**: API Gateway para enrutamiento de solicitudes entre cliente-servidor.

## Servicios y Puertos

- Validador: `http://localhost:5001`
- Pedidos1: `http://localhost:5002`
- Pedidos2: `http://localhost:5003`
- Pedidos3: `http://localhost:5004`
- Autorizador: `http://localhost:5005`
- Certificador: `http://localhost:5006`
- RabbitMQ Management: `http://localhost:15672` (usuario: guest, contraseña: guest)
- API Gateway: `http://localhost:8080`

## Instalación y Ejecución

1. Clona o descarga este repositorio
2. Ejecuta: `docker-compose up --build`
3. Accede a los servicios en los puertos indicados arriba

## Uso

### 1. Registro de Usuario

```bash
curl -X POST http://localhost:8080/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "testpass",
    "org": "orgA",
    "roles": ["client"]
  }'
```

**Campos del payload:**

- `username` (requerido): Nombre de usuario único
- `password` (requerido): Contraseña del usuario
- `org` (opcional): Organización del usuario (por defecto: "orgA")
- `roles` (opcional): Lista de roles (por defecto: ["client"])

### 2. Login para Obtener JWT

```bash
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass"}'
```

Respuesta: `{"token": "jwt_token_here"}`

### 3. Crear Pedido

```bash
curl -X POST http://localhost:8080/pedidos/create_order \
  -H "Authorization: Bearer jwt_token_here" \
  -H "Content-Type: application/json" \
  -d '{"product_id": "P001", "quantity": 100}'
```

### 4. Consultar Historial de Pedidos

```bash
curl -X GET http://localhost:8080/pedidos/history \
  -H "Authorization: Bearer jwt_token_here"
```

### 5. Consulta de Pedidos (Sistema Original)

```bash
curl -X POST http://localhost:8080/consulta-pedidos \
  -H "Content-Type: application/json" \
  -d '{"product_id": "P001"}'
```

## Endpoints Disponibles

### Autorizador (`/auth/`)

- `POST /auth/register`: Registrar nuevo usuario
- `POST /auth/login`: Obtener token JWT
- `POST /auth/validate`: Validar token (interno)

### Pedidos (`/pedidos/`)

- `POST /pedidos/create_order`: Crear nuevo pedido (requiere JWT)
- `GET /pedidos/history`: Consultar historial (requiere JWT)
- `GET /pedidos/orders`: Ver todos los pedidos (sin autenticación)

### Validador (`/consulta-pedidos`)

- `POST /consulta-pedidos`: Procesar consulta distribuida
- `GET /api-health`: Health check del validador

### Certificador (`/cert/`)

- `POST /cert/certificate`: Generar certificado (interno)

## Flujo de Trabajo

1. **Registro/Login**: Usuario se registra y obtiene JWT del Autorizador.
2. **Crear Pedido**: Cliente envía pedido con JWT → Pedidos valida token con Autorizador → Crea pedido en BD → Solicita certificado al Certificador → Devuelve confirmación + certificado.
3. **Consultar Historial**: Cliente solicita historial con JWT → Pedidos valida token → Consulta BD → Solicita certificado → Devuelve historial + certificado.

## Certificados

Los certificados son hashes SHA256 generados por el servicio Certificador para cada transacción, proporcionando una prueba digital de la operación realizada.

## Detener el Sistema

```bash
docker-compose down
```

## Notas Técnicas

- Las instancias de Pedidos almacenan pedidos en bases de datos SQLite individuales.
- La validación de consenso se realiza comparando respuestas de las 3 instancias de Pedidos.
- Los tokens JWT expiran en 1 hora.
- El sistema usa Docker Compose para orquestación de contenedores.
