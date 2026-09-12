# sensors.py — ESP8266 + Grove HAT (WeMos D1 Mini / NodeMCU)
#
# Copy this file to sensors.py on the device root before uploading boot.py:
#   mpremote connect <PORT> cp examples/sensors_esp8266_grove.py :sensors.py
#
# Wiring (Grove HAT connector → GPIO → sensor):
#   Connector D8 → GPIO2 (D4)  → DHT22   (temperatureSensor, humiditySensor)
#   Connector A0  → ADC0 (A0)  → Light v1.2 (lightSensor) — raw 10-bit (0-1023)
#
# Note: the Grove HAT has no connector labeled “D4”. The connector labeled “D8”
# exposes two signal pins: D8 and D4 (GPIO2). Plug the DHT22 into the D4 pin
# of that connector (second signal pin).
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

_sensor = dht.DHT22(Pin(2))  # Grove HAT connector D8 → D4 = GPIO2
_adc = ADC(0)                 # Grove HAT connector A0 → ADC0
_MIN_INTERVAL_MS = 2000       # DHT22 minimum read interval
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
    return _last_temp  # float, degrees Celsius


def humiditySensor():
    _measure()
    return _last_hum   # float, percent


def lightSensor():
    return _adc.read() # integer, 0-1023 (10-bit ADC)
