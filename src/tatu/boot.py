import ujson, network, utime, esp, gc, socket, select
from umqtt.simple import MQTTClient
import tatu

esp.osdebug(None)
gc.collect()

with open('config.json') as f:
    _cfg = ujson.load(f)


def _connect_wifi():
    sta = network.WLAN(network.STA_IF)
    sta.active(False)
    utime.sleep_ms(200)
    sta.active(True)
    gc.collect()
    print('ssid:', _cfg['ssid'])
    sta.connect(_cfg['ssid'], _cfg['ssidPassword'])
    for _ in range(15):
        utime.sleep(1)
        if sta.isconnected():
            print('wifi ok', sta.ifconfig())
            return True
    print('wifi: no ip')
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
    if client is not None:
        try:
            client.disconnect()
        except Exception:
            pass
        client = None
    gc.collect()
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
print('heap free:', gc.mem_free())
print('broker reachable:', _broker_ok())

_mqtt_connect()

_dead_count = 0
_last_ping_ms = utime.ticks_ms()
_PING_MS = 30000

while True:
    now = utime.ticks_ms()
    try:
        client.check_msg()
        tatu.tick()
        _dead_count = 0
    except OSError as e:
        if e.args[0] != -1:
            print('loop err:', e)
            _dead_count += 1
        gc.collect()
    except Exception as e:
        print('loop err:', e)
        _dead_count += 1
        gc.collect()

    if utime.ticks_diff(now, _last_ping_ms) >= _PING_MS:
        try:
            client.ping()
        except Exception:
            _dead_count += 3
        _last_ping_ms = now

    if _dead_count >= 3:
        _dead_count = 0
        print('reconnecting...')
        sta = network.WLAN(network.STA_IF)
        if not sta.isconnected():
            _connect_wifi()
        try:
            _mqtt_connect()
            _last_ping_ms = utime.ticks_ms()
        except Exception as e2:
            print('reconnect err:', e2)
            utime.sleep(5)

    utime.sleep_ms(200)
