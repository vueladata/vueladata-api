from app.schemas.aerolinea import AerolineaBase, AerolineaCreate, AerolineaUpdate, AerolineaResponse
from app.schemas.aeronave import AeronaveBase, AeronaveCreate, AeronaveUpdate, AeronaveResponse
from app.schemas.aeropuerto import AeropuertoBase, AeropuertoCreate, AeropuertoUpdate, AeropuertoResponse
from app.schemas.auditoria_causa import AuditoriaCausaBase, AuditoriaCausaCreate, AuditoriaCausaUpdate, AuditoriaCausaResponse
from app.schemas.causa import CausaBase, CausaCreate, CausaUpdate, CausaResponse
from app.schemas.checkin import CheckinBase, CheckinCreate, CheckinUpdate, CheckinResponse
from app.schemas.ciudad import CiudadBase, CiudadCreate, CiudadUpdate, CiudadResponse
from app.schemas.compensacion import CompensacionBase, CompensacionCreate, CompensacionUpdate, CompensacionResponse
from app.schemas.conexion_itinerario import ConexionItinerarioBase, ConexionItinerarioCreate, ConexionItinerarioUpdate, ConexionItinerarioResponse
from app.schemas.detalle_reserva import DetalleReservaBase, DetalleReservaCreate, DetalleReservaUpdate, DetalleReservaResponse
from app.schemas.estado_vuelo import EstadoVueloBase, EstadoVueloCreate, EstadoVueloUpdate, EstadoVueloResponse
from app.schemas.evaluacion_conexion import EvaluacionConexionBase, EvaluacionConexionCreate, EvaluacionConexionUpdate, EvaluacionConexionResponse
from app.schemas.evento_operacional import EventoOperacionalBase, EventoOperacionalCreate, EventoOperacionalUpdate, EventoOperacionalResponse
from app.schemas.evento_pago import EventoPagoBase, EventoPagoCreate, EventoPagoUpdate, EventoPagoResponse
from app.schemas.incidencia_vuelo import IncidenciaVueloBase, IncidenciaVueloCreate, IncidenciaVueloUpdate, IncidenciaVueloResponse
from app.schemas.itinerario import ItinerarioBase, ItinerarioCreate, ItinerarioUpdate, ItinerarioResponse
from app.schemas.notificacion import NotificacionBase, NotificacionCreate, NotificacionUpdate, NotificacionResponse
from app.schemas.observacion_clima import ObservacionClimaBase, ObservacionClimaCreate, ObservacionClimaUpdate, ObservacionClimaResponse
from app.schemas.pago import PagoBase, PagoCreate, PagoUpdate, PagoResponse
from app.schemas.pais import PaisBase, PaisCreate, PaisUpdate, PaisResponse
from app.schemas.pasajero import PasajeroBase, PasajeroCreate, PasajeroUpdate, PasajeroResponse
from app.schemas.pasajero_consulta import (
    PasajeroCompensacionesResponse,
    PasajeroItinerariosResponse,
    PasajeroPerfilResponse,
    ReservaEstadoResponse,
)
from app.schemas.posicion_aeronave import PosicionAeronaveBase, PosicionAeronaveCreate, PosicionAeronaveUpdate, PosicionAeronaveResponse
from app.schemas.proyeccion_propagacion import ProyeccionPropagacionBase, ProyeccionPropagacionCreate, ProyeccionPropagacionUpdate, ProyeccionPropagacionResponse
from app.schemas.regla_compensacion import ReglaCompensacionBase, ReglaCompensacionCreate, ReglaCompensacionUpdate, ReglaCompensacionResponse
from app.schemas.regla_rotacion import ReglaRotacionBase, ReglaRotacionCreate, ReglaRotacionUpdate, ReglaRotacionResponse
from app.schemas.reserva import ReservaBase, ReservaCreate, ReservaUpdate, ReservaResponse
from app.schemas.reserva_pasajero import ReservaPasajeroBase, ReservaPasajeroCreate, ReservaPasajeroUpdate, ReservaPasajeroResponse
from app.schemas.reubicacion import ReubicacionBase, ReubicacionCreate, ReubicacionUpdate, ReubicacionResponse
from app.schemas.ruta import RutaBase, RutaCreate, RutaUpdate, RutaResponse
from app.schemas.tiempo_minimo_conexion import TiempoMinimoConexionBase, TiempoMinimoConexionCreate, TiempoMinimoConexionUpdate, TiempoMinimoConexionResponse
from app.schemas.vuelo import VueloBase, VueloCreate, VueloUpdate, VueloResponse

__all__ = ['AerolineaBase', 'AerolineaCreate', 'AerolineaUpdate', 'AerolineaResponse', 'AeronaveBase', 'AeronaveCreate', 'AeronaveUpdate', 'AeronaveResponse', 'AeropuertoBase', 'AeropuertoCreate', 'AeropuertoUpdate', 'AeropuertoResponse', 'AuditoriaCausaBase', 'AuditoriaCausaCreate', 'AuditoriaCausaUpdate', 'AuditoriaCausaResponse', 'CausaBase', 'CausaCreate', 'CausaUpdate', 'CausaResponse', 'CheckinBase', 'CheckinCreate', 'CheckinUpdate', 'CheckinResponse', 'CiudadBase', 'CiudadCreate', 'CiudadUpdate', 'CiudadResponse', 'CompensacionBase', 'CompensacionCreate', 'CompensacionUpdate', 'CompensacionResponse', 'ConexionItinerarioBase', 'ConexionItinerarioCreate', 'ConexionItinerarioUpdate', 'ConexionItinerarioResponse', 'DetalleReservaBase', 'DetalleReservaCreate', 'DetalleReservaUpdate', 'DetalleReservaResponse', 'EstadoVueloBase', 'EstadoVueloCreate', 'EstadoVueloUpdate', 'EstadoVueloResponse', 'EvaluacionConexionBase', 'EvaluacionConexionCreate', 'EvaluacionConexionUpdate', 'EvaluacionConexionResponse', 'EventoOperacionalBase', 'EventoOperacionalCreate', 'EventoOperacionalUpdate', 'EventoOperacionalResponse', 'EventoPagoBase', 'EventoPagoCreate', 'EventoPagoUpdate', 'EventoPagoResponse', 'IncidenciaVueloBase', 'IncidenciaVueloCreate', 'IncidenciaVueloUpdate', 'IncidenciaVueloResponse', 'ItinerarioBase', 'ItinerarioCreate', 'ItinerarioUpdate', 'ItinerarioResponse', 'NotificacionBase', 'NotificacionCreate', 'NotificacionUpdate', 'NotificacionResponse', 'ObservacionClimaBase', 'ObservacionClimaCreate', 'ObservacionClimaUpdate', 'ObservacionClimaResponse', 'PagoBase', 'PagoCreate', 'PagoUpdate', 'PagoResponse', 'PaisBase', 'PaisCreate', 'PaisUpdate', 'PaisResponse', 'PasajeroBase', 'PasajeroCreate', 'PasajeroUpdate', 'PasajeroResponse', 'PosicionAeronaveBase', 'PosicionAeronaveCreate', 'PosicionAeronaveUpdate', 'PosicionAeronaveResponse', 'ProyeccionPropagacionBase', 'ProyeccionPropagacionCreate', 'ProyeccionPropagacionUpdate', 'ProyeccionPropagacionResponse', 'ReglaCompensacionBase', 'ReglaCompensacionCreate', 'ReglaCompensacionUpdate', 'ReglaCompensacionResponse', 'ReglaRotacionBase', 'ReglaRotacionCreate', 'ReglaRotacionUpdate', 'ReglaRotacionResponse', 'ReservaBase', 'ReservaCreate', 'ReservaUpdate', 'ReservaResponse', 'ReservaPasajeroBase', 'ReservaPasajeroCreate', 'ReservaPasajeroUpdate', 'ReservaPasajeroResponse', 'ReubicacionBase', 'ReubicacionCreate', 'ReubicacionUpdate', 'ReubicacionResponse', 'RutaBase', 'RutaCreate', 'RutaUpdate', 'RutaResponse', 'TiempoMinimoConexionBase', 'TiempoMinimoConexionCreate', 'TiempoMinimoConexionUpdate', 'TiempoMinimoConexionResponse', 'VueloBase', 'VueloCreate', 'VueloUpdate', 'VueloResponse', 'PasajeroPerfilResponse', 'PasajeroItinerariosResponse', 'PasajeroCompensacionesResponse', 'ReservaEstadoResponse']
