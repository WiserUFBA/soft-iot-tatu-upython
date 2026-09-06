# sensors.py — ESP8266 + Grove Shield (WeMos D1 Mini)
#
# Copy this file to sensors.py on the device root before uploading boot.py:
#   mpremote connect <PORT> cp examples/sensors_esp8266_grove.py :sensors.py
#
# Wiring (WeMos D1 Mini pin → Grove Shield port → sensor):
#   D4 (GPIO2)  → Grove Digital → DHT22   (temperatureSensor, humiditySensor)
#   A0 (ADC0)   → Grove Analog  → Light v1.2 (lightSensor) — raw 10-bit (0-1023)
#
# All libraries used (dht, machine) are built-in to MicroPython — no mip install needed.
#
# config.json for this node:
#   "sensors": [
#     {"type": "float", "name": "temperatureSensor"},
#     {"type": "float", "name": "humiditySensor"},
#     {"type": "integer", "name": "lightSensor"}
#   ]

from machine import Pin, ADC
import dht
import utime

_sensor = dht.DHT22(Pin(2))  # D4 on WeMos D1 Mini = GPIO2
_adc = ADC(0)                 # A0/ADC0 — only ADC pin on ESP8266
_last_ms = 0
_MIN_INTERVAL_MS = 2000       # DHT22 needs at least 2s between reads


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
    return _sensor.humidity()     # float, percent


def lightSensor():
    return _adc.read()            # integer, 0-1023 (10-bit ADC)
