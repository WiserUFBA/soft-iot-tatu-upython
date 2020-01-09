

from machine import Pin
import dht

sensor = dht.DHT11(Pin(15))

def temperatureSensor():
  sensor.measure()
  return sensor.temperature()

def humiditySensor():
  sensor.measure()
  return sensor.humidity()



