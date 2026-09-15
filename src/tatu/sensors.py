from machine import Pin
import dht
import utime

_sensor = dht.DHT22(Pin(12))  # D6 = GPIO12
_MIN_INTERVAL_MS = 2000
_MAX_CACHE_MS = 30000  # dado válido por no máximo 30s

_first = True          # sentinela: força tentativa na primeira chamada
_last_attempt_ms = 0   # instante da última tentativa (bem-sucedida ou não)
_last_success_ms = 0   # instante da última leitura válida
_last_temp = None
_last_hum = None


def _measure():
    global _first, _last_attempt_ms, _last_success_ms, _last_temp, _last_hum
    now = utime.ticks_ms()
    if not _first and utime.ticks_diff(now, _last_attempt_ms) < _MIN_INTERVAL_MS:
        return
    _first = False
    _last_attempt_ms = now
    try:
        _sensor.measure()
        _last_temp = _sensor.temperature()
        _last_hum = _sensor.humidity()
        _last_success_ms = now
    except Exception:
        pass  # mantém cache anterior; _last_attempt_ms já foi atualizado


def _fresh(value):
    if value is None:
        return None
    if utime.ticks_diff(utime.ticks_ms(), _last_success_ms) > _MAX_CACHE_MS:
        return None  # cache expirado
    return value


def temperatureSensor():
    _measure()
    return _fresh(_last_temp)


def humiditySensor():
    _measure()
    return _fresh(_last_hum)
