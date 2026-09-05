import asyncio
import ujson
import sensors

_tasks = {}  # task_id -> asyncio.Task


def _task_id(method, device, sensor):
    return method + '_' + device + '_' + sensor


async def on_message(data, client, topic, raw_msg):
    try:
        msg_json = ujson.loads(raw_msg)
    except Exception:
        print('Invalid JSON payload, ignoring.')
        return

    method = msg_json.get('method', '')
    if method == 'STOP':
        _stop_sensor(data, msg_json)
    elif method:
        await _start_sensor(data, client, msg_json, raw_msg)
    else:
        print('Message missing method field, ignoring.')


def _stop_sensor(data, msg_json):
    target = msg_json.get('target', 'FLOW')
    sensor_name = msg_json.get('sensor', '')
    tid = _task_id(target, data['deviceName'], sensor_name)

    task = _tasks.pop(tid, None)
    if task:
        task.cancel()
        print('Stopping thread ' + tid)
    else:
        print('No running thread found for ' + tid)


async def _start_sensor(data, client, msg_json, raw_msg):
    method = msg_json.get('method', '')
    sensor_name = msg_json.get('sensor', data['deviceName'])
    tid = _task_id(method, data['deviceName'], sensor_name)

    existing = _tasks.pop(tid, None)
    if existing:
        existing.cancel()

    print('-------------------------------------------------')
    print('| Task: ' + tid)
    print('| Message: ' + str(raw_msg))
    print('-------------------------------------------------')

    task = asyncio.create_task(_run_sensor(data, client, msg_json, tid))
    _tasks[tid] = task


async def _run_sensor(data, client, msg_json, tid):
    method = msg_json.get('method', '')
    sensor_name = msg_json.get('sensor', data['deviceName'])
    device = data['deviceName']
    topic = (data['topicPrefix'] + device + data['topicRes']).encode()
    topic_err = (data['topicPrefix'] + device + data['topicErr']).encode()

    try:
        if method == 'GET':
            await _do_get(device, sensor_name, topic, topic_err, client, data)
        elif method == 'FLOW':
            time_cfg = msg_json.get('time', {})
            collect = time_cfg.get('collect', 1)
            publish = time_cfg.get('publish', collect)
            await _do_flow(device, sensor_name, topic, topic_err, client, collect, publish, data)
        elif method == 'EVENT':
            time_cfg = msg_json.get('time', {})
            collect = time_cfg.get('collect', 1)
            await _do_event(device, sensor_name, topic, topic_err, client, collect)
        elif method == 'POST':
            await _do_post(device, sensor_name, topic, topic_err, client, msg_json.get('value'))
        else:
            print('Unknown method: ' + method)
    except asyncio.CancelledError:
        pass  # task was cancelled via STOP
    finally:
        print('Stopping thread ' + tid)
        _tasks.pop(tid, None)


def _sensor_list(data, sensor_name):
    all_sensors = list(data['sensors'])
    if sensor_name == data['deviceName']:
        return all_sensors
    return [s for s in all_sensors if s['name'] == sensor_name]


async def _publish_error(client, topic_err, sensor_name, device, msg=''):
    if not msg:
        msg = 'There is no ' + sensor_name + ' sensor in device ' + device
    await client.publish(topic_err, ujson.dumps({'code': 'ERROR', 'number': 1, 'message': msg}))


async def _do_get(device, sensor_name, topic, topic_err, client, data):
    sensors_list = _sensor_list(data, sensor_name)
    try:
        if not sensors_list:
            raise Exception('Sensor not found: ' + sensor_name)
        sensor_data = {}
        for s in sensors_list:
            sensor_data[s['name']] = [getattr(sensors, s['name'])()]
        header = {'method': 'GET', 'device': device, 'sensor': sensor_name}
        payload = {'sensors': [{k: v} for k, v in sensor_data.items()]}
        await client.publish(topic, ujson.dumps({'header': header, 'payload': payload}))
    except Exception as e:
        await _publish_error(client, topic_err, sensor_name, device, str(e))


async def _do_flow(device, sensor_name, topic, topic_err, client, collect, publish, data):
    sensors_list = _sensor_list(data, sensor_name)
    try:
        if not sensors_list:
            raise Exception('Sensor not found: ' + sensor_name)
        buf = {s['name']: [] for s in sensors_list}
        t = 0
        while True:
            for s in sensors_list:
                buf[s['name']].append(getattr(sensors, s['name'])())
            t += collect
            if t >= publish:
                header = {
                    'method': 'FLOW', 'device': device, 'sensor': sensor_name,
                    'time': {'collect': collect, 'publish': publish},
                }
                payload = {'sensors': [{k: list(v)} for k, v in buf.items()]}
                await client.publish(topic, ujson.dumps({'header': header, 'payload': payload}))
                t = 0
                for name in buf:
                    buf[name] = []
            await asyncio.sleep(collect)  # yields to event loop; CancelledError exits here on STOP
    except Exception as e:
        await _publish_error(client, topic_err, sensor_name, device, str(e))


async def _do_event(device, sensor_name, topic, topic_err, client, collect):
    try:
        fn = getattr(sensors, sensor_name)
        value = fn()
        header = {'method': 'EVENT', 'device': device, 'sensor': sensor_name,
                  'time': {'collect': collect}}
        payload = {'sensors': [{sensor_name: [value]}]}
        await client.publish(topic, ujson.dumps({'header': header, 'payload': payload}))
        while True:
            await asyncio.sleep(collect)
            new_val = fn()
            if new_val != value:
                value = new_val
                payload = {'sensors': [{sensor_name: [value]}]}
                await client.publish(topic, ujson.dumps({'header': header, 'payload': payload}))
    except Exception as e:
        await _publish_error(client, topic_err, sensor_name, device, str(e))


async def _do_post(device, sensor_name, topic, topic_err, client, value):
    try:
        result = getattr(sensors, sensor_name)(value)
        header = {'method': 'POST', 'device': device, 'sensor': sensor_name, 'value': result}
        await client.publish(topic, ujson.dumps({'header': header, 'payload': {'value': result}}))
    except Exception as e:
        await _publish_error(client, topic_err, sensor_name, device, str(e))
