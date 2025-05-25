# ESP32-telegram-cloud-cam
# (English & Español)

---

## English

### Description
Remotely control an ESP32-S3-CAM to take photos on demand using Telegram and a FastAPI cloud server. The ESP32 stays in low-power mode and receives commands via WebSocket. Photos are sent back to Telegram automatically.

### Features
- ESP32-S3-CAM stays in light sleep, keeping Wi-Fi active for remote commands.
- Full control via Telegram: request photos, check status, ping, or remotely reboot.
- The server (FastAPI) receives Telegram messages, relays commands to the ESP32 via WebSocket, and forwards images to Telegram.
- **All scripts are thoroughly commented in both English and Spanish for beginners.**

### Project Structure
```
cam-test/
├── src/main.cpp           # ESP32-S3-CAM firmware
├── cloud_server.py        # FastAPI + WebSocket + Telegram server
├── requirements.txt       # Python dependencies
├── platformio.ini         # PlatformIO config
├── .env                   # Secret variables (DO NOT commit)
├── src/env.example.h      # Example environment config (copy as env.h)
├── .gitignore             # Files/folders ignored by git
└── ...
```

### Environment Configuration
- **Never commit your real WiFi or server credentials!**
- Copy `src/env.example.h` to `src/env.h` and fill in your own WiFi and WebSocket server info.
- `src/env.h` is in `.gitignore` by default to protect your secrets.

---

## Español

### Descripción
Controla remotamente una ESP32-S3-CAM para tomar fotos bajo demanda usando Telegram y un servidor en la nube con FastAPI. El ESP32 permanece en modo de bajo consumo y recibe comandos por WebSocket. Las fotos se envían automáticamente a Telegram.

### Características
- El ESP32-S3-CAM permanece en light sleep, manteniendo Wi-Fi activo para recibir comandos.
- Control total mediante Telegram: puedes pedir fotos, consultar estado, hacer ping o reiniciar el dispositivo.
- El servidor (FastAPI) recibe mensajes del bot, reenvía comandos al ESP32 vía WebSocket y reenvía imágenes a Telegram.
- **Todos los scripts están ampliamente comentados en inglés y español para principiantes.**

### Estructura del proyecto
```
cam-test/
├── src/main.cpp           # Firmware para ESP32-S3-CAM
├── cloud_server.py        # Servidor FastAPI + WebSocket + Telegram
├── requirements.txt       # Dependencias Python
├── platformio.ini         # Configuración PlatformIO
├── .env                   # Variables secretas (NO subir a GitHub)
├── src/env.example.h      # Configuración de entorno de ejemplo (copiar como env.h)
├── .gitignore             # Archivos/Carpetas ignorados por git
└── ...
```

### Configuración de entorno
- **¡Nunca subas tus credenciales reales de WiFi o servidor!**
- Copia `src/env.example.h` a `src/env.h` y pon tus datos de WiFi y WebSocket.
- `src/env.h` ya está en `.gitignore` para proteger tus claves.

---

**See each script for detailed, bilingual comments explaining every relevant step.**
**Consulta cada script para ver comentarios detallados y bilingües sobre cada paso relevante.**

### ESP32-S3-CAM Code Example (Commented)
```cpp
#include <esp_camera.h>               // Camera library
#include <Adafruit_NeoPixel.h>        // RGB LED for feedback
#include <WiFi.h>                     // WiFi connection
#include <WebSocketsClient.h>         // WebSocket for cloud comm

const char* ssid = "YOUR_WIFI";
const char* password = "YOUR_PASS";
const char* ws_server = "wss://YOUR_RENDER_URL/ws";
WebSocketsClient webSocket;
bool take_photo_flag = false;
bool reboot_flag = false;

// Handles incoming WebSocket commands
void onWebSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    if (type == WStype_TEXT) {
        String cmd = String((char*)payload);
        Serial.print("[WebSocket] Received: "); Serial.println(cmd);
        if (cmd == "TAKE_PHOTO") {
            take_photo_flag = true;
        } else if (cmd == "PING") {
            webSocket.sendTXT("PONG");
        } else if (cmd == "STATUS") {
            char status[128];
            snprintf(status, sizeof(status), "STATUS: heap=%u, psram=%u, ip=%s", ESP.getFreeHeap(), ESP.getFreePsram(), WiFi.localIP().toString().c_str());
            webSocket.sendTXT(status);
        } else if (cmd == "REBOOT") {
            reboot_flag = true;
        } else {
            webSocket.sendTXT("UNKNOWN_COMMAND");
        }
    }
}

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    // Camera and SD init...
    webSocket.beginSSL("YOUR_RENDER_URL", 443, "/ws");
    webSocket.onEvent(onWebSocketEvent);
}

void loop() {
    if (!webSocket.isConnected()) {
        webSocket.beginSSL("YOUR_RENDER_URL", 443, "/ws");
    }
    webSocket.loop();
    if (take_photo_flag) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb && fb->len > 0) {
            webSocket.sendBIN(fb->buf, fb->len);
            esp_camera_fb_return(fb);
        } else {
            webSocket.sendTXT("ERROR:CAPTURE_FAIL");
        }
        take_photo_flag = false;
    }
    if (reboot_flag) {
        ESP.restart();
    }
    esp_sleep_enable_timer_wakeup(500 * 1000); // 500 ms light sleep
    esp_light_sleep_start();
}
```

### Supported Commands
- `TAKE_PHOTO`: take and send a photo
- `PING`: respond with `PONG`
- `STATUS`: send memory and network status
- `REBOOT`: reboot ESP32

### Server Setup & Deployment
- Set up `.env` with your Telegram token (and optionally CHAT_ID)
- Install dependencies:
```sh
python -m venv venv
venv\Scripts\activate   # On Windows
pip install -r requirements.txt
uvicorn cloud_server:app --reload --port 8000
```
- Deploy to Render.com (see README for details)

---

## Español

### Descripción
Este proyecto permite controlar remotamente una cámara ESP32-S3-CAM usando un bot de Telegram y un servidor Python (FastAPI) en la nube (ej: Render.com). El ESP32 está optimizado para bajo consumo (light sleep) y solo toma fotos bajo demanda.

### Características
- El ESP32-S3-CAM permanece en light sleep, manteniendo Wi-Fi activo para recibir comandos.
- Control total mediante Telegram: puedes pedir fotos, consultar estado, hacer ping o reiniciar el dispositivo.
- El servidor (FastAPI) recibe mensajes del bot, reenvía comandos al ESP32 vía WebSocket y reenvía imágenes a Telegram.
- Código comentado línea a línea para principiantes.

### Estructura del proyecto
```
cam-test/
├── src/main.cpp           # Firmware para ESP32-S3-CAM
├── cloud_server.py        # Servidor FastAPI + WebSocket + Telegram
├── requirements.txt       # Dependencias Python
├── platformio.ini         # Configuración PlatformIO
├── .env                   # Variables secretas (NO subir a GitHub)
├── .gitignore             # Archivos/Carpetas ignorados por git
└── ...
```

### Ejemplo de código ESP32-S3-CAM (Comentado)
```cpp
#include <esp_camera.h>               // Librería principal de la cámara
#include <Adafruit_NeoPixel.h>        // LED RGB para feedback visual
#include <WiFi.h>                     // Conexión WiFi
#include <WebSocketsClient.h>         // WebSocket para comunicación cloud

const char* ssid = "TU_WIFI";
const char* password = "TU_PASS";
const char* ws_server = "wss://TU_RENDER_URL/ws";
WebSocketsClient webSocket;
bool take_photo_flag = false;
bool reboot_flag = false;

// Callback: maneja comandos recibidos por WebSocket
void onWebSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    if (type == WStype_TEXT) {
        String cmd = String((char*)payload);
        Serial.print("[WebSocket] Comando recibido: "); Serial.println(cmd);
        if (cmd == "TAKE_PHOTO") {
            take_photo_flag = true;
        } else if (cmd == "PING") {
            webSocket.sendTXT("PONG");
        } else if (cmd == "STATUS") {
            char status[128];
            snprintf(status, sizeof(status), "STATUS: heap=%u, psram=%u, ip=%s", ESP.getFreeHeap(), ESP.getFreePsram(), WiFi.localIP().toString().c_str());
            webSocket.sendTXT(status);
        } else if (cmd == "REBOOT") {
            reboot_flag = true;
        } else {
            webSocket.sendTXT("UNKNOWN_COMMAND");
        }
    }
}

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    // Inicializa la cámara y la SD...
    webSocket.beginSSL("TU_RENDER_URL", 443, "/ws");
    webSocket.onEvent(onWebSocketEvent);
}

void loop() {
    if (!webSocket.isConnected()) {
        webSocket.beginSSL("TU_RENDER_URL", 443, "/ws");
    }
    webSocket.loop();
    if (take_photo_flag) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb && fb->len > 0) {
            webSocket.sendBIN(fb->buf, fb->len); // Envía la foto
            esp_camera_fb_return(fb);
        } else {
            webSocket.sendTXT("ERROR:CAPTURE_FAIL");
        }
        take_photo_flag = false;
    }
    if (reboot_flag) {
        ESP.restart();
    }
    esp_sleep_enable_timer_wakeup(500 * 1000); // 500 ms light sleep
    esp_light_sleep_start();
}
```

### Comandos soportados por el ESP32:
- `TAKE_PHOTO`: toma y envía una foto.
- `PING`: responde con `PONG`.
- `STATUS`: responde con información de memoria y red.
- `REBOOT`: reinicia el ESP32.

### Configuración y despliegue
- Configura tu `.env` con el token de Telegram (y opcionalmente CHAT_ID)
- Instala dependencias:
```sh
python -m venv venv
venv\Scripts\activate   # En Windows
pip install -r requirements.txt
uvicorn cloud_server:app --reload --port 8000
```
- Despliega en Render.com (ver detalles en README)

---

## Notas / Notes
- **No subas tu `.env` ni claves a GitHub.**
- Puedes extender los comandos y lógica fácilmente.
- El ESP32 puede usarse con otros servicios (MQTT, HTTP, etc) cambiando el backend.
- El código está comentado para que puedas entender cada bloque y adaptarlo a tu necesidad.

---

¡Listo! / Ready! Now you have a robust and well-documented IoT base for ESP32, Telegram, and Python Cloud.
---

## 1. Código ESP32-S3-CAM (`src/main.cpp`)

### Fragmentos clave comentados:
```cpp
#include <esp_camera.h>               // Librería principal de la cámara
#include <Adafruit_NeoPixel.h>        // LED RGB para feedback visual
#include <WiFi.h>                     // Conexión WiFi
#include <WebSocketsClient.h>         // WebSocket para comunicación cloud

// Configuración WiFi y WebSocket
const char* ssid = "TU_WIFI";
const char* password = "TU_PASS";
const char* ws_server = "wss://TU_RENDER_URL/ws"; // URL del servidor cloud
WebSocketsClient webSocket;
bool take_photo_flag = false;         // Flag para saber si hay que tomar foto
bool reboot_flag = false;             // Flag para reinicio remoto

// Callback: maneja comandos recibidos por WebSocket
void onWebSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    if (type == WStype_TEXT) {
        String cmd = String((char*)payload);
        Serial.print("[WebSocket] Comando recibido: "); Serial.println(cmd);
        if (cmd == "TAKE_PHOTO") {
            take_photo_flag = true;
        } else if (cmd == "PING") {
            webSocket.sendTXT("PONG");
        } else if (cmd == "STATUS") {
            char status[128];
            snprintf(status, sizeof(status), "STATUS: heap=%u, psram=%u, ip=%s", ESP.getFreeHeap(), ESP.getFreePsram(), WiFi.localIP().toString().c_str());
            webSocket.sendTXT(status);
        } else if (cmd == "REBOOT") {
            reboot_flag = true;
        } else {
            webSocket.sendTXT("UNKNOWN_COMMAND");
        }
    }
}

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    // Inicializa la cámara y la SD...
    webSocket.beginSSL("TU_RENDER_URL", 443, "/ws");
    webSocket.onEvent(onWebSocketEvent);
}

void loop() {
    // Reconexión automática WebSocket
    if (!webSocket.isConnected()) {
        webSocket.beginSSL("TU_RENDER_URL", 443, "/ws");
    }
    webSocket.loop();
    if (take_photo_flag) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb && fb->len > 0) {
            webSocket.sendBIN(fb->buf, fb->len); // Envía la foto
            esp_camera_fb_return(fb);
        } else {
            webSocket.sendTXT("ERROR:CAPTURE_FAIL");
        }
        take_photo_flag = false;
    }
    if (reboot_flag) {
        ESP.restart();
    }
    esp_sleep_enable_timer_wakeup(500 * 1000); // Light sleep 500ms
    esp_light_sleep_start();
}
```

### Comandos soportados por el ESP32:
- `TAKE_PHOTO`: toma y envía una foto.
- `PING`: responde con `PONG`.
- `STATUS`: responde con información de memoria y red.
- `REBOOT`: reinicia el ESP32.

---

## 2. Servidor Cloud Python (`cloud_server.py`)

### Fragmentos clave comentados:
```python
import os
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from telegram import Bot
from dotenv import load_dotenv
load_dotenv()  # Carga variables de .env

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
bot = Bot(token=TELEGRAM_TOKEN)
app = FastAPI()
esp32_clients = set()  # WebSocket clients conectados (ESP32)

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    esp32_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_bytes()
            if data and CHAT_ID:
                await bot.send_photo(chat_id=CHAT_ID, photo=data)
    except WebSocketDisconnect:
        pass
    finally:
        esp32_clients.remove(websocket)

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    msg = data.get("message", {}).get("text", "")
    chat_id = data.get("message", {}).get("chat", {}).get("id")
    if msg and chat_id:
        for ws in list(esp32_clients):
            await ws.send_text("TAKE_PHOTO")
        await bot.send_message(chat_id=chat_id, text="¡Tomando foto!")
    return {"ok": True}
```

---

## 3. Configuración y despliegue

### Variables de entorno (`.env`):
```
TELEGRAM_TOKEN=tu_token_de_bot
CHAT_ID=opcional
```

### Instalar dependencias y correr localmente:
```sh
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
pip install -r requirements.txt
uvicorn cloud_server:app --reload --port 8000
```

### Despliegue en Render.com
1. Sube el repo a GitHub (sin `.env`).
2. Crea un nuevo Web Service en Render, conecta tu repo y pon las variables de entorno.
3. Usa como comando de inicio:
   ```
   uvicorn cloud_server:app --host 0.0.0.0 --port 10000
   ```
4. Configura el webhook de Telegram:
   ```
   https://api.telegram.org/bot<TU_TOKEN>/setWebhook?url=https://<tu-app>.onrender.com/webhook
   ```

---

## 4. Notas para principiantes
- **No subas tu `.env` ni claves a GitHub.**
- Puedes extender los comandos y lógica fácilmente.
- El ESP32 puede usarse con otros servicios (MQTT, HTTP, etc) cambiando el backend.
- El código está comentado para que puedas entender cada bloque y adaptarlo a tu necesidad.

---

¡Listo! Ahora tienes una base robusta y didáctica para proyectos IoT con ESP32, Telegram y Python Cloud.
