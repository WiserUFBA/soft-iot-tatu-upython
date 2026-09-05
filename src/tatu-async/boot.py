import asyncio
import ujson
from mqtt_as import MQTTClient, config as mqtt_config
import tatu

_data = None
_sub_topic = None


async def _on_connect(client):
    await client.subscribe(_sub_topic, qos=0)
    print('Connected - subscribed to ' + _sub_topic.decode())


async def main():
    global _data, _sub_topic

    with open('config.json') as f:
        _data = ujson.load(f)

    deviceName = _data['deviceName']
    _sub_topic = (_data['topicPrefix'] + deviceName + _data['topicReq'] + '/#').encode()

    mqtt_config['ssid'] = _data['ssid']
    mqtt_config['wifi_pw'] = _data['ssidPassword']
    mqtt_config['server'] = _data['mqttBroker']
    mqtt_config['port'] = _data['mqttPort']
    mqtt_config['user'] = _data['mqttUsername']
    mqtt_config['password'] = _data['mqttPassword']
    mqtt_config['client_id'] = deviceName + '_sub'
    mqtt_config['queue_len'] = 8
    mqtt_config['connect_coro'] = _on_connect

    client = MQTTClient(mqtt_config)

    print('Device: ' + deviceName)
    for s in _data.get('sensors', []):
        print('  Sensor: ' + s['name'])

    await client.connect()

    async for topic, msg, retained in client.queue:
        if not retained:
            asyncio.create_task(tatu.on_message(_data, client, topic, msg))


asyncio.run(main())
