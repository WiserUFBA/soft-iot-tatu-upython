import ujson, utime

_client = None
_data = None
_tasks = {}

_MAX_BUF = 30    # amostras por sensor por buffer de FLOW
_RETRY_MS = 5000  # atraso antes de nova tentativa após falha de publish


def init(client, data):
    global _client, _data
    _client = client
    _data = data


def _topic(suffix):
    return (_data['topicPrefix'] + _data['deviceName'] + suffix).encode()


def _tid(method, sensor):
    return method + '_' + _data['deviceName'] + '_' + sensor


def _sensor_list(sensor_name):
    if sensor_name == _data['deviceName']:
        return list(_data['sensors'])
    return [s for s in _data['sensors'] if s['name'] == sensor_name]


def _read(name):
    import sensors
    return getattr(sensors, name)()


def _pub_err(msg):
    try:
        _client.publish(_topic(_data['topicErr']), ujson.dumps({'code': 'ERROR', 'number': 1, 'message': msg}))
    except OSError:
        raise  # falha de transporte → propaga para boot.py
    except Exception:
        pass


def _advance_deadline(deadline, period, now):
    diff = utime.ticks_diff(now, deadline)
    if diff < 0:
        return deadline
    skip = (diff // period + 1) * period
    return utime.ticks_add(deadline, skip)


def _validate_periods(collect_ms, publish_ms):
    return collect_ms > 0 and publish_ms >= collect_ms


def on_message(cfg, topic, raw_msg):
    try:
        msg = ujson.loads(raw_msg)
    except Exception:
        return
    method = msg.get('method', '')
    if not method:
        return
    if method == 'STOP':
        _do_stop(msg)
    else:
        _do_start(msg)


def _do_stop(msg):
    target = msg.get('target', 'FLOW')
    sensor = msg.get('sensor', '')
    _tasks.pop(_tid(target, sensor), None)


def _do_start(msg):
    method = msg.get('method', '')
    sensor_name = msg.get('sensor', _data['deviceName'])
    device = _data['deviceName']
    topic = _topic(_data['topicRes'])
    now = utime.ticks_ms()

    if method == 'GET':
        sl = _sensor_list(sensor_name)
        if not sl:
            _pub_err('Sensor not found: ' + sensor_name)
            return
        try:
            data = {s['name']: [_read(s['name'])] for s in sl}
            header = {'method': 'GET', 'device': device, 'sensor': sensor_name}
            payload = {'sensors': [{k: v} for k, v in data.items()]}
            _client.publish(topic, ujson.dumps({'header': header, 'payload': payload}))
        except OSError:
            raise  # falha de transporte → propaga para boot.py
        except Exception as e:
            _pub_err(str(e))

    elif method == 'FLOW':
        sl = _sensor_list(sensor_name)
        if not sl:
            _pub_err('Sensor not found: ' + sensor_name)
            return
        time_cfg = msg.get('time', {})
        try:
            collect_ms = int(time_cfg.get('collect', 1)) * 1000
            publish_ms = int(time_cfg.get('publish', time_cfg.get('collect', 1))) * 1000
        except Exception:
            _pub_err('Invalid time parameters')
            return
        if not _validate_periods(collect_ms, publish_ms):
            _pub_err('Invalid periods: collect=' + str(collect_ms // 1000) + ' publish=' + str(publish_ms // 1000))
            return
        _tasks[_tid('FLOW', sensor_name)] = {
            'method': 'FLOW', 'sensor': sensor_name, 'sl': sl,
            'collect_ms': collect_ms, 'publish_ms': publish_ms,
            'next_collect': utime.ticks_add(now, collect_ms),
            'next_publish': utime.ticks_add(now, publish_ms),
            'buf': {s['name']: [] for s in sl},
        }

    elif method == 'EVENT':
        sl = _sensor_list(sensor_name)
        if not sl:
            _pub_err('Sensor not found: ' + sensor_name)
            return
        time_cfg = msg.get('time', {})
        try:
            collect_ms = int(time_cfg.get('collect', 1)) * 1000
        except Exception:
            _pub_err('Invalid time parameters')
            return
        if collect_ms <= 0:
            _pub_err('Invalid collect period')
            return
        last = {}
        for s in sl:
            try:
                last[s['name']] = _read(s['name'])
            except Exception:
                last[s['name']] = None
        _tasks[_tid('EVENT', sensor_name)] = {
            'method': 'EVENT', 'sensor': sensor_name, 'sl': sl,
            'collect_ms': collect_ms,
            'next_collect': utime.ticks_add(now, collect_ms),
            'last': last,
        }

    elif method == 'POST':
        value = msg.get('value')
        try:
            import sensors
            fn = getattr(sensors, sensor_name)
            result = fn(value) if value is not None else fn()
            header = {'method': 'POST', 'device': device, 'sensor': sensor_name, 'value': result}
            _client.publish(topic, ujson.dumps({'header': header, 'payload': {'value': result}}))
        except OSError:
            raise  # falha de transporte → propaga para boot.py
        except Exception as e:
            _pub_err(str(e))


def _tick_flow(task, now, device, topic):
    if utime.ticks_diff(now, task['next_collect']) >= 0:
        for s in task['sl']:
            try:
                val = _read(s['name'])
                buf = task['buf'][s['name']]
                if len(buf) < _MAX_BUF:
                    buf.append(val)
            except Exception:
                pass  # falha de sensor: mantém buffer atual
        task['next_collect'] = _advance_deadline(task['next_collect'], task['collect_ms'], now)

    if utime.ticks_diff(now, task['next_publish']) >= 0:
        header = {
            'method': 'FLOW', 'device': device, 'sensor': task['sensor'],
            'time': {'collect': task['collect_ms'] // 1000, 'publish': task['publish_ms'] // 1000},
        }
        payload = {'sensors': [{k: list(v)} for k, v in task['buf'].items()]}
        try:
            _client.publish(topic, ujson.dumps({'header': header, 'payload': payload}))
        except OSError:
            # falha de transporte: atrasa próxima tentativa e propaga
            task['next_publish'] = utime.ticks_add(now, _RETRY_MS)
            raise
        task['next_publish'] = _advance_deadline(task['next_publish'], task['publish_ms'], now)
        for name in task['buf']:
            task['buf'][name] = []


def _tick_event(task, now, device, topic):
    if utime.ticks_diff(now, task['next_collect']) >= 0:
        new_vals = {}
        changed = False
        for s in task['sl']:
            try:
                val = _read(s['name'])
                new_vals[s['name']] = val
                if val != task['last'].get(s['name']):
                    changed = True
            except Exception:
                new_vals[s['name']] = task['last'].get(s['name'])

        if changed:
            task['last'] = new_vals
            header = {
                'method': 'EVENT', 'device': device, 'sensor': task['sensor'],
                'time': {'collect': task['collect_ms'] // 1000},
            }
            payload = {'sensors': [{k: [v]} for k, v in new_vals.items()]}
            try:
                _client.publish(topic, ujson.dumps({'header': header, 'payload': payload}))
            except OSError:
                task['next_collect'] = utime.ticks_add(now, _RETRY_MS)
                raise

        task['next_collect'] = _advance_deadline(task['next_collect'], task['collect_ms'], now)


def tick():
    now = utime.ticks_ms()
    device = _data['deviceName']
    topic = _topic(_data['topicRes'])

    for task in list(_tasks.values()):
        try:
            if task['method'] == 'FLOW':
                _tick_flow(task, now, device, topic)
            elif task['method'] == 'EVENT':
                _tick_event(task, now, device, topic)
        except OSError:
            raise  # falha de transporte → boot.py incrementa _dead_count e reconecta
        except Exception:
            pass   # falha de sensor ou encoding → ignora esta tarefa
