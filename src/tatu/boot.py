import ujson, network, utime, esp, gc, socket, select
from umqtt.simple import MQTTClient
import tatu

esp.osdebug(None)
gc.collect()

with open('config.json') as f:
    _cfg = ujson.load(f)


def _connect_wifi():
    sta = network.WLAN(network.STA_IF)
    # active(False) + active(True) forces the radio to drop stored credentials
    # and reconnect to the SSID in config.json instead of the last known network
    sta.active(False)
    utime.sleep_ms(200)
    sta.active(True)
    gc.collect()
    print('ssid alvo:', _cfg['ssid'])
    sta.connect(_cfg['ssid'], _cfg['ssidPassword'])
    for _ in range(15):
        utime.sleep(1)
        if sta.isconnected():
            print('wifi dhcp ok', sta.ifconfig())
            return True
    print('wifi sem ip')
    return False


def _broker_ok():
    s = socket.socket()
    s.setblocking(False)
    try:
        s.connect((_cfg['mqttBroker'], _cfg['mqttPort']))
    except OSError:
        pass
    _, w, _ = select.select([], [s], [], 5)
    s.close()
    return bool(w)


client = None


def _on_msg(topic, msg):
    tatu.on_message(_cfg, topic, msg)


def _mqtt_connect():
    global client
    print('mqtt connect...')
    c = MQTTClient(
        _cfg['deviceName'],
        _cfg['mqttBroker'],
        port=_cfg['mqttPort'],
        user=_cfg.get('mqttUsername') or None,
        password=_cfg.get('mqttPassword') or None,
        keepalive=60,
    )
    c.set_callback(_on_msg)
    c.connect(clean_session=True)
    sub = (_cfg['topicPrefix'] + _cfg['deviceName'] + _cfg['topicReq'] + '/#').encode()
    c.subscribe(sub)
    client = c
    tatu.init(client, _cfg)
    print('mqtt ok, subscribed', sub)


_connect_wifi()
gc.collect()
print('heap livre:', gc.mem_free())
print('broker tcp:', _broker_ok())

_mqtt_connect()

_err_count = 0
while True:
    try:
        client.check_msg()
        tatu.tick()
        _err_count = 0
    except Exception as e:
        print('loop err:', e)
        _err_count += 1
        gc.collect()
        if _err_count >= 3:
            _err_count = 0
            print('reconectando...')
            sta = network.WLAN(network.STA_IF)
            if not sta.isconnected():
                _connect_wifi()
            try:
                _mqtt_connect()
            except Exception as e2:
                print('reconexao err:', e2)
                utime.sleep(5)
    utime.sleep_ms(200)
