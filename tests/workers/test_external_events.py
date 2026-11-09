import json
import pytest
from unittest.mock import Mock
from shared import models
from worker_rds.handlers.posicion_handler import procesar_posicion_aeronave
from worker_rds.handlers.clima_handler import procesar_observacion_clima
from worker_lake import s3_uploader


def position():
    return {'event_type': 'opensky_adsb', 'id_externo_posicion': 'opensky:abc123:1',
            'codigo_icao24': 'ABC123', 'latitud': 40., 'longitud': -73.,
            'fecha_hora_posicion_utc': '2026-11-08T12:00:00+00:00', 'en_tierra': False}


def test_position_requires_real_catalog_mapping_and_is_idempotent(db):
    assert procesar_posicion_aeronave(position(), db) == 'sin_catalogo'
    assert db.query(models.PosicionAeronave).count() == 0
    db.add(models.Aeronave(id_aeronave=7, codigo_icao24='abc123'))
    db.commit()
    assert procesar_posicion_aeronave(position(), db) == 'ok'
    assert procesar_posicion_aeronave(position(), db) == 'duplicado'
    assert db.query(models.PosicionAeronave).one().id_aeronave == 7


def test_weather_resolves_iata_without_fabricated_id(db):
    event = {'event_type': 'clima', 'id_aeropuerto': 'BOG',
             'fecha_hora_observacion_utc': '2026-11-08T12:00:00+00:00', 'velocidad_viento_kmh': 51.}
    assert procesar_observacion_clima(event, db) == 'ok'
    assert procesar_observacion_clima(event, db) == 'duplicado'
    assert db.query(models.ObservacionClima).one().id_aeropuerto == 1
    assert procesar_observacion_clima(dict(event, id_aeropuerto='XYZ'), db) == 'sin_catalogo'


def test_lake_routes_external_events_to_spark_prefixes(monkeypatch):
    s3 = Mock()
    monkeypatch.setattr(s3_uploader, '_cliente_s3', lambda: s3)
    events = [dict(position(), event_id='one'), {'event_type': 'clima', 'event_id': 'two', 'id_aeropuerto': 'BOG'}]
    first = s3_uploader.subir_lote(events)
    assert s3_uploader.subir_lote(events) == first
    assert len(s3.put_object.call_args_list) == 4
    for call in s3.put_object.call_args_list[:2]:
        record = json.loads(call.kwargs['Body'])
        source = 'opensky' if record['event_type'] == 'opensky_adsb' else 'clima'
        assert call.kwargs['Key'].startswith(f'bronze/events/{source}/')


@pytest.mark.parametrize('event_type,handler', [('opensky_adsb', 'procesar_posicion_aeronave'),
                                               ('clima', 'procesar_observacion_clima')])
def test_callback_routes_event_type_and_confirms_unresolved_before_ack(monkeypatch, event_type, handler):
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://')
    from worker_rds import main
    monkeypatch.setattr(main, 'SessionLocal', Mock(return_value=Mock()))
    processor = Mock(return_value='sin_catalogo')
    monkeypatch.setattr(main, handler, processor)
    ch = Mock()
    body = json.dumps({'event_type': event_type, 'event_id': 'test-event'}).encode()
    method = Mock(delivery_tag=42, routing_key='q.rds_writer')
    main.callback(ch, method, None, body)
    processor.assert_called_once()
    assert ch.basic_publish.call_args.kwargs['routing_key'] == 'q.rds_unresolved'
    assert ch.basic_publish.call_args.kwargs['body'] == body
    ch.basic_ack.assert_called_once_with(delivery_tag=42)
    ch.reset_mock()
    ch.basic_publish.side_effect = RuntimeError('confirm failed')
    main.callback(ch, method, None, body)
    ch.basic_ack.assert_not_called()
    ch.basic_nack.assert_called_once_with(delivery_tag=42, requeue=True)
