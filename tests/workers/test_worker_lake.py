"""worker_lake: escritura en S3 Bronze / fallback local y orden ACK-escritura."""

import json

import pytest

import worker_lake.main as lake_main
import worker_lake.s3_uploader as s3_uploader


class CanalFalso:
    def __init__(self):
        self.acks = []

    def basic_ack(self, delivery_tag):
        self.acks.append(delivery_tag)


@pytest.fixture(autouse=True)
def limpiar_buffer(monkeypatch):
    monkeypatch.setattr(lake_main, "_buffer", [])
    monkeypatch.setattr(lake_main, "_tags", [])
    monkeypatch.setattr(lake_main, "_ultimo_flush", 0)
    yield


def _cargar_lote(cantidad=2):
    for i in range(1, cantidad + 1):
        lake_main._buffer.append({"id": i})
        lake_main._tags.append(100 + i)


def test_flush_hace_ack_solo_despues_de_escribir(monkeypatch):
    escritos = []
    monkeypatch.setattr(lake_main, "subir_lote", lambda lote: escritos.append(list(lote)))
    _cargar_lote()
    canal = CanalFalso()

    resultado = lake_main._realizar_flush(canal)

    assert resultado is True
    assert escritos == [[{"id": 1}, {"id": 2}]]
    assert canal.acks == [101, 102]
    assert lake_main._buffer == []
    assert lake_main._tags == []


def test_si_falla_la_escritura_no_hay_ack_ni_se_pierde_el_lote(monkeypatch):
    def subir_que_falla(lote):
        raise ConnectionError("S3 caído")

    monkeypatch.setattr(lake_main, "subir_lote", subir_que_falla)
    _cargar_lote()
    canal = CanalFalso()

    resultado = lake_main._realizar_flush(canal)

    assert resultado is False
    assert canal.acks == []
    assert lake_main._buffer == [{"id": 1}, {"id": 2}]
    assert lake_main._tags == [101, 102]


def test_lote_nuevo_durante_la_subida_no_se_borra(monkeypatch):
    def subir_y_agregar(lote):
        # Simula un mensaje que llega mientras la escritura está en curso.
        lake_main._buffer.append({"id": 99})
        lake_main._tags.append(199)

    monkeypatch.setattr(lake_main, "subir_lote", subir_y_agregar)
    _cargar_lote()
    canal = CanalFalso()

    lake_main._realizar_flush(canal)

    assert canal.acks == [101, 102]
    assert lake_main._buffer == [{"id": 99}]
    assert lake_main._tags == [199]


class ClienteS3Falso:
    def __init__(self, fallar=False):
        self.fallar = fallar
        self.llamadas = []

    def put_object(self, **kwargs):
        if self.fallar:
            raise ConnectionError("sin credenciales")
        self.llamadas.append(kwargs)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}


def test_subir_lote_escribe_en_s3_bronze(monkeypatch):
    cliente = ClienteS3Falso()
    monkeypatch.setattr(s3_uploader, "_cliente_s3", lambda: cliente)

    clave = s3_uploader.subir_lote([{"id_vuelo": 1}])

    assert clave.startswith("bronze/eventos_oooi/year=")
    assert cliente.llamadas[0]["Bucket"] == s3_uploader.BUCKET
    assert cliente.llamadas[0]["Key"] == clave
    assert json.loads(cliente.llamadas[0]["Body"]) == [{"id_vuelo": 1}]


def test_subir_lote_usa_fallback_local(monkeypatch, tmp_path):
    monkeypatch.setattr(s3_uploader, "_cliente_s3", lambda: ClienteS3Falso(fallar=True))
    monkeypatch.setenv("LOCAL_LAKE_FALLBACK", "true")
    monkeypatch.chdir(tmp_path)

    ruta = s3_uploader.subir_lote([{"id_vuelo": 2}])

    archivo = tmp_path / ruta
    assert archivo.exists()
    assert json.loads(archivo.read_text(encoding="utf-8")) == [{"id_vuelo": 2}]


def test_subir_lote_sin_fallback_propaga_el_error(monkeypatch):
    monkeypatch.setattr(s3_uploader, "_cliente_s3", lambda: ClienteS3Falso(fallar=True))
    monkeypatch.setenv("LOCAL_LAKE_FALLBACK", "false")

    with pytest.raises(ConnectionError):
        s3_uploader.subir_lote([{"id_vuelo": 3}])
