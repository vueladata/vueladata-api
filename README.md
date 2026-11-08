# VuelaData - Módulo F7: API de Compensaciones y Pagos

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.143+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.1+-red.svg?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![uv](https://img.shields.io/badge/Package_Manager-uv-blueviolet.svg)](https://github.com/astral-sh/uv)
[![Tests](<https://img.shields.io/badge/Tests-88%20Passed-brightgreen.svg>)]()

Servicio web operacional REST perteneciente a la plataforma de datos de la aerolínea regional **VuelaData**. Este microservicio corresponde a la **Fuente F7**, encargada de la simulación de la pasarela de pagos asíncrona, el registro de incidencias y la gestión de compensaciones económicas a pasajeros.

El mismo repositorio contiene además los procesos en segundo plano de la plataforma, que comparten la imagen Docker de la API: **`worker_rds`** (consume eventos de RabbitMQ y los guarda en PostgreSQL/RDS), **`worker_lake`** (guarda los mensajes crudos en el Data Lake S3 Bronze), **`worker_notificaciones`** (envía los correos a los pasajeros) y el simulador de eventos **`simulate_stream.py`**.

---

## 📋 Historias de Usuario Cubiertas

* **HU-04 – Configurar la Base del Backend Operativo y ORM:** Estructura modular con FastAPI, persistencia con SQLAlchemy 2.0 y driver `psycopg` contra el esquema `vueladata`. Modelado tipado con Pydantic.
* **HU-05 – Implementar Endpoints CRUD y Documentación:** Operaciones CRUD completas para causas, reglas de compensación, compensaciones, pagos y eventos de pago. Documentación autogenerada OpenAPI/Swagger.
* **HU-20 – Containerize Applications with Optimized Dockerfiles:** Imagen Docker optimizada (`python:3.12-slim`). Orquestación con `docker-compose.yml` (centralizada en el repositorio **`vueladata-orchestration`**). Ejecución segura bajo usuario `appuser`.
* **HU-25 – Consumo confiable de mensajes (worker_rds):** Implementación de ACK y NACK para reencolar o descartar mensajes según la tipología del error.

---

## ⚖️ Reglas de Negocio Implementadas

* **RN-02 (Hora local):** Los correos a pasajeros muestran la salida y llegada en hora local.
* **RN-03 (Causas Imputables):** Clasificación de causas entre responsabilidad directa de la aerolínea y causas no imputables (clima, control aéreo).
* **RN-04 (Condiciones Climáticas Adversas):** Evaluación de observaciones meteorológicas (viento, visibilidad, tormentas).
* **RN-05 (Escala de Compensaciones):** Escalas basadas en tiempos de demora imputables y alertas de cancelación.
* **RN-06 (Reubicación):** Asignación automática o manual de vuelos alternativos ante cancelaciones.
* **RN-07 (Conexiones en riesgo):** Evaluación de tiempos mínimos de conexión en el aeropuerto.
* **RN-09 (Pago Único e Idempotencia):** Reglas para prevenir cobros y eventos duplicados a través de `clave_idempotencia` y control por `id_externo_evento`.

---

## 🚀 Puesta en Marcha Rápida (con Docker Compose)

El entorno local completo (base de datos, RabbitMQ, servidor web y orquestación) se levanta utilizando el archivo `docker-compose.yml` provisto en el repositorio **`vueladata-orchestration`**. 

Desde dicho repositorio, ejecuta:

```bash
docker compose up -d --build
```

### Servicios expuestos:

| Servicio             | Contenedor           | Puerto Local | Descripción                      |
| -------------------- | -------------------- | :----------: | --------------------------------- |
| **API REST**         | `vueladata_f7_api`   |   `8000`   | Servidor FastAPI Uvicorn          |
| **PostgreSQL**       | `vueladata_pg_dev`   |   `5433`   | Motor de base de datos relacional |

* **Documentación interactiva (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Verificación de conexión a BD:** [http://localhost:8000/health/db](http://localhost:8000/health/db)

Para detener los servicios, utiliza `docker compose down`.

---

## 💻 Ejecución Local en Desarrollo (sin Docker)

### 1. Requisitos previos
* Python 3.12+ y `uv` (o `pip`).
* Base de datos PostgreSQL activa con el esquema `vueladata` (gestionada desde `vueladata-orchestration`).
* RabbitMQ activo (gestionado desde `vueladata-orchestration`).

### 2. Instalación de dependencias
```bash
uv sync
```

### 3. Configuración de Variables de Entorno
Crea tu archivo `.env` utilizando `.env.example`. Las configuraciones de conexión a RabbitMQ y PostgreSQL deben apuntar a `localhost` si los puertos están expuestos en tu máquina.

**Configuración de Colas (Workers vs Simulador):**
El simulador publica por defecto en `q_rds_writer` y `q_lake_writer`. Asegúrate de que las variables `QUEUE_RDS` y `QUEUE_LAKE` en tu `.env` correspondan exactamente a estos nombres para asegurar el consumo en modo de desarrollo local.

### 4. Iniciar el servidor
```bash
uv run fastapi dev app/main.py
```

---

## 🧪 Pruebas Automatizadas

Para ejecutar la suite de pruebas unitarias y de integración (asegúrate de que PostgreSQL con el esquema `vueladata` esté activo para las pruebas CRUD):

```bash
uv run pytest -v
```

Cobertura de pruebas:

* ✅ Contratos de documentación OpenAPI autogenerada expuestos.
* ✅ Ciclo de vida CRUD completo (Crear, Consultar, Actualizar y Eliminar).
* ✅ Respuestas de error esperadas (`404 Not Found` en identificadores inexistentes).
* ✅ Rechazo automático de tipos de datos incorrectos (`422 Unprocessable Entity`).
* ✅ Rechazo de registros duplicados por restricciones de unicidad (`400 Bad Request`).
* ✅ Validación estricta de esquemas antes de tocar la base de datos relacional.

---

## 📌 Endpoints Principales

| Recurso                  |  Método  | Endpoint                        | Descripción                             |       Códigos HTTP       |
| ------------------------ | :--------: | ------------------------------- | ---------------------------------------- | :-----------------------: |
| **Health**         |  `GET`  | `/health`                     | Estado del contenedor de la API          |          `200`          |
| **Health**         |  `GET`  | `/health/db`                  | Conectividad contra PostgreSQL           |     `200`, `503`     |
| **Pasajeros**      |  `GET`  | `/pasajeros/{id}`             | Perfil del pasajero autenticado (RF-06)  | `200`, `401`, `403`, `404` |
| **Pasajeros**      |  `GET`  | `/pasajeros/{id}/itinerarios` | Reservas, vuelos, conexiones y reubicaciones | `200`, `401`, `403`, `404` |
| **Pasajeros**      |  `GET`  | `/pasajeros/{id}/reservas`    | Alias de `/itinerarios`                  | `200`, `401`, `403`, `404` |
| **Pasajeros**      |  `GET`  | `/pasajeros/{id}/compensaciones` | Compensaciones, pagos y notificaciones propias | `200`, `401`, `403`, `404` |
| **Pasajeros**      |  `GET`  | `/reservas/{codigo}/estado`   | Estado consolidado de una reserva propia | `200`, `401`, `403`, `404` |
| **Causas**         |  `GET`  | `/causas/`                    | Listar catálogo de causas operacionales |          `200`          |
| **Causas**         |  `POST`  | `/causas/`                    | Registrar nueva causa (RN-03)            | `201`, `400`, `422` |
| **Causas**         |  `GET`  | `/causas/{id}`                | Consultar causa por identificador        |     `200`, `404`     |
| **Causas**         | `PATCH` | `/causas/{id}`                | Actualización parcial de causa          | `200`, `404`, `400` |
| **Causas**         | `DELETE` | `/causas/{id}`                | Eliminar causa                           |     `204`, `404`     |
| **Reglas**         |  `GET`  | `/reglas-compensacion/`       | Listar reglas y porcentajes (RN-05)      |          `200`          |
| **Reglas**         |  `POST`  | `/reglas-compensacion/`       | Crear nueva regla de compensación       |     `201`, `422`     |
| **Compensaciones** |  `GET`  | `/compensaciones/`            | Consultar compensaciones económicas     |          `200`          |
| **Compensaciones** |  `POST`  | `/compensaciones/`            | Generar compensación para un segmento   | `201`, `400`, `422` |
| **Pagos**          |  `GET`  | `/pagos/`                     | Listar solicitudes de desembolso F7      |          `200`          |
| **Pagos**          |  `POST`  | `/pagos/`                     | Iniciar pago con clave de idempotencia   | `201`, `400`, `404` |
| **Pagos**          |  `GET`  | `/pagos/idempotencia/{clave}` | Consultar pago por clave idempotente     |     `200`, `404`     |
| **Eventos Pago**   |  `POST`  | `/eventos-pago/`              | Webhook asíncrono de confirmación F7   | `201`, `400`, `404` |

---

## 📧 Notificaciones por Correo a Pasajeros (RabbitMQ + Gmail)

Cuando sucede una interrupción de vuelo, `worker_rds` procesa el evento y emite un mensaje mediante un exchange `topic`. Posteriormente, `worker_notificaciones` envía correos a los afectados utilizando Gmail SMTP.

| Routing key | Cuándo lo publica `worker_rds` | `notificacion.tipo` |
| --- | --- | --- |
| `vuelo.cancelado` | Llega un evento `CANCEL` | `INTERRUPCION` |
| `vuelo.retrasado` | Evento `OUT` con retraso ≥ 120 min | `INTERRUPCION` |
| `conexion.en_riesgo` | Retraso que vulnera el tiempo de conexión | `CONEXION_RIESGO` |
| `itinerario.cambiado` | Reubicación tras cancelación | `REUBICACION` |

### Configuración de SMTP (Gmail)
1. Habilita la verificación en dos pasos en Gmail.
2. Crea una contraseña de aplicación.
3. Actualiza tu `.env` con `SMTP_USUARIO`, `SMTP_CLAVE` y `EMAIL_DESTINO_PRUEBAS`.

**Importante sobre las Pruebas:** Mantén `EMAIL_DESTINO_PRUEBAS` configurado con el buzón de tu equipo para evitar bloqueos por envíos a direcciones generadas de forma ficticia (seed data).

### Ejecución de los procesos auxiliares:
```bash
uv run python -m worker_rds.main                
uv run python -m worker_lake.main               
uv run python -m worker_notificaciones.main     
uv run python simulate_stream.py                
```
