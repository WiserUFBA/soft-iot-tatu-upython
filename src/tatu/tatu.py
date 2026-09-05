import _thread
import utime
import ujson
import sensors

from umqtt.robust import MQTTClient

_threads = {}       # thread_id -> StopEvent
_lock = _thread.allocate_lock()

_pub = None         # shared MQTT publisher (one connection for all threads)
_pub_lock = _thread.allocate_lock()


class StopEvent:
    """threading.Event equivalent for MicroPython."""

    def __init__(self):
        self._flag = False

    def set(self):
        self._flag = True

    def is_set(self):
        return self._flag

    def wait(self, timeout):
        """Sleep up to `timeout` seconds; return True if event was set."""
        end = utime.ticks_add(utime.ticks_ms(), int(timeout * 1000))
        while utime.ticks_diff(end, utime.ticks_ms()) > 0:
            if self._flag:
                return True
            utime.sleep_ms(50)
        return self._flag


def _thread_id(method, device, sensor):
    return method + '_' + device + '_' + sensor


def _ensure_pub(data):
    global _pub
    if _pub is None:
        _pub = MQTTClient(
            data['deviceName'] + '_pub',
            data['mqttBroker'],
            port=data['mqttPort'],
            user=data['mqttUsername'],
            password=data['mqttPassword'],
        )
        _pub.connect()


def _publish(topic, msg):
    """Thread-safe publish via the shared publisher."""
    _pub_lock.acquire()
    try:
        _pub.publish(topic, msg)
    finally:
        _pub_lock.release()


def on_message(data, topic, raw_msg):
    _ensure_pub(data)
    try:
        msg_json = ujson.loads(raw_msg)
    except Exception:
        print('Invalid JSON payload, ignoring.')
        return

    method = msg_json.get('method', '')
    if method == 'STOP':
        _stop_sensor(data, msg_json)
    elif method:
        _start_sensor(data, msg_json, raw_msg)
    else:
        print('Message missing method field, ignoring.')


def _stop_sensor(data, msg_json):
    target = msg_json.get('target', 'FLOW')
    sensor_name = msg_json.get('sensor', '')
    tid = _thread_id(target, data['deviceName'], sensor_name)

    _lock.acquire()
    try:
        stop_event = _threads.pop(tid, None)
    finally:
        _lock.release()

    if stop_event:
        stop_event.set()
        print('Stopping thread ' + tid)
    else:
        print('No running thread found for ' + tid)


def _start_sensor(data, msg_json, raw_msg):
    method = msg_json.get('method', '')
    sensor_name = msg_json.get('sensor', data['deviceName'])
    tid = _thread_id(method, data['deviceName'], sensor_name)
    stop_event = StopEvent()

    _lock.acquire()
    try:
        existing = _threads.pop(tid, None)
        if existing:
            existing.set()
        _threads[tid] = stop_event
    finally:
        _lock.release()

    print('-------------------------------------------------')
    print('| Thread: ' + tid)
    print('| Message: ' + str(raw_msg))
    print('-------------------------------------------------')

    _thread.start_new_thread(_run_sensor, (data, msg_json, tid, stop_event))


def _run_sensor(data, msg_json, tid, stop_event):
    method = msg_json.get('method', '')
    sensor_name = msg_json.get('sensor', data['deviceName'])
    device = data['deviceName']
    topic = (data['topicPrefix'] + device + data['topicRes']).encode()
    topic_err = (data['topicPrefix'] + device + data['topicErr']).encode()

    try:
        if method == 'GET':
            _do_get(device, sensor_name, topic, topic_err, data)
        elif method == 'FLOW':
            time_cfg = msg_json.get('time', {})
            collect = time_cfg.get('collect', 1)
            publish = time_cfg.get('publish', collect)
            _do_flow(device, sensor_name, topic, topic_err, collect, publish, stop_event, data)
        elif method == 'EVENT':
            time_cfg = msg_json.get('time', {})
            collect = time_cfg.get('collect', 1)
            _do_event(device, sensor_name, topic, topic_err, collect, stop_event)
        elif method == 'POST':
            _do_post(device, sensor_name, topic, topic_err, msg_json.get('value'))
        else:
            print('Unknown method: ' + method)
    finally:
        print('Stopping thread ' + tid)
        _lock.acquire()
        try:
            _threads.pop(tid, None)
        finally:
            _lock.release()


def _sensor_list(data, sensor_name):
    all_sensors = list(data['sensors'])
    if sensor_name == data['deviceName']:
        return all_sensors
    return [s for s in all_sensors if s['name'] == sensor_name]


def _publish_error(topic_err, sensor_name, device, msg=''):
    if not msg:
        msg = 'There is no ' + sensor_name + ' sensor in device ' + device
    _publish(topic_err, ujson.dumps({'code': 'ERROR', 'number': 1, 'message': msg}))


def _do_get(device, sensor_name, topic, topic_err, data):
    sensors_list = _sensor_list(data, sensor_name)
    try:
        if not sensors_list:
            raise Exception('Sensor not found: ' + sensor_name)
        sensor_data = {}
        for s in sensors_list:
            sensor_data[s['name']] = [getattr(sensors, s['name'])()] 
        header = {'method': 'GET', 'device': device, 'sensor': sensor_name}
        payload = {'sensors': [{k: v} for k, v in sensor_data.items()]}
        _publish(topic, ujson.dumps({'header': header, 'payload': payload}))
    except Exception as e:
        _publish_error(topic_err, sensor_name, device, str(e))


def _do_flow(device, sensor_name, topic, topic_err, collect, publish, stop_event, data):
    sensors_list = _sensor_list(data, sensor_name)
    try:
        if not sensors_list:
            raise Exception('Sensor not found: ' + sensor_name)
        buf = {s['name']: [] for s in sensors_list}
        t = 0
        while not stop_event.is_set():
            for s in sensors_list:
                buf[s['name']].append(getattr(sensors, s['name'])())
            t += collect
            if t >= publish:
                header = {
                    'method': 'FLOW', 'device': device, 'sensor': sensor_name,
                    'time': {'collect': collect, 'publish': publish},
                }
                payload = {'sensors': [{k: list(v)} for k, v in buf.items()]}
                _publish(topic, ujson.dumps({'header': header, 'payload': payload}))
                t = 0
                for name in buf:
                    buf[name] = []
            if stop_event.wait(collect):
                break
    except Exception as e:
        _publish_error(topic_err, sensor_name, device, str(e))


def _do_event(device, sensor_name, topic, topic_err, collect, stop_event):
    try:
        fn = getattr(sensors, sensor_name)
        value = fn()
        header = {'method': 'EVENT', 'device': device, 'sensor': sensor_name,
                  'time': {'collect': collect}}
        payload = {'sensors': [{sensor_name: [value]}]}
        _publish(topic, ujson.dumps({'header': header, 'payload': payload}))
        while not stop_event.wait(collect):
            new_val = fn()
            if new_val != value:
                value = new_val
                payload = {'sensors': [{sensor_name: [value]}]}
                _publish(topic, ujson.dumps({'header': header, 'payload': payload}))
    except Exception as e:
        _publish_error(topic_err, sensor_name, device, str(e))


def _do_post(device, sensor_name, topic, topic_err, value):
    try:
        result = getattr(sensors, sensor_name)(value)
        header = {'method': 'POST', 'device': device, 'sensor': sensor_name, 'value': result}
        _publish(topic, ujson.dumps({'header': header, 'payload': {'value': result}}))
    except Exception as e:
        _publish_error(topic_err, sensor_name, device, str(e))
