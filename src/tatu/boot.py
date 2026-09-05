import network
import esp
import ujson
import gc

esp.osdebug(None)
gc.collect()

from umqtt.robust import MQTTClient
import tatu

data = None


def sub_cb(topic, msg):
    if data['topicReq'].encode() in topic:
        tatu.on_message(data, topic, msg)


with open('config.json') as f:
    data = ujson.load(f)

station = network.WLAN(network.STA_IF)
station.active(True)
station.connect(data['ssid'], data['ssidPassword'])

while not station.isconnected():
    pass

print('Connection successful - ' + str(station.ifconfig()))

deviceName = data['deviceName']

c = MQTTClient(
    deviceName + '_sub',
    data['mqttBroker'],
    port=data['mqttPort'],
    user=data['mqttUsername'],
    password=data['mqttPassword'],
)
c.set_callback(sub_cb)

session_present = c.connect(clean_session=False)
if not session_present:
    print('New session, subscribing to topics')
    c.subscribe((data['topicPrefix'] + deviceName + data['topicReq'] + '/#').encode())
else:
    print('Resumed existing session')

print('Device: ' + deviceName)
for s in data.get('sensors', []):
    print('  Sensor: ' + s['name'])

try:
    while True:
        c.wait_msg()
finally:
    c.disconnect()
