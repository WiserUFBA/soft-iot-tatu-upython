# soft-iot-tatu-upython

MicroPython implementation of the TATU protocol for ESP8266 devices.

TATU is a lightweight IoT protocol built on top of MQTT that lets a gateway or broker send commands to embedded devices to read sensors (GET, FLOW, EVENT) and write actuators (POST), and stop ongoing operations (STOP).

This implementation uses a **polling/tasks loop** — no threads, no uasyncio. `boot.py` drives a single tight loop calling `client.check_msg()` and `tatu.tick()` every 200 ms; `tatu.py` manages all active tasks using timestamps and a dict, with no blocking calls.

> **Why not `_thread` or `uasyncio`?**
> `_thread` on MicroPython/ESP8266 is not stable under concurrent MQTT + sensor workloads — it causes hard crashes.
> `uasyncio` with `mqtt_as` exceeds the available heap (~25 KB) when WiFi and MQTT stacks are active, causing `MemoryError` on startup.
> The polling loop avoids both issues and has been validated on hardware at IC/UFBA.

---

## Requirements

### Hardware
- **ESP8266** (WeMos D1 Mini / NodeMCU)
- Grove Shield for ESP8266 — used with Grove sensors (DHT22, Light v1.2)

### Software
- [MicroPython](https://micropython.org/download/ESP8266_GENERIC/) ≥ 1.24.1 for ESP8266
- `umqtt.simple` — ships with MicroPython, no extra install needed
- An MQTT broker reachable from the device (e.g. Mosquitto)
- One of these tools to upload files to the device:
  - [`mpremote`](https://docs.micropython.org/en/latest/reference/mpremote.html) (recommended)
  - [`ampy`](https://github.com/scientifichackers/ampy)
  - [Thonny IDE](https://thonny.org/) (GUI)

---

## Quick start

### 1. Flash MicroPython

Download `ESP8266_GENERIC-*.bin` from https://micropython.org/download/ESP8266_GENERIC/ and flash:

```bash
esptool --chip esp8266 erase_flash
esptool --chip esp8266 --flash-mode dout --flash-size 4MB write_flash 0 ESP8266_GENERIC-*.bin
```

> **Note:** `--flash-mode dout` is required on most ESP8266 modules. Using the default `dio` causes a crash loop on boot.

### 2. Configure the device

Edit `src/tatu/config.json` with your network and broker settings (see [Configuration](#configuration)).

### 3. Implement your sensors

Copy the appropriate example from `examples/` to `sensors.py` (see [Sensor examples](#sensor-examples)), or edit `src/tatu/sensors.py` directly.

### 4. Upload the files

```bash
mpremote connect /dev/ttyUSB0 cp examples/sensors_esp8266_grove.py :sensors.py
mpremote connect /dev/ttyUSB0 cp src/tatu/config.json :config.json
mpremote connect /dev/ttyUSB0 cp src/tatu/tatu.py :tatu.py
mpremote connect /dev/ttyUSB0 cp src/tatu/boot.py :boot.py
```

On Windows, replace `/dev/ttyUSB0` with the COM port (e.g. `COM3`).

### 5. Reset the device

```bash
mpremote connect /dev/ttyUSB0 reset
```

The device connects to WiFi, subscribes to its MQTT request topic, and waits for commands. The shell output shows the IP address, heap free, and broker reachability before the main loop starts.

---

## Configuration

```json
{
    "deviceName": "esp8266-01",
    "ssid": "your-wifi-ssid",
    "ssidPassword": "your-wifi-password",
    "mqttBroker": "192.168.1.100",
    "mqttPort": 1883,
    "mqttUsername": "",
    "mqttPassword": "",
    "topicPrefix": "dev/",
    "topicReq": "/REQ",
    "topicRes": "/RES",
    "topicErr": "/ERR",
    "sensors": [
        {"type": "float", "name": "temperatureSensor"},
        {"type": "float", "name": "humiditySensor"}
    ]
}
```

| Field | Description |
|-------|-------------|
| `deviceName` | Unique identifier for the device. Used in MQTT topics. Convention: `esp8266-<id>`. |
| `ssid` / `ssidPassword` | WiFi credentials. Hidden SSIDs are supported. |
| `mqttBroker` | IP address or hostname of the MQTT broker. |
| `mqttPort` | MQTT broker port. Default: `1883`. |
| `mqttUsername` / `mqttPassword` | MQTT credentials. Leave empty if the broker has no auth. |
| `topicPrefix` | Prefix for all topics. Default: `"dev/"`. |
| `topicReq` | Suffix for the request topic. The device subscribes to `{topicPrefix}{deviceName}{topicReq}/#`. |
| `topicRes` | Suffix for the response topic. The device publishes sensor data here. |
| `topicErr` | Suffix for the error topic. The device publishes error messages here. |
| `sensors` | List of sensor/actuator functions available on this device. Each `name` must match a function in `sensors.py`. |

With the default config, the topics are:
- Subscribe: `dev/esp8266-01/REQ/#`
- Publish responses: `dev/esp8266-01/RES`
- Publish errors: `dev/esp8266-01/ERR`

---

## Adding sensors

Edit `sensors.py`. Each function name must match an entry in the `sensors` list in `config.json`.

**Sensor (read-only):** return a value.

```python
from machine import Pin, ADC

_adc = ADC(0)

def lightSensor():
    return _adc.read()
```

**Actuator (write):** accept an optional value, apply it, return the result.

```python
from machine import Pin

_led = Pin(2, Pin.OUT)

def ledActuator(value=None):
    if value is not None:
        _led.value(1 if value else 0)
    return bool(_led.value())
```

### Sensor examples

| File | Hardware | TATU variables | Notes |
|------|----------|----------------|-------|
| [`src/tatu/sensors.py`](src/tatu/sensors.py) | Any ESP8266 | DHT22 on GPIO12 (D6) → `temperatureSensor`, `humiditySensor` | Default — float values; cache expires after 30 s without a valid read |
| [`examples/sensors_dht22.py`](examples/sensors_dht22.py) | Any ESP8266 | DHT22 on GPIO15 → `temperatureSensor`, `humiditySensor` | Float values, higher precision |
| [`examples/sensors_esp8266_grove.py`](examples/sensors_esp8266_grove.py) | ESP8266 + Grove Shield (WeMos D1 Mini) | DHT22 on D4/GPIO2 → `temperatureSensor`, `humiditySensor`; Light on A0 → `lightSensor` | Ready for Grove Shield |

To use an example, copy it to the device as `sensors.py`:

```bash
# ESP8266 + Grove Shield (WeMos D1 Mini)
mpremote connect /dev/ttyUSB0 cp examples/sensors_esp8266_grove.py :sensors.py

# Generic DHT22 (GPIO15)
mpremote connect /dev/ttyUSB0 cp examples/sensors_dht22.py :sensors.py
```

**DHT11 vs DHT22:**

| | DHT11 | DHT22 |
|--|-------|-------|
| Temperature range | 0–50 °C ±2 °C | -40–80 °C ±0.5 °C |
| Humidity range | 20–90 % ±5 % | 0–100 % ±2–5 % |
| Return type | `int` | `float` |
| MicroPython class | `dht.DHT11` | `dht.DHT22` |
| Minimum read interval | 2 s | 2 s |

Both use the same wiring: VCC (3.3 V), GND, DATA + 10 kΩ pull-up resistor on DATA (the Grove Shield already includes the pull-up).

---

## TATU protocol reference

All requests are JSON published to `{topicPrefix}{deviceName}{topicReq}/...`.
All responses are JSON published to `{topicPrefix}{deviceName}{topicRes}`.
Errors are published to `{topicPrefix}{deviceName}{topicErr}`.

### GET — one-shot read

Request:
```json
{"method": "GET", "sensor": "temperatureSensor"}
```

Response:
```json
{
  "header": {"method": "GET", "device": "esp8266-01", "sensor": "temperatureSensor"},
  "payload": {"sensors": [{"temperatureSensor": [24.2]}]}
}
```

Use `"sensor": "esp8266-01"` (the device name) to read **all** sensors at once.

---

### FLOW — periodic collection

Collects values every `collect` seconds and publishes a batch every `publish` seconds.

**Constraints:** `collect` and `publish` must be positive integers, and `publish` must be ≥ `collect`. Invalid values produce an error on `/ERR` and the task is not created.

Request:
```json
{"method": "FLOW", "sensor": "temperatureSensor", "time": {"collect": 5, "publish": 30}}
```

Response (published every `publish` seconds):
```json
{
  "header": {
    "method": "FLOW", "device": "esp8266-01", "sensor": "temperatureSensor",
    "time": {"collect": 5, "publish": 30}
  },
  "payload": {"sensors": [{"temperatureSensor": [24.2, 24.5, 24.5, 24.8, 24.5, 24.5]}]}
}
```

Runs continuously until a STOP command is received.

---

### EVENT — change detection

Polls the sensor every `collect` seconds and publishes only when the value changes.

**Constraints:** `collect` must be a positive integer. Invalid values produce an error on `/ERR` and the task is not created.

Request:
```json
{"method": "EVENT", "sensor": "lightSensor", "time": {"collect": 1}}
```

Response (published on each value change):
```json
{
  "header": {"method": "EVENT", "device": "esp8266-01", "sensor": "lightSensor", "time": {"collect": 1}},
  "payload": {"sensors": [{"lightSensor": [842]}]}
}
```

Runs continuously until a STOP command is received.

---

### POST — actuator write

Request:
```json
{"method": "POST", "sensor": "ledActuator", "value": true}
```

Response:
```json
{
  "header": {"method": "POST", "device": "esp8266-01", "sensor": "ledActuator", "value": true},
  "payload": {"value": true}
}
```

---

### STOP — stop an ongoing operation

Stops a running FLOW or EVENT operation.

Request:
```json
{"method": "STOP", "sensor": "temperatureSensor", "target": "FLOW"}
```

- `target`: the method to stop (`"FLOW"` or `"EVENT"`). Defaults to `"FLOW"` if omitted.
- `sensor`: must match the sensor name used in the original FLOW/EVENT request.

---

### Error response

Published to the error topic when a sensor function fails or is not found:
```json
{"code": "ERROR", "number": 1, "message": "Sensor not found: unknownSensor"}
```

---

## Platform notes

### ESP8266 RAM budget

After WiFi + MQTT connect, heap available is ~25–30 KB. The polling loop is designed to minimize allocations: it uses a single `MQTTClient` from `umqtt.simple`, calls `client.check_msg()` non-blocking each iteration, and runs `tatu.tick()` to advance all active tasks.

Practical limit: **4–6 concurrent FLOW/EVENT tasks** before heap pressure causes instability.

### Reconnection

`boot.py` implements automatic reconnection at two points:

- **Boot time:** `_boot_connect()` retries WiFi + MQTT with exponential backoff (2 s → 4 → 8 → … → 30 s cap) until the device is connected. The device never halts on a failed first connection.
- **Runtime:** if 3 consecutive loop errors are detected, or a keepalive ping fails, the WiFi + MQTT connect sequence is re-run without rebooting the device. Active FLOW and EVENT tasks survive reconnection; their deadlines are advanced to skip missed periods.

### Hidden SSIDs

`network.WLAN.connect()` on MicroPython supports hidden SSIDs natively — no extra configuration needed.

### Installing files with ampy (alternative to mpremote)

```bash
ampy --port /dev/ttyUSB0 put examples/sensors_esp8266_grove.py /sensors.py
ampy --port /dev/ttyUSB0 put src/tatu/config.json /config.json
ampy --port /dev/ttyUSB0 put src/tatu/tatu.py /tatu.py
ampy --port /dev/ttyUSB0 put src/tatu/boot.py /boot.py
```

---

## Related projects

- [soft-iot-tatu-python](https://github.com/WiserUFBA/soft-iot-tatu-python) — CPython version (Raspberry Pi, PC)
- [MicroPython documentation](https://docs.micropython.org/en/latest/)
- [umqtt library](https://github.com/micropython/micropython-lib/tree/master/micropython/umqtt.simple)
