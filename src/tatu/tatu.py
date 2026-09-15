import ujson, utime

_client = None
_data = None
_tasks = {}

_MAX_BUF = 30    # amostras por sensor por buffer de FLOW/EVENT janela
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


def _pub_err(code, message=''):
    try:
        payload = {'code': code}
        if message:
            payload['message'] = message
        _client.publish(_topic(_data['topicErr']), ujson.dumps(payload))
    except OSError:
        raise
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


def _new_metrics(now):
    return {
        'created_at': now,
        'last_collect': 0,
        'last_publish': 0,
        'samples': 0,
        'dropped': 0,
        'errors': 0,
        'total_errors': 0,
    }


def on_message(raw_msg):
    try:
        msg = ujson.loads(raw_msg)
    except Exception:
        return
    method = msg.get('method', '')
    if not method:
        return
    if method == 'STOP':
        _do_stop(msg)
    elif method in ('GET', 'FLOW', 'EVENT', 'POST'):
        _do_start(msg)
    else:
        _pub_err('UNKNOWN_METHOD', method)


def _do_stop(msg):
    target = msg.get('target', 'FLOW')
    sensor = msg.get('sensor', '')
    if not sensor:
        _pub_err('INVALID_PARAMS', 'STOP requires sensor field')
        return
    tid = _tid(target, sensor)
    if tid not in _tasks:
        _pub_err('STOP_NOT_FOUND', target + ' not found for sensor: ' + sensor)
        return
    _tasks.pop(tid)


def _do_start(msg):
    method = msg.get('method', '')
    sensor_name = msg.get('sensor', _data['deviceName'])
    device = _data['deviceName']
    topic = _topic(_data['topicRes'])
    now = utime.ticks_ms()

    if method == 'GET':
        sl = _sensor_list(sensor_name)
        if not sl:
            _pub_err('SENSOR_NOT_FOUND', sensor_name)
            return
        try:
            data = {s['name']: [_read(s['name'])] for s in sl}
            header = {'method': 'GET', 'device': device, 'sensor': sensor_name}
            payload = {'sensors': [{k: v} for k, v in data.items()]}
            _client.publish(topic, ujson.dumps({'header': header, 'payload': payload}))
        except OSError:
            raise
        except Exception as e:
            _pub_err('SENSOR_READ_ERROR', str(e))

    elif method == 'FLOW':
        sl = _sensor_list(sensor_name)
        if not sl:
            _pub_err('SENSOR_NOT_FOUND', sensor_name)
            return
        time_cfg = msg.get('time', {})
        try:
            collect_ms = int(time_cfg.get('collect', 1)) * 1000
            publish_ms = int(time_cfg.get('publish', time_cfg.get('collect', 1))) * 1000
        except Exception:
            _pub_err('INVALID_PARAMS', 'Invalid time parameters')
            return
        if not _validate_periods(collect_ms, publish_ms):
            _pub_err('INVALID_PARAMS', 'collect=' + str(collect_ms // 1000) + ' publish=' + str(publish_ms // 1000))
            return
        task = _new_metrics(now)
        task.update({
            'method': 'FLOW', 'sensor': sensor_name, 'sl': sl,
            'collect_ms': collect_ms, 'publish_ms': publish_ms,
            'next_collect': utime.ticks_add(now, collect_ms),
            'next_publish': utime.ticks_add(now, publish_ms),
            'buf': {s['name']: [] for s in sl},
        })
        _tasks[_tid('FLOW', sensor_name)] = task

    elif method == 'EVENT':
        sl = _sensor_list(sensor_name)
        if not sl:
            _pub_err('SENSOR_NOT_FOUND', sensor_name)
            return
        time_cfg = msg.get('time', {})
        try:
            collect_ms = int(time_cfg.get('collect', 1)) * 1000
            publish_ms = int(time_cfg.get('publish', 0)) * 1000
        except Exception:
            _pub_err('INVALID_PARAMS', 'Invalid time parameters')
            return
        if collect_ms <= 0:
            _pub_err('INVALID_PARAMS', 'collect must be > 0')
            return
        if publish_ms > 0 and publish_ms < collect_ms:
            _pub_err('INVALID_PARAMS', 'publish must be >= collect')
            return
        last = {}
        for s in sl:
            try:
                last[s['name']] = _read(s['name'])
            except Exception:
                last[s['name']] = None
        task = _new_metrics(now)
        task.update({
            'method': 'EVENT', 'sensor': sensor_name, 'sl': sl,
            'collect_ms': collect_ms,
            'publish_ms': publish_ms,
            'next_collect': utime.ticks_add(now, collect_ms),
            'next_publish': utime.ticks_add(now, publish_ms) if publish_ms > 0 else 0,
            'buf': {s['name']: [] for s in sl} if publish_ms > 0 else None,
            'last': last,
        })
        _tasks[_tid('EVENT', sensor_name)] = task
        # publica valor inicial como referência
        initial = {k: v for k, v in last.items() if v is not None}
        if initial:
            try:
                header = {
                    'method': 'EVENT', 'device': device, 'sensor': sensor_name,
                    'time': {'collect': collect_ms // 1000, 'publish': publish_ms // 1000},
                }
                payload = {'sensors': [{k: [v]} for k, v in initial.items()]}
                _client.publish(topic, ujson.dumps({'header': header, 'payload': payload}))
            except OSError:
                raise
            except Exception:
                pass

    elif method == 'POST':
        value = msg.get('value')
        try:
            import sensors
            fn = getattr(sensors, sensor_name)
            result = fn(value) if value is not None else fn()
            header = {'method': 'POST', 'device': device, 'sensor': sensor_name, 'value': result}
            _client.publish(topic, ujson.dumps({'header': header, 'payload': {'value': result}}))
        except OSError:
            raise
        except Exception as e:
            _pub_err('SENSOR_READ_ERROR', str(e))


def _tick_flow(task, now, device, topic):
    if utime.ticks_diff(now, task['next_collect']) >= 0:
        for s in task['sl']:
            try:
                val = _read(s['name'])
                buf = task['buf'][s['name']]
                if len(buf) < _MAX_BUF:
                    buf.append(val)
                    task['samples'] += 1
                else:
                    task['dropped'] += 1
            except Exception:
                pass
        task['last_collect'] = now
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
            task['errors'] += 1
            task['total_errors'] += 1
            task['next_publish'] = utime.ticks_add(now, _RETRY_MS)
            raise
        task['last_publish'] = now
        task['errors'] = 0
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
            task['samples'] += 1
            if task['publish_ms'] == 0:
                # modo imediato: publica na mudança
                header = {
                    'method': 'EVENT', 'device': device, 'sensor': task['sensor'],
                    'time': {'collect': task['collect_ms'] // 1000, 'publish': 0},
                }
                payload = {'sensors': [{k: [v]} for k, v in new_vals.items()]}
                try:
                    _client.publish(topic, ujson.dumps({'header': header, 'payload': payload}))
                except OSError:
                    task['errors'] += 1
                    task['total_errors'] += 1
                    task['next_collect'] = utime.ticks_add(now, _RETRY_MS)
                    raise
                task['last_publish'] = now
                task['errors'] = 0
            else:
                # modo janela: bufferiza só os que mudaram
                for k, v in new_vals.items():
                    buf = task['buf'][k]
                    if len(buf) < _MAX_BUF:
                        buf.append(v)
                    else:
                        task['dropped'] += 1

        task['last_collect'] = now
        task['next_collect'] = _advance_deadline(task['next_collect'], task['collect_ms'], now)

    if task['publish_ms'] > 0 and utime.ticks_diff(now, task['next_publish']) >= 0:
        has_data = any(task['buf'][s['name']] for s in task['sl'])
        if has_data:
            header = {
                'method': 'EVENT', 'device': device, 'sensor': task['sensor'],
                'time': {'collect': task['collect_ms'] // 1000, 'publish': task['publish_ms'] // 1000},
            }
            payload = {'sensors': [{k: list(v)} for k, v in task['buf'].items()]}
            try:
                _client.publish(topic, ujson.dumps({'header': header, 'payload': payload}))
            except OSError:
                task['errors'] += 1
                task['total_errors'] += 1
                task['next_publish'] = utime.ticks_add(now, _RETRY_MS)
                raise
            task['last_publish'] = now
            task['errors'] = 0
            for name in task['buf']:
                task['buf'][name] = []
        task['next_publish'] = _advance_deadline(task['next_publish'], task['publish_ms'], now)


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
            raise
        except Exception:
            pass
