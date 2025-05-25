// main.cpp
// ESP32-S3-CAM IoT Camera Firmware
// Firmware de cámara IoT ESP32-S3-CAM
// --- Bilingual comments for beginners / Comentarios bilingües para principiantes ---

#include <esp_camera.h>               // Camera library / Librería de cámara
#include <Adafruit_NeoPixel.h>        // RGB LED for feedback / LED RGB para feedback
#include <WiFi.h>                     // WiFi connection / Conexión WiFi
#include <WebServer.h>                // HTTP server / Servidor HTTP
#include <WebSocketsClient.h>         // WebSocket for cloud / WebSocket para la nube
#include "FS.h"                      // File system / Sistema de archivos
#include "SD_MMC.h"                  // SD card / Tarjeta SD
#include "esp_camera.h"              // Camera driver / Driver de cámara

// --- WiFi and WebSocket configuration / Configuración WiFi y WebSocket ---
const char* ssid = "420 - 2,4GHZ";      // <-- Change for your network / Cambia por tu red
const char* password = "Seleccion420";  // <-- Change for your password / Cambia por tu clave
const char* ws_server = "wss://TU_RENDER_URL/ws"; // Change for your Render URL / Cambia por tu URL Render
WebSocketsClient webSocket;
bool take_photo_flag = false;   // Flag to take photo / Bandera para tomar foto
bool reboot_flag = false;       // Flag to reboot / Bandera para reiniciar

// Supported commands: TAKE_PHOTO, PING, STATUS, REBOOT
// Comandos soportados: TAKE_PHOTO, PING, STATUS, REBOOT
void onWebSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    if (type == WStype_TEXT) {
        String cmd = String((char*)payload);
        Serial.print("[WebSocket] Received command: /"); Serial.print("[WebSocket] Comando recibido: "); Serial.println(cmd);
        if (cmd == "TAKE_PHOTO") {
            take_photo_flag = true; // Set flag / Activa bandera
        } else if (cmd == "PING") {
            webSocket.sendTXT("PONG"); // Respond to ping / Responde a ping
        } else if (cmd == "STATUS") {
            char status[128];
            snprintf(status, sizeof(status), "STATUS: heap=%u, psram=%u, ip=%s", ESP.getFreeHeap(), ESP.getFreePsram(), WiFi.localIP().toString().c_str());
            webSocket.sendTXT(status); // Send status / Envía estado
        } else if (cmd == "REBOOT") {
            reboot_flag = true; // Set reboot flag / Activa bandera de reinicio
        } else {
            webSocket.sendTXT("UNKNOWN_COMMAND"); // Unknown command / Comando desconocido
        }
    }
}

// WS2812 LED
// LED WS2812
#define WS2812_PIN 48
#define NUMPIXELS 1
Adafruit_NeoPixel pixels(NUMPIXELS, WS2812_PIN, NEO_GRB + NEO_KHZ800); // LED setup / Configuración LED

// Camera pinout / Pines de la cámara
#define PWDN_GPIO_NUM    -1
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM    15
#define SIOD_GPIO_NUM    4
#define SIOC_GPIO_NUM    5
#define Y9_GPIO_NUM      16
#define Y8_GPIO_NUM      17
#define Y7_GPIO_NUM      18
#define Y6_GPIO_NUM      12
#define Y5_GPIO_NUM      10
#define Y4_GPIO_NUM      8
#define Y3_GPIO_NUM      9
#define Y2_GPIO_NUM      11
#define VSYNC_GPIO_NUM   6
#define HREF_GPIO_NUM    7
#define PCLK_GPIO_NUM    13

WebServer server(80); // HTTP server on port 80 / Servidor HTTP en puerto 80

void setup() {
    Serial.begin(115200); // Start serial / Inicia serial
    delay(2000);
    Serial.println("Setup started / Inicio setup");

    // --- WiFi connection / Conexión WiFi ---
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    Serial.println("\nWiFi connected. IP: / WiFi conectado. IP: " + WiFi.localIP().toString());

    // --- SD card init with forced pins (CLK=39, CMD=38, DATA0=40, 1-bit mode) ---
    // Inicializa SD con pines forzados (CLK=39, CMD=38, DATA0=40, modo 1-bit)
    // Tries to mount SD and format if needed (this erases all previous data!)
    // Intenta montar la SD y formatear si es necesario (¡esto borra todos los datos previos!)
    if(!SD_MMC.setPins(39, 38, 40) || !SD_MMC.begin("/sdcard", true, true)){
        Serial.println("SD_MMC mount error, formatting or forced pins. Restarting... / Error al montar SD_MMC (1-bit, pines forzados, intenta formatear). Reiniciando...");
        delay(2000);
        ESP.restart();
    }
    Serial.println("SD_MMC mounted OK (forced pins or formatted) / SD_MMC montada correctamente (pines forzados o formateada)");

    pixels.begin(); pixels.clear(); pixels.show(); delay(100); // LED init / Inicializa LED

    // Camera configuration / Configuración de la cámara
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_XGA; // See datasheet for options / Ver datasheet para opciones
    config.jpeg_quality = 30;
    config.fb_count = 1;

    esp_err_t err = esp_camera_init(&config);
    if (err == ESP_OK) {
        pixels.setPixelColor(0, pixels.Color(0, 255, 0)); // Green LED / LED verde
        pixels.show();
        Serial.println("Camera initialized OK / Camara inicializada correctamente");
    } else {
        pixels.setPixelColor(0, pixels.Color(255, 0, 0)); // Red LED / LED rojo
        pixels.show();
        Serial.println("Camera init error / Error al inicializar la camara");
        while (true) { delay(1000); }
    }

    // --- HTTP route to download image / Ruta HTTP para descargar imagen ---
    server.on("/imagen.jpg", HTTP_GET, [](){
        File file = SD_MMC.open("/imagen.jpg");
        if(!file || file.size() == 0){
            server.send(404, "text/plain", "File not found or empty / Archivo no encontrado o vacío");
            if(file) file.close();
            return;
        }
        Serial.printf("Serving image /imagen.jpg (%d bytes) / Sirviendo imagen /imagen.jpg de %d bytes\n", file.size(), file.size());
        server.streamFile(file, "image/jpeg");
        file.close();
    });
    server.begin(); // Start HTTP server / Inicia servidor HTTP
}


void loop() {
    // Reconexión automática WebSocket si se desconecta
    if (!webSocket.isConnected()) {
        Serial.println("[WebSocket] Desconectado, intentando reconectar...");
        webSocket.beginSSL("TU_RENDER_URL", 443, "/ws");
    }
    webSocket.loop();

    // Comando: Tomar foto y enviar
    if (take_photo_flag) {
        Serial.println("[Accion] Capturando y enviando foto...");
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb && fb->len > 0) {
            webSocket.sendBIN(fb->buf, fb->len);
            Serial.printf("[Foto] Capturada y enviada (%d bytes)\n", fb->len);
            esp_camera_fb_return(fb);
        } else {
            Serial.println("[Error] No se pudo capturar la imagen o está vacía");
            if (fb) esp_camera_fb_return(fb);
            webSocket.sendTXT("ERROR:CAPTURE_FAIL");
        }
        take_photo_flag = false;
    }

    // Comando: Reinicio remoto
    if (reboot_flag) {
        Serial.println("[Accion] Reiniciando ESP32 por comando remoto...");
        delay(1000);
        ESP.restart();
    }

    // Light sleep: mantiene WiFi y espera comandos
    esp_sleep_enable_timer_wakeup(500 * 1000); // 500 ms
    esp_light_sleep_start();
}