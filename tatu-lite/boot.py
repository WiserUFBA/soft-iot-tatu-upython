


import upip
upip.install('umqtt.robust')

import tatu
import machine
import micropython
import network
import esp
import ujson
esp.osdebug(None)
import gc
gc.collect()
from umqtt.robust import MQTTClient

data = None

def sub_cb(topic, msg):
  #print(topic, msg)
  if data["topicReq"] in topic:
    tatu.main(data, msg)

  
with open('config.json') as f:
  data = ujson.load(f)

ssid = data['ssid']
ssidPassword = data['ssidPassword']
mqttBroker = data['mqttBroker']
mqttPort = data['mqttPort']
mqttUsername = data['mqttUsername']
mqttPassword = data['mqttPassword']
deviceName = data['deviceName']

station = network.WLAN(network.STA_IF)

station.active(True)
station.connect(ssid, ssidPassword)

while station.isconnected() == False:
  pass

print('Connection successful')
print(station.ifconfig())

c = MQTTClient(deviceName + '_sub', mqttBroker)

c.DEBUG = True
c.set_callback(sub_cb)

if not c.connect(clean_session=False):
  print('New session being set up')
  c.subscribe(str.encode(data['topicPrefix'] + deviceName + data['topicReq']))

while True:
  c.wait_msg()

c.disconnect()





