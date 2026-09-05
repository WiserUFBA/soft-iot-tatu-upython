from machine import Pin
import dht
import utime

_sensor = dht.DHT11(Pin(15))
_last_ms = 0
_MIN_INTERVAL_MS = 2000  # DHT11 needs at least 2s between reads


def _measure():
    global _last_ms
    now = utime.ticks_ms()
    if utime.ticks_diff(now, _last_ms) >= _MIN_INTERVAL_MS:
        _sensor.measure()
        _last_ms = now


def temperatureSensor():
    _measure()
    return _sensor.temperature()


def humiditySensor():
    _measure()
    return _sensor.humidity()
