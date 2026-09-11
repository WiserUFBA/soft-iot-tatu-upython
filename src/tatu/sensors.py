# Generic DHT22 sensors example.
# Adjust Pin number to match your hardware:
#   WeMos D1 Mini: D4=GPIO2, D5=GPIO14, D6=GPIO12, D7=GPIO13, D8=GPIO15
#   NodeMCU:       same GPIO numbering as WeMos D1 Mini
# See examples/ for device-specific configurations (Grove Shield, etc.).
from machine import Pin
import dht
import utime

_sensor = dht.DHT22(Pin(12))  # D6 = GPIO12 — adjust as needed
_MIN_INTERVAL_MS = 2000
_last_ms = 0
_last_temp = None
_last_hum = None


def _measure():
    global _last_ms, _last_temp, _last_hum
    now = utime.ticks_ms()
    if utime.ticks_diff(now, _last_ms) >= _MIN_INTERVAL_MS:
        try:
            _sensor.measure()
            _last_temp = _sensor.temperature()
            _last_hum = _sensor.humidity()
            _last_ms = now
        except Exception:
            pass


def temperatureSensor():
    _measure()
    return _last_temp


def humiditySensor():
    _measure()
    return _last_hum
