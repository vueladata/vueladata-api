"""Seguridad: sin secretos ni Account IDs reales en Task Definitions ni en código."""

import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
TASK_DEFINITIONS = sorted(RAIZ.glob("task-definition-*.json"))
PATRON_PARAMETRO = re.compile(
    r"^arn:aws:ssm:us-east-1:<ACCOUNT_ID>:parameter/vueladata/dev/[a-z0-9_]+/[a-z0-9_]+$"
)
PATRON_CUENTA_REAL = re.compile(r"\b\d{12}\b")
PATRON_SECRETO_AWS = re.compile(r"AKIA[0-9A-Z]{16}")

NOMBRES_SENSIBLES = re.compile(
    r"(PASSWORD|PASS|CLAVE|SECRET|TOKEN|USUARIO|USER|DATABASE_URL)", re.IGNORECASE
)


@pytest.mark.parametrize("ruta", TASK_DEFINITIONS, ids=lambda p: p.name)
def test_task_definition_es_json_valido(ruta):
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["family"]
    assert datos["containerDefinitions"]


@pytest.mark.parametrize("ruta", TASK_DEFINITIONS, ids=lambda p: p.name)
def test_parametros_siguen_la_lista_maestra(ruta):
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    for contenedor in datos["containerDefinitions"]:
        for secreto in contenedor.get("secrets", []):
            assert PATRON_PARAMETRO.match(secreto["valueFrom"]), (
                f"{ruta.name}: parámetro fuera de /vueladata/dev/<servicio>/<parametro>: "
                f"{secreto['valueFrom']}"
            )


@pytest.mark.parametrize("ruta", TASK_DEFINITIONS, ids=lambda p: p.name)
def test_no_hay_account_ids_reales(ruta):
    texto = ruta.read_text(encoding="utf-8")
    assert not PATRON_CUENTA_REAL.search(texto), f"{ruta.name} contiene un Account ID real"
    assert "<ACCOUNT_ID>" in texto  # el placeholder sí está permitido


@pytest.mark.parametrize("ruta", TASK_DEFINITIONS, ids=lambda p: p.name)
def test_credenciales_van_por_secrets_no_por_environment(ruta):
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    for contenedor in datos["containerDefinitions"]:
        variables_entorno = {item["name"] for item in contenedor.get("environment", [])}
        secretos = {item["name"] for item in contenedor.get("secrets", [])}

        sensibles_en_entorno = {n for n in variables_entorno if NOMBRES_SENSIBLES.search(n)}
        assert not sensibles_en_entorno, (
            f"{ruta.name}: variables sensibles en environment: {sorted(sensibles_en_entorno)}"
        )

        # Toda credencial declarada debe venir de SSM.
        for nombre in secretos:
            assert NOMBRES_SENSIBLES.search(nombre) or nombre in {
                "DATABASE_URL",
                "SMTP_USUARIO",
                "SMTP_CLAVE",
            }


def test_codigo_no_tiene_credenciales_quemadas():
    archivos = [
        RAIZ / "shared" / "rabbit_client.py",
        RAIZ / "shared" / "db_session.py",
    ]
    for archivo in archivos:
        texto = archivo.read_text(encoding="utf-8")
        assert "admin123" not in texto, f"{archivo} contiene la contraseña por defecto admin123"
        assert "postgres:password" not in texto, f"{archivo} contiene credenciales PostgreSQL"
        assert not PATRON_SECRETO_AWS.search(texto), f"{archivo} contiene una Access Key de AWS"
        assert not PATRON_CUENTA_REAL.search(texto), f"{archivo} contiene un Account ID real"


def test_env_example_no_publica_credenciales_reales():
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert "VuelaData_Rabbit2026!" not in texto
    assert "postgres:postgres@" not in texto
    assert "CAMBIAR_PASSWORD" in texto
