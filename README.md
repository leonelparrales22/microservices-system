# Sistema de Microservicios con RabbitMQ + To-Do List Application

Este sistema implementa un validador que distribuye solicitudes a múltiples microservicios de inventario usando Nginx como enrutador de peticiones y RabbitMQ como mensajería asíncrona. Además, incluye una aplicación de lista de tareas (To-Do List) moderna construida con React.

## Estructura

- **Validador**: Recibe solicitudes HTTP y las envía a los microservicios apropiados
- **Inventario (3 instancias)**: Procesan solicitudes y devuelven respuestas JSON
- **RabbitMQ**: Servidor de mensajería que coordina la comunicación
- **Nginx**: API Gateway para enrutamiento de solitudes entre cliente-servidor
- **Todo Frontend**: Aplicación React de lista de tareas con persistencia en localStorage

## Instalación y ejecución

1. Clona o descarga este repositorio
2. Ejecuta: `docker-compose up --build`
3. Accede a:
   - **To-Do List App**: http://localhost:8080 (Aplicación principal)
   - **To-Do List (directo)**: http://localhost:3000 (Acceso directo al frontend)
   - Validador: http://localhost:5001
   - RabbitMQ Management: http://localhost:15672 (usuario: guest, contraseña: guest)

## To-Do List Application

### Características

La aplicación de lista de tareas incluye las siguientes funcionalidades:

- ✅ **Agregar tareas**: Formulario intuitivo para añadir nuevas tareas
- ✏️ **Editar tareas**: Edición en línea con teclado shortcuts (Enter/Escape)
- 🗑️ **Eliminar tareas**: Botón de eliminación para cada tarea
- ☑️ **Marcar como completadas**: Checkbox para cambiar el estado de las tareas
- 📊 **Estadísticas**: Contador de tareas totales, pendientes y completadas
- 💾 **Persistencia**: Los datos se guardan automáticamente en localStorage
- 📱 **Responsive**: Diseño adaptable para móviles y escritorio
- 🧹 **Limpiar completadas**: Botón para eliminar todas las tareas completadas

### Tecnologías utilizadas

- **React 18**: Framework principal con hooks modernos
- **CSS3**: Estilos modernos con gradients y animaciones
- **localStorage**: Persistencia de datos en el navegador
- **Docker**: Containerización para deployment
- **Nginx**: Servidor web para servir la aplicación

### Estructura del código

```
todo-frontend/
├── src/
│   ├── components/
│   │   ├── AddTask.js          # Componente para agregar tareas
│   │   ├── AddTask.css         # Estilos del formulario
│   │   ├── TaskList.js         # Lista de tareas organizada
│   │   ├── TaskList.css        # Estilos de la lista
│   │   ├── TaskItem.js         # Componente individual de tarea
│   │   └── TaskItem.css        # Estilos de cada tarea
│   ├── App.js                  # Componente principal
│   └── App.css                 # Estilos globales
├── Dockerfile                  # Configuración Docker
├── nginx.conf                  # Configuración Nginx
└── package.json               # Dependencias del proyecto
```

## Uso de la API de Microservicios

Envía una solicitud POST al validador:

```bash
curl -X POST http://localhost:5001/process \
  -H "Content-Type: application/json" \
  -d '{"product_id": "12345", "action": "check_inventory"}'

# Health check del validador
curl -X GET http://localhost:5001/health
```

### Gateway (Nginx)

```bash
# API de inventario a través del gateway
curl -X POST http://localhost:8080/api/consulta-inventario \
  -H "Content-Type: application/json" \
  -d '{"product_id": "12345", "action": "check_inventory"}'

# Health check a través del gateway
curl -X GET http://localhost:8080/api/health
```

## Instrucciones de instalación:

1. **Descarga todos los archivos** en una carpeta llamada `microservices-system`

2. **Ejecuta el sistema:**
   ```bash
   cd microservices-system
   docker-compose up --build
   ```

3. **Accede a la aplicación:**
   - Abre tu navegador en http://localhost:8080 para usar la To-Do List
   - Las tareas se guardarán automáticamente en tu navegador

4. **Dar de baja:**
   ```bash
   docker-compose down
   ```

## Notas para desarrolladores

### Arquitectura modular

La aplicación To-Do está diseñada con una arquitectura modular que facilita la extensión:

- **Componentes reutilizables**: Cada parte de la UI es un componente independiente
- **Estado centralizado**: Gestión de estado en el componente principal App.js
- **Persistencia abstracta**: Fácil de cambiar de localStorage a una API
- **Estilos modulares**: CSS separado por componente para mejor mantenimiento

### Extensiones posibles

- Agregar fechas de vencimiento
- Categorías o etiquetas para tareas
- Sincronización con backend/API
- Búsqueda y filtrado avanzado
- Notificaciones push
- Modo oscuro/claro
- Exportar/importar tareas
