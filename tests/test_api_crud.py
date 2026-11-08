import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, SmallInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # registra todas las tablas del dominio F7
from app.database import Base, get_db
from app.main import app


@compiles(BigInteger, "sqlite")
def _bigint_como_integer(tipo, compilador, **kw):
    return "INTEGER"


@compiles(SmallInteger, "sqlite")
def _smallint_como_integer(tipo, compilador, **kw):
    return "INTEGER"


@pytest.fixture(autouse=True)
def base_sqlite():
    """CRUD aislado en SQLite: no requiere PostgreSQL para correr la suite."""
    motor = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"vueladata": None}},
    )
    Base.metadata.create_all(motor)
    Session = sessionmaker(bind=motor)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield motor
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(motor)


client = TestClient(app)


# ============================================================================
# Criterio 3: Documentación OpenAPI autogenerada
# ============================================================================

def test_openapi_documentation_available():
    """Valida que la documentación OpenAPI esté generada y exponga contratos y esquemas."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "components" in schema
    assert "/causas/" in schema["paths"]
    assert "/reglas-compensacion/" in schema["paths"]
    assert "/compensaciones/" in schema["paths"]
    assert "/pagos/" in schema["paths"]
    assert "/eventos-pago/" in schema["paths"]

    # Validar que los tags de negocio están documentados
    tag_names = [t["name"] for t in schema.get("tags", [])]
    assert "Causas" in tag_names
    assert "Compensaciones" in tag_names
    assert "Pagos" in tag_names


def test_health_endpoints():
    """Valida los endpoints de monitoreo y conectividad."""
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json() == {"status": "ok"}

    r_db = client.get("/health/db")
    assert r_db.status_code == 200
    assert r_db.json() == {"status": "ok", "database": "online"}


# ============================================================================
# Criterio 1: Operaciones CRUD requeridas impactando la BD de manera correcta
# ============================================================================

def test_crud_causa_lifecycle():
    """Prueba el ciclo completo CRUD de Causa: Crear, Leer, Actualizar y Eliminar."""
    unique_code = "TEST_CRUD_01"

    # 1. CREATE (POST)
    payload = {
        "codigo": unique_code,
        "nombre": "Causa de prueba para verificación CRUD",
        "descripcion": "Descripción inicial",
        "es_imputable": True,
    }
    r_create = client.post("/causas/", json=payload)
    assert r_create.status_code == 201
    created = r_create.json()
    assert created["codigo"] == unique_code
    assert created["es_imputable"] is True
    id_causa = created["id_causa"]

    # 2. READ (GET by ID)
    r_get = client.get(f"/causas/{id_causa}")
    assert r_get.status_code == 200
    assert r_get.json()["id_causa"] == id_causa
    assert r_get.json()["nombre"] == payload["nombre"]

    # 3. READ LIST (GET with pagination)
    r_list = client.get("/causas/?limit=10")
    assert r_list.status_code == 200
    assert isinstance(r_list.json(), list)
    assert any(c["id_causa"] == id_causa for c in r_list.json())

    # 4. UPDATE (PATCH)
    update_payload = {
        "nombre": "Nombre actualizado por CRUD",
        "descripcion": "Descripción actualizada",
    }
    r_update = client.patch(f"/causas/{id_causa}", json=update_payload)
    assert r_update.status_code == 200
    updated = r_update.json()
    assert updated["nombre"] == update_payload["nombre"]
    assert updated["descripcion"] == update_payload["descripcion"]
    assert updated["codigo"] == unique_code  # no cambió

    # 5. DELETE
    r_delete = client.delete(f"/causas/{id_causa}")
    assert r_delete.status_code == 204

    # 6. VERIFY DELETION (GET should return 404)
    r_verify = client.get(f"/causas/{id_causa}")
    assert r_verify.status_code == 404


def test_crud_regla_compensacion_lifecycle():
    """Prueba el ciclo CRUD para ReglaCompensacion."""
    payload = {
        "tipo_incidencia": "RETRASO",
        "minutos_minimos": 180,
        "minutos_maximos": 300,
        "aviso_max_horas": None,
        "porcentaje": "0.5000",
        "requiere_reubicacion": False,
        "vigente_desde_utc": "2026-01-01T00:00:00Z",
        "vigente_hasta_utc": None,
    }
    # Create
    r_create = client.post("/reglas-compensacion/", json=payload)
    assert r_create.status_code == 201
    created = r_create.json()
    id_regla = created["id_regla_compensacion"]

    # Read
    r_get = client.get(f"/reglas-compensacion/{id_regla}")
    assert r_get.status_code == 200
    assert r_get.json()["tipo_incidencia"] == "RETRASO"

    # Update
    r_update = client.patch(f"/reglas-compensacion/{id_regla}", json={"porcentaje": "0.6000"})
    assert r_update.status_code == 200
    assert float(r_update.json()["porcentaje"]) == 0.6

    # Delete
    r_del = client.delete(f"/reglas-compensacion/{id_regla}")
    assert r_del.status_code == 204

    # Verify 404
    assert client.get(f"/reglas-compensacion/{id_regla}").status_code == 404


# ============================================================================
# Criterio 2: Manejo de errores HTTP y respuestas claras (404, 400, 422)
# ============================================================================

def test_error_404_on_nonexistent_resource():
    """Valida que registros inexistentes retornen código 404 y un mensaje claro."""
    # Causa inexistente (id dentro del rango de SMALLINT pero que no existe)
    r_causa = client.get("/causas/32000")
    assert r_causa.status_code == 404
    assert "no fue encontrada" in r_causa.json()["detail"]

    # Compensación inexistente
    r_comp = client.get("/compensaciones/999999")
    assert r_comp.status_code == 404
    assert "no fue encontrada" in r_comp.json()["detail"]

    # Pago inexistente
    r_pago = client.get("/pagos/999999")
    assert r_pago.status_code == 404
    assert "no fue encontrado" in r_pago.json()["detail"]

    # Clave de idempotencia inexistente
    r_idemp = client.get("/pagos/idempotencia/CLAVE_INEXISTENTE_XYZ")
    assert r_idemp.status_code == 404


def test_error_422_on_invalid_data_types():
    """Valida que enviar datos con tipos o estructuras erróneas devuelva 422 Unprocessable Entity."""
    # id_causa debe ser entero, no texto
    r_invalid_id = client.get("/causas/texto_en_vez_de_id")
    assert r_invalid_id.status_code == 422

    # Payload con campo requerido ausente
    r_missing_field = client.post("/causas/", json={"nombre": "Sin código"})
    assert r_missing_field.status_code == 422

    # Payload con string vacío que viola min_length=1
    r_empty_string = client.post(
        "/causas/",
        json={"codigo": "", "nombre": "Nombre", "es_imputable": True},
    )
    assert r_empty_string.status_code == 422


def test_error_400_on_duplicate_unique_constraint():
    """Valida que intentar crear duplicados controlados devuelva 400 Bad Request."""
    code = "DUPLICATE_CODE_TEST"
    payload = {
        "codigo": code,
        "nombre": "Causa original",
        "descripcion": "Primera inserción",
        "es_imputable": False,
    }

    # Primera inserción exitosa
    r1 = client.post("/causas/", json=payload)
    assert r1.status_code == 201
    id_causa = r1.json()["id_causa"]

    try:
        # Segunda inserción con el mismo código debe fallar con 400
        r2 = client.post("/causas/", json=payload)
        assert r2.status_code == 400
        assert "Ya existe una causa con el código" in r2.json()["detail"]
    finally:
        # Limpieza
        client.delete(f"/causas/{id_causa}")
