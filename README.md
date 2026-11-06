# VuelaData - Módulo F7: API de Compensaciones y Pagos

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.143+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![uv](https://img.shields.io/badge/Package_Manager-uv-blueviolet.svg)](https://github.com/astral-sh/uv)
[![Tests](<https://img.shields.io/badge/Tests-13%20Passed-brightgreen.svg>)]()

Servicio web operacional REST perteneciente a la plataforma de datos de la aerolínea regional **VuelaData**. Este microservicio corresponde a la **Fuente F7**, encargada de la simulación de la pasarela de pagos asíncrona, el registro de incidencias y el cálculo y gestión de compensaciones económicas a pasajeros afectados por retrasos o cancelaciones.

---

## 📋 Historias de Usuario Cubiertas

* **HU-04 – Configurar la Base del Backend Operativo y ORM:**
  * Estructura modular de backend con FastAPI.
  * Persistencia relacional con SQLAlchemy 2.0 y driver nativo `psycopg` contra el esquema `vueladata`.
  * Modelado tipado de las entidades operacionales y esquemas Pydantic con validación estricta de tipos y formatos.
* **HU-05 – Implementar Endpoints CRUD y Documentación de la API:**
  * Operaciones completas de Crear, Leer, Actualizar y Eliminar (CRUD).
  * Manejo estandarizado de errores HTTP (`200`, `201`, `204`, `400`, `404`, `422`).
  * Documentación autogenerada OpenAPI/Swagger con esquemas de solicitud/respuesta.
* **HU-20 – Containerize Applications with Optimized Dockerfiles:**
  * Imagen Docker optimizada multi-etapa basada en `python:3.12-slim` con `uv`.
  * Ejecución segura con usuario no root (`appuser`).
  * Healthcheck nativo consultando `/health`.
  * Orquestación con `docker-compose.yml` vinculando la API y PostgreSQL.

---

## ⚖️ Reglas de Negocio Implementadas

* **RN-03 (Causas Imputables):** Clasificación de causas entre responsabilidad directa de la aerolínea (`es_imputable = true`) y causas no imputables (clima, control aéreo, seguridad).
* **RN-05 (Escala de Compensaciones):** Parámetros y reglas regulatorias según tiempo de demora imputable:
  * 25% de la tarifa del segmento (retrasos entre 2 y 4 horas).
  * 50% de la tarifa del segmento (retrasos entre 4 y 6 horas).
  * 100% de la tarifa del segmento (retrasos > 6 horas o cancelaciones imputables con aviso < 72h).
* **RN-09 (Pago Único e Idempotencia):**
  * Un segmento de pasajero (`id_detalle_reserva`) puede recibir como máximo una compensación económica.
  * Una compensación puede tener como máximo un pago.
  * Las solicitudes de pago hacia la pasarela F7 exigen una `clave_idempotencia` única para prevenir cobros duplicados.

---

## 🏗️ Estructura del Proyecto

```text
api/
├── app/
│   ├── core/               # Configuración central y variables de entorno (.env)
│   │   └── config.py
│   ├── crud/               # Capa de acceso a datos (queries puras de SQLAlchemy)
│   │   ├── causa.py
│   │   ├── compensacion.py
│   │   ├── pago.py
│   │   ├── evento_pago.py
│   │   └── regla_compensacion.py
│   ├── models/             # Modelos ORM de SQLAlchemy 2.0 (esquema vueladata)
│   │   ├── causa.py
│   │   ├── compensacion.py
│   │   ├── pago.py
│   │   └── ... (31 modelos mapeados)
│   ├── routers/            # Controladores de endpoints REST y códigos HTTP
│   │   ├── causa.py
│   │   ├── compensacion.py
│   │   ├── pago.py
│   │   ├── evento_pago.py
│   │   └── regla_compensacion.py
│   ├── schemas/            # Esquemas Pydantic v2 (Base, Create, Update, Response)
│   ├── database.py         # Engine, SessionLocal y dependencia get_db
│   └── main.py             # Entrada de FastAPI y metadatos OpenAPI
├── tests/                  # Suite de pruebas automatizadas con pytest
│   ├── test_schemas.py     # Pruebas de validación estricta (HU-04)
│   └── test_api_crud.py    # Pruebas de endpoints CRUD y errores (HU-05)
├── .dockerignore           # Exclusión de archivos para imagen limpia
├── .env.example            # Plantilla de variables de entorno
├── .gitignore              # Archivos y carpetas ignorados por git
├── docker-compose.yml      # Orquestación de contenedores (API + PostgreSQL)
├── Dockerfile              # Construcción de la imagen Docker optimizada
└── pyproject.toml          # Definición de dependencias gestionadas por uv
```

---

## 🚀 Puesta en Marcha Rápida (con Docker Compose)

El entorno local completo (base de datos relacional y servidor web) se levanta con un solo comando:

```bash
docker compose up -d --build
```

### Servicios expuestos:

| Servicio             | Contenedor           | Puerto Local | Descripción                      |
| -------------------- | -------------------- | :----------: | --------------------------------- |
| **API REST**   | `vueladata_f7_api` |   `8000`   | Servidor FastAPI Uvicorn          |
| **PostgreSQL** | `vueladata_pg_dev` |   `5433`   | Motor de base de datos relacional |

* **Documentación interactiva (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Especificación OpenAPI (JSON):** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
* **Verificación de salud:** [http://localhost:8000/health](http://localhost:8000/health)
* **Verificación de conexión a BD:** [http://localhost:8000/health/db](http://localhost:8000/health/db)

Para detener los servicios:

```bash
docker compose down
```

---

## 💻 Ejecución Local en Desarrollo (sin Docker)

### 1. Requisitos previos

* Python 3.12 o superior.
* Gestor de paquetes [`uv`](https://github.com/astral-sh/uv).
* Base de datos PostgreSQL activa con el esquema `vueladata`.

### 2. Instalación de dependencias

```bash
# Sincronizar el entorno virtual (.venv) con las dependencias exactas
uv sync
```

### 3. Configuración de Variables de Entorno

Crea un archivo `.env` en la raíz de `api/`:

```env
DATABASE_URL=postgresql+psycopg://postgres:tu_password@localhost:5433/vueladata_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=tu_password
POSTGRES_DB=vueladata_db
```

### 4. Iniciar el servidor de desarrollo

```bash
uv run fastapi dev app/main.py
```

---

## 🧪 Pruebas Automatizadas

La suite de pruebas incluye validaciones unitarias de esquemas Pydantic y pruebas de integración sobre los endpoints CRUD usando `pytest` y `TestClient`:

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

Cuando pasa algo con un vuelo, `worker_rds` publica un mensaje y `worker_notificaciones` envía el correo a cada pasajero afectado.

```text
simulate_stream.py ──> q_rds_writer ──> worker_rds (guarda el evento en RDS)
                                            │ después del commit publica en:
                                            ▼
                         exchange "vueladata.notificaciones" (topic, durable)
                                            │ routing keys
                                            ▼
                         cola "q.notificaciones_email" (durable)
                                            ▼
                         worker_notificaciones ──> tabla notificacion + correo (Gmail SMTP)
```

| Routing key | Cuándo lo publica `worker_rds` | Correo que recibe el pasajero | `notificacion.tipo` |
| --- | --- | --- | --- |
| `vuelo.cancelado` | Llega un evento `CANCEL` | "Tu vuelo X fue cancelado" + sus derechos (RN-05/RN-06) | `INTERRUPCION` |
| `vuelo.retrasado` | Evento `OUT` con retraso ≥ `UMBRAL_RETRASO_NOTIFICACION_MIN` (120) | "Tu vuelo X tiene un retraso de N h M min" | `INTERRUPCION` |
| `conexion.en_riesgo` | Un retraso deja una conexión por debajo del tiempo mínimo (RN-07) | "Tu conexión en BOG está en riesgo" o "Perdiste tu conexión" | `CONEXION_RIESGO` |
| `itinerario.cambiado` | Tras una cancelación se ofrece el siguiente vuelo de la misma ruta | "Te ofrecemos un nuevo vuelo" + cómo aceptarlo en la API de pasajeros | `REUBICACION` |

### Garantías

* **Mensajes persistentes** (`delivery_mode=2`) en exchange y cola durables: sobreviven a un reinicio de RabbitMQ.
* **Publisher confirms**: `worker_rds` usa `confirm_delivery()`, así que cada publicación espera el ACK del broker.
* **Se publica después del commit**: nunca se avisa de algo que no quedó guardado. Si RabbitMQ falla al publicar, el evento igual queda guardado y el error queda en el log.
* **Sin correos duplicados**: un evento repetido se descarta en `worker_rds` (RN-09) y, si RabbitMQ entrega dos veces el mismo mensaje, `worker_notificaciones` encuentra la notificación ya `ENVIADA` y no la vuelve a mandar.
* **Fallos de Gmail**: la notificación queda `FALLIDA` en la tabla y se reintenta si el mensaje vuelve a llegar.
* **ACK manual** y `prefetch=1` en el worker de correos.

### Configurar Gmail

1. Activa la verificación en dos pasos en la cuenta de Gmail del equipo.
2. Crea una **contraseña de aplicación** en <https://myaccount.google.com/apppasswords>.
3. En `.env`: `SMTP_USUARIO`, `SMTP_CLAVE` (la contraseña de aplicación) y `EMAIL_DESTINO_PRUEBAS`.

> ⚠️ **Deja `EMAIL_DESTINO_PRUEBAS` con el correo del equipo.** Los correos del seed son inventados: si se envían de verdad, Gmail recibe rebotes y puede bloquear la cuenta. En modo pruebas todos los correos llegan a ese buzón e indican para quién eran. Gmail también limita los envíos diarios (~500 para cuentas personales).

### Ejecutar

```bash
uv run python -m worker_rds.main                # consume eventos y publica notificaciones
uv run python -m worker_notificaciones.main     # envía los correos
uv run python simulate_stream.py                # el último vuelo simulado se cancela
```

En AWS se despliega con `task-definition-worker-notificaciones.json` (las credenciales SMTP salen de SSM Parameter Store, no del archivo).

### Pruebas

```bash
uv run pytest tests/workers -v   # no necesita PostgreSQL, RabbitMQ ni Gmail
```
