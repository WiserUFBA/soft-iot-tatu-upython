# soft-iot-tatu-upython

MicroPython implementation of the TATU protocol for ESP8266 devices.

TATU is a lightweight IoT protocol built on top of MQTT that lets a gateway or broker send commands to embedded devices to read sensors (GET, FLOW, EVENT) and write actuators (POST), and stop ongoing operations (STOP).

This repository contains two implementations:

| | `src/tatu/` | `src/tatu-async/` |
|--|-------------|-------------------|
| Concurrency | `_thread` (preemptive) | `uasyncio` (cooperative) |
| MQTT library | `umqtt.robust` | `mqtt_as` (Peter Hinch) |
| WiFi reconnection | manual | automatic (via `mqtt_as`) |
| STOP mechanism | `StopEvent` (polling) | `task.cancel()` (immediate) |
| RAM usage | slightly higher (locks + StopEvent) | slightly lower (no locks) |
| ESP8266 support | yes (~2–3 concurrent ops) | yes (~4–6 concurrent ops) |
| Maturity | stable | experimental |

From the **protocol perspective both versions are identical** — same `config.json` format, same MQTT topics, same JSON request/response structure. The same `sensors.py` works with both versions.

---

## Requirements

### Hardware
- **ESP8266** (WeMos D1 Mini / NodeMCU) — the target hardware for this project
- Grove Shield for ESP8266 — used with Grove sensors (DHT22, Light v1.2)

### Software
- [MicroPython](https://micropython.org/download/) ≥ 1.19 for ESP8266
- An MQTT broker reachable from the device (e.g. Mosquitto)
- One of these tools to upload files to the device:
  - [`mpremote`](https://docs.micropython.org/en/latest/reference/mpremote.html) (recommended)
  - [`ampy`](https://github.com/scientifichackers/ampy)
  - [Thonny IDE](https://thonny.org/) (GUI)

---

## Quick start — thread version (`src/tatu/`)

### 1. Flash MicroPython

Download the firmware for your board from https://micropython.org/download/ and flash it:

```bash
esptool.py --chip esp8266 erase_flash
esptool.py --chip esp8266 --baud 460800 write_flash --flash_size=detect 0 esp8266-*.bin
```

### 2. Install the MQTT library

Connect to the device REPL (via `mpremote connect` or Thonny) and run once:

```python
import mip
mip.install('umqtt.robust')
```

This requires the device to be connected to WiFi first. Alternatively, copy `umqtt.simple` and `umqtt.robust` manually from the [micropython-lib](https://github.com/micropython/micropython-lib) repository.

### 3. Configure the device

Edit `src/tatu/config.json` with your network and broker settings (see [Configuration](#configuration)).

### 4. Implement your sensors

Copy the appropriate example from `examples/` to `sensors.py` (see [Sensor examples](#sensor-examples)), or edit `src/tatu/sensors.py` directly.

### 5. Upload the files

```bash
mpremote connect /dev/ttyUSB0 cp examples/sensors_esp8266_grove.py :sensors.py
mpremote connect /dev/ttyUSB0 cp src/tatu/config.json :config.json
mpremote connect /dev/ttyUSB0 cp src/tatu/tatu.py :tatu.py
mpremote connect /dev/ttyUSB0 cp src/tatu/boot.py :boot.py
```

On Windows, replace `/dev/ttyUSB0` with the appropriate COM port (e.g. `COM3`).

### 6. Reset the device

```bash
mpremote connect /dev/ttyUSB0 reset
```

The device will connect to WiFi, subscribe to its MQTT topic, and wait for commands.

---

## Quick start — uasyncio version (`src/tatu-async/`)

### 1. Flash MicroPython

Same as the thread version above.

### 2. Install `mqtt_as`

`mqtt_as` is an async MQTT library by Peter Hinch that also manages WiFi reconnection automatically. It is not available via `mip`, so you need to download it manually:

1. Download [`mqtt_as.py`](https://raw.githubusercontent.com/peterhinch/micropython-mqtt/master/mqtt_as/mqtt_as.py) from the [micropython-mqtt](https://github.com/peterhinch/micropython-mqtt) repository.
2. Upload it to the device:

```bash
mpremote connect /dev/ttyUSB0 cp mqtt_as.py :mqtt_as.py
```

### 3. Configure the device

Edit `src/tatu-async/config.json` — the format is identical to the thread version.

### 4. Implement your sensors

Same `sensors.py` as the thread version — copy the appropriate example from `examples/`.

### 5. Upload the files

```bash
mpremote connect /dev/ttyUSB0 cp examples/sensors_esp8266_grove.py :sensors.py
mpremote connect /dev/ttyUSB0 cp src/tatu-async/config.json :config.json
mpremote connect /dev/ttyUSB0 cp src/tatu-async/tatu.py :tatu.py
mpremote connect /dev/ttyUSB0 cp src/tatu-async/boot.py :boot.py
```

### 6. Reset the device

```bash
mpremote connect /dev/ttyUSB0 reset
```

`mqtt_as` handles WiFi connection and MQTT reconnection automatically — no separate WiFi setup step is needed.

---

## Configuration

The `config.json` format is the same for both versions:

```json
{
    "deviceName": "esp8266-grove-01",
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
        {"type": "float", "name": "humiditySensor"},
        {"type": "integer", "name": "lightSensor"}
    ]
}
```

| Field | Description |
|-------|-------------|
| `deviceName` | Unique identifier for the device. Used in MQTT topics. Convention: `esp8266-<id>`. |
| `ssid` / `ssidPassword` | WiFi credentials. |
| `mqttBroker` | IP address or hostname of the MQTT broker. |
| `mqttPort` | MQTT broker port. Default: `1883`. |
| `mqttUsername` / `mqttPassword` | MQTT credentials. Leave empty if the broker has no auth. |
| `topicPrefix` | Prefix for all topics. Default: `"dev/"`. |
| `topicReq` | Suffix for the request topic. The device subscribes to `{topicPrefix}{deviceName}{topicReq}/#`. |
| `topicRes` | Suffix for the response topic. The device publishes sensor data here. |
| `topicErr` | Suffix for the error topic. The device publishes error messages here. |
| `sensors` | List of sensor/actuator functions available on this device. Each `name` must match a function in `sensors.py`. |

With the default config, the topics are:
- Subscribe: `dev/esp8266-grove-01/REQ/#`
- Publish responses: `dev/esp8266-grove-01/RES`
- Publish errors: `dev/esp8266-grove-01/ERR`

---

## Adding sensors

Edit `sensors.py`. Each function name must match an entry in the `sensors` list in `config.json`. The same `sensors.py` works with both the thread and uasyncio versions.

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

Ready-to-use `sensors.py` files are in the [`examples/`](examples/) folder:

| Arquivo | Hardware | Sensores / variáveis TATU | Notas |
|---------|----------|---------------------------|-------|
| [`src/tatu/sensors.py`](src/tatu/sensors.py) | Any ESP8266 | DHT11 on GPIO15 → `temperatureSensor`, `humiditySensor` | Default — integer values |
| [`examples/sensors_dht22.py`](examples/sensors_dht22.py) | Any ESP8266 | DHT22 on GPIO15 → `temperatureSensor`, `humiditySensor` | Float values, higher precision |
| [`examples/sensors_esp8266_grove.py`](examples/sensors_esp8266_grove.py) | ESP8266 + Grove Shield (WeMos D1 Mini) | DHT22 on D4/GPIO2 → `temperatureSensor`, `humiditySensor`; Light on A0 → `lightSensor` | Pronto para uso com Grove Shield; funciona tanto na versão thread quanto async |

To use an example, copy it to the device as `sensors.py`:

```bash
# ESP8266 + Grove Shield (WeMos D1 Mini) — recomendado para este projeto
mpremote connect /dev/ttyUSB0 cp examples/sensors_esp8266_grove.py :sensors.py

# Generic DHT22 (GPIO15)
mpremote connect /dev/ttyUSB0 cp examples/sensors_dht22.py :sensors.py
```

**DHT11 vs DHT22:**

| | DHT11 | DHT22 |
|--|-------|-------|
| Temperature range | 0–50 °C ±2 °C | -40–80 °C ±0.5 °C |
| Humidity range | 20–90 % ±5 % | 0–100 % ±2-5 % |
| Return type | `int` | `float` |
| MicroPython class | `dht.DHT11` | `dht.DHT22` |
| Minimum read interval | 2 s | 2 s |

Both use the same wiring: VCC (3.3 V), GND, DATA + 10 kΩ pull-up resistor on DATA (the Grove Shield already includes the pull-up).

---

## TATU protocol reference

All requests are JSON published to `{topicPrefix}{deviceName}{topicReq}/...`.  
All responses are JSON published to `{topicPrefix}{deviceName}{topicRes}`.  
Errors are published to `{topicPrefix}{deviceName}{topicErr}`.

The protocol is identical between the thread and uasyncio versions.

### GET — one-shot read

Request:
```json
{"method": "GET", "sensor": "temperatureSensor"}
```

Response:
```json
{
  "header": {"method": "GET", "device": "esp8266-grove-01", "sensor": "temperatureSensor"},
  "payload": {"sensors": [{"temperatureSensor": [25]}]}
}
```

Use `"sensor": "esp8266-grove-01"` (the device name) to read **all** sensors at once.

---

### FLOW — periodic collection

Collects values every `collect` seconds and publishes a batch every `publish` seconds.

Request:
```json
{"method": "FLOW", "sensor": "temperatureSensor", "time": {"collect": 5, "publish": 30}}
```

Response (published every `publish` seconds):
```json
{
  "header": {
    "method": "FLOW", "device": "esp8266-grove-01", "sensor": "temperatureSensor",
    "time": {"collect": 5, "publish": 30}
  },
  "payload": {"sensors": [{"temperatureSensor": [24, 25, 25, 26, 25, 25]}]}
}
```

Runs continuously until a STOP command is received.

---

### EVENT — change detection

Polls the sensor every `collect` seconds and publishes only when the value changes.

Request:
```json
{"method": "EVENT", "sensor": "lightSensor", "time": {"collect": 1}}
```

Response (published on each value change):
```json
{
  "header": {"method": "EVENT", "device": "esp8266-grove-01", "sensor": "lightSensor", "time": {"collect": 1}},
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
  "header": {"method": "POST", "device": "esp8266-grove-01", "sensor": "ledActuator", "value": true},
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

In the thread version, STOP sets a flag that the thread checks on the next sleep cycle. In the uasyncio version, STOP calls `task.cancel()`, which interrupts the coroutine at the next `await asyncio.sleep()` immediately.

---

### Error response

Published to the error topic when a sensor function fails or is not found:
```json
{"code": "ERROR", "number": 1, "message": "Sensor not found: unknownSensor"}
```

---

## Platform notes

### ESP8266
Supported on both versions. RAM is limited (~25–30 KB heap available after WiFi + MQTT).

- **Thread version**: practical limit of ~2–3 concurrent FLOW/EVENT operations. All threads share a single MQTT publisher connection to minimize RAM usage.
- **uasyncio version**: cooperative scheduling has lower overhead per concurrent operation, raising the practical limit to ~4–6.

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
- [micropython-mqtt / mqtt_as](https://github.com/peterhinch/micropython-mqtt) — async MQTT library used by the uasyncio version
- [MicroPython documentation](https://docs.micropython.org/en/latest/)
- [umqtt library](https://github.com/micropython/micropython-lib/tree/master/micropython/umqtt.simple)
