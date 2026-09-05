# soft-iot-tatu-upython

MicroPython implementation of the TATU protocol for ESP32 and ESP8266 devices.

TATU is a lightweight IoT protocol built on top of MQTT that lets a gateway or broker send commands to embedded devices to read sensors (GET, FLOW, EVENT) and write actuators (POST), and stop ongoing operations (STOP).

---

## Requirements

### Hardware
- **ESP32** (recommended) — more RAM, better thread support
- **ESP8266** — supported, but limited to ~2–3 concurrent operations (see [Platform notes](#platform-notes))

### Software
- [MicroPython](https://micropython.org/download/) ≥ 1.19 for ESP32/ESP8266
- An MQTT broker reachable from the device (e.g. Mosquitto)
- One of these tools to upload files to the device:
  - [`mpremote`](https://docs.micropython.org/en/latest/reference/mpremote.html) (recommended)
  - [`ampy`](https://github.com/scientifichackers/ampy)
  - [Thonny IDE](https://thonny.org/) (GUI)

---

## Quick start

### 1. Flash MicroPython

Download the firmware for your board from https://micropython.org/download/ and flash it. Example with `esptool`:

**ESP32:**
```bash
esptool.py --chip esp32 erase_flash
esptool.py --chip esp32 --baud 460800 write_flash -z 0x1000 esp32-*.bin
```

**ESP8266:**
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

This requires the device to be connected to WiFi first. Alternatively, install `umqtt.simple` and `umqtt.robust` manually by copying the files from the [micropython-lib](https://github.com/micropython/micropython-lib) repository.

### 3. Configure the device

Edit `src/tatu/config.json` with your network and broker settings (see [Configuration](#configuration)).

### 4. Implement your sensors

Edit `src/tatu/sensors.py` to add functions for your hardware (see [Adding sensors](#adding-sensors)).

### 5. Upload the files

```bash
mpremote connect /dev/ttyUSB0 cp src/tatu/config.json :config.json
mpremote connect /dev/ttyUSB0 cp src/tatu/sensors.py :sensors.py
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

## Configuration

`src/tatu/config.json`:

```json
{
    "deviceName": "esp32-01",
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
        {"type": "integer", "name": "humiditySensor"},
        {"type": "integer", "name": "temperatureSensor"}
    ]
}
```

| Field | Description |
|-------|-------------|
| `deviceName` | Unique identifier for the device. Used in MQTT topics. |
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
- Subscribe: `dev/esp32-01/REQ/#`
- Publish responses: `dev/esp32-01/RES`
- Publish errors: `dev/esp32-01/ERR`

---

## Adding sensors

Edit `src/tatu/sensors.py`. Each function name must match an entry in the `sensors` list in `config.json`.

**Sensor (read-only):** return a value.

```python
from machine import Pin, ADC

_adc = ADC(Pin(34))
_adc.atten(ADC.ATTN_11DB)

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

| File | Sensor | Notes |
|------|--------|-------|
| [`src/tatu/sensors.py`](src/tatu/sensors.py) | DHT11 on GPIO 15 | Integer values |
| [`examples/sensors_dht22.py`](examples/sensors_dht22.py) | DHT22 on GPIO 15 | Float values, higher precision |

To use an example, copy it to the device as `sensors.py`:
```bash
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

Both use the same wiring: VCC (3.3 V), GND, DATA + 10 kΩ pull-up resistor on DATA.

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
  "header": {"method": "GET", "device": "esp32-01", "sensor": "temperatureSensor"},
  "payload": {"sensors": [{"temperatureSensor": [25]}]}
}
```

Use `"sensor": "esp32-01"` (the device name) to read **all** sensors at once.

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
    "method": "FLOW", "device": "esp32-01", "sensor": "temperatureSensor",
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
  "header": {"method": "EVENT", "device": "esp32-01", "sensor": "lightSensor", "time": {"collect": 1}},
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
  "header": {"method": "POST", "device": "esp32-01", "sensor": "ledActuator", "value": true},
  "payload": {"value": true}
}
```

---

### STOP — stop an ongoing operation

Stops a running FLOW or EVENT thread.

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

### ESP32
Full support for all features. Multiple concurrent FLOW/EVENT operations work reliably.

### ESP8266
Supported, but RAM is limited (~25–30 KB heap available after WiFi + MQTT). Practical limit is **2–3 concurrent operations** (FLOW/EVENT running simultaneously). GET and POST are one-shot and barely count toward the limit.

All threads share a single MQTT publisher connection to minimize RAM usage (one TCP connection instead of one per thread).

### Installing files with ampy (alternative to mpremote)

```bash
ampy --port /dev/ttyUSB0 put src/tatu/config.json /config.json
ampy --port /dev/ttyUSB0 put src/tatu/sensors.py /sensors.py
ampy --port /dev/ttyUSB0 put src/tatu/tatu.py /tatu.py
ampy --port /dev/ttyUSB0 put src/tatu/boot.py /boot.py
```

---

## Related projects

- [soft-iot-tatu-python](https://github.com/WiserUFBA/soft-iot-tatu-python) — CPython version (Raspberry Pi, PC)
- [MicroPython documentation](https://docs.micropython.org/en/latest/)
- [umqtt library](https://github.com/micropython/micropython-lib/tree/master/micropython/umqtt.simple)
