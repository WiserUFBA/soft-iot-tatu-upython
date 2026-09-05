# sensors.py for DHT22 on GPIO 15
# Copy this file to sensors.py (on the device root) to use it.
#
# DHT22 vs DHT11:
#   - Higher precision: temperature ±0.5 °C, humidity ±2-5 %
#   - Returns floats (e.g. 25.3, 60.5) instead of integers
#   - Same 2-second minimum interval between reads
#   - Same wiring: VCC, GND, DATA + 10k pull-up on DATA

from machine import Pin
import dht
import utime

_sensor = dht.DHT22(Pin(15))
_last_ms = 0
_MIN_INTERVAL_MS = 2000  # DHT22 needs at least 2s between reads


def _measure():
    global _last_ms
    now = utime.ticks_ms()
    if utime.ticks_diff(now, _last_ms) >= _MIN_INTERVAL_MS:
        _sensor.measure()
        _last_ms = now


def temperatureSensor():
    _measure()
    return _sensor.temperature()  # float, degrees Celsius


def humiditySensor():
    _measure()
    return _sensor.humidity()  # float, percent
