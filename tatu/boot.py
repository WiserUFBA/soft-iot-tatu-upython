

import upip
upip.install('umqtt.robust')

import tatu
import machine
import micropython
import network
import esp
import utime
import ujson
esp.osdebug(None)
import gc
gc.collect()
from umqtt.robust import MQTTClient

data = None
topicPrefix = "dev/"

def sub_cb(topic, msg):
  #print(topic, msg)
  if "RES" not in topic:
    tatu.main(data, msg)


  
station = network.WLAN(network.STA_IF)
station.active(True)


if not station.isconnected():
  print("Waiting for connection...")
  while not station.isconnected():
    with open('config.json') as f:
      data = ujson.load(f)
    ssid = data['ssid']
    ssidPassword = data['ssidPassword']
    station.connect(ssid, ssidPassword)  
    f.close()
    utime.sleep(1)    


print(station.ifconfig())


conn = False

while not conn:
  with open('config.json') as f:
    data = ujson.load(f)
    
  mqttBroker = data['mqttBroker']
  mqttPort = data['mqttPort']
  mqttUsername = data['mqttUsername']
  mqttPassword = data['mqttPassword']
  deviceName = data['deviceName']
  c = MQTTClient(deviceName + '_sub', mqttBroker)
  c.DEBUG = True
  c.set_callback(sub_cb)
  try:
    c.connect()
    c.subscribe(str.encode(topicPrefix + deviceName + "/#"))
    conn = True
    print ("Broker connected on " + mqttBroker + " URL!")
  except:
    print ("Broker unreachable on " + mqttBroker + " URL!")
    utime.sleep(3)
  f.close()



while True:
  c.wait_msg()

c.disconnect()


