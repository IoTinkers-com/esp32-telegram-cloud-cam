// main.cpp
// ESP32-S3-CAM IoT Camera Firmware
// Firmware de cámara IoT ESP32-S3-CAM
// --- Bilingual comments for beginners / Comentarios bilingües para principiantes ---

#include <esp_camera.h>               // Camera library / Librería de cámara
#include <Adafruit_NeoPixel.h>        // RGB LED for feedback / LED RGB para feedback
#include <WiFi.h>                     // WiFi connection / Conexión WiFi
#include <WebServer.h>                // HTTP server / Servidor HTTP
#include <HTTPClient.h>               // HTTP client / Cliente HTTP
#include "FS.h"                      // File system / Sistema de archivos
#include "SD_MMC.h"                  // SD card / Tarjeta SD
// Eliminada la inclusión duplicada de esp_camera.h
#include "env.h"                     // Environment config / Configuración de entorno

// --- WiFi and HTTP configuration from env.h ---
// Configuración WiFi y HTTP desde env.h
const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;
// Usando las constantes WS_ por compatibilidad, pero ahora son para HTTP
// URLs completas para cada endpoint (definidas en env.h)
// Full URLs for each endpoint (defined in env.h)
String commandUrl = WS_COMMAND_URL;   // Comandos / Commands
String photoUrl   = WS_PHOTO_URL;     // Foto / Photo
String statusUrl  = WS_STATUS_URL;    // Estado / Status
bool take_photo_flag = false;   // Flag to take photo / Bandera para tomar foto
bool reboot_flag = false;       // Flag to reboot / Bandera para reiniciar

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

// Function to reconnect WiFi if disconnected
// Función para reconectar WiFi si está desconectado
bool reconnectWiFi(int maxAttempts = 5) {
  if (WiFi.status() == WL_CONNECTED) {
    return true; // Ya está conectado
  }

  Serial.println("[WiFi] No conectado, intentando reconectar...");
  WiFi.disconnect();
  delay(500);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < maxAttempts) {
    Serial.printf("[WiFi] Intento de reconexión #%d\n", attempts + 1);
    delay(1000);
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[WiFi] Reconectado exitosamente. IP: " + WiFi.localIP().toString());
    return true;
  } else {
    Serial.println("[WiFi] No se pudo reconectar después de " + String(maxAttempts) + " intentos");
    return false;
  }
}

// Function to check for commands from the server
// Función para verificar comandos del servidor
String checkForCommands() {
  // Verificar conexión WiFi antes de hacer petición HTTP
  if (WiFi.status() != WL_CONNECTED) {
    if (!reconnectWiFi(3)) { // Intentar reconectar con 3 intentos máximo
      Serial.println("[HTTP] No se puede verificar comandos: WiFi desconectado");
      return "NONE";
    }
  }
  
  HTTPClient http;
  // Usar la URL de comandos definida en env.h / Use the command URL from env.h
  String url = commandUrl;
  http.begin(url);
  
  int httpCode = http.GET();
  String command = "NONE";
  
  if (httpCode == HTTP_CODE_OK) {
    command = http.getString();
    Serial.println("[HTTP] Comando recibido: " + command);
  } else {
    Serial.printf("[HTTP] Error al verificar comandos: %d\n", httpCode);
  }
  
  http.end();
  return command;
}

// Function to send status to the server
// Función para enviar estado al servidor
bool sendStatus() {
  // Verificar conexión WiFi antes de hacer petición HTTP
  if (WiFi.status() != WL_CONNECTED) {
    if (!reconnectWiFi(3)) { // Intentar reconectar con 3 intentos máximo
      Serial.println("[HTTP] No se puede enviar estado: WiFi desconectado");
      return false;
    }
  }
  
  HTTPClient http;
  // Usar la URL de estado definida en env.h / Use the status URL from env.h
  String url = statusUrl;
  http.begin(url);
  
  String status = "STATUS: heap=" + String(ESP.getFreeHeap()) + ", ip=" + WiFi.localIP().toString();
  
  http.addHeader("Content-Type", "application/json");
  String jsonPayload = "{\"status\":\"" + status + "\"}";
  
  int httpCode = http.POST(jsonPayload);
  bool success = false;
  
  if (httpCode == HTTP_CODE_OK) {
    Serial.println("[HTTP] Estado enviado correctamente");
    success = true;
  } else {
    Serial.printf("[HTTP] Error al enviar estado: %d\n", httpCode);
  }
  
  http.end();
  return success;
}

// Function to send photo to the server
// Función para enviar foto al servidor
bool sendPhoto(uint8_t* imageData, size_t imageSize) {
  // Verificar conexión WiFi antes de hacer petición HTTP
  if (WiFi.status() != WL_CONNECTED) {
    if (!reconnectWiFi(3)) { // Intentar reconectar con 3 intentos máximo
      Serial.println("[HTTP] No se puede enviar foto: WiFi desconectado");
      return false;
    }
  }
  
  HTTPClient http;
  // Usar la URL de foto definida en env.h / Use the photo URL from env.h
  String url = photoUrl;
  // Imprimir más información para depuración
  Serial.println("[DEBUG] Conectando a URL: " + url);
  Serial.printf("[DEBUG] Tamaño de imagen: %d bytes\n", imageSize);
  
  http.begin(url);
  http.addHeader("Content-Type", "image/jpeg");
  
  // Aumentar el timeout para dar más tiempo a la transferencia
  http.setTimeout(20000); // 20 segundos
  
  Serial.println("[HTTP] Enviando imagen al servidor...");
  int httpCode = http.POST(imageData, imageSize);
  
  // Imprimir más información sobre la respuesta
  Serial.printf("[DEBUG] Código de respuesta HTTP: %d\n", httpCode);
  
  if (httpCode > 0) {
    String payload = http.getString();
    Serial.println("[DEBUG] Respuesta del servidor: " + payload);
  } else {
    Serial.printf("[DEBUG] Error en la solicitud HTTP: %s\n", http.errorToString(httpCode).c_str());
  }
  
  bool success = (httpCode == HTTP_CODE_OK);
  
  if (success) {
    Serial.println("[HTTP] Imagen enviada correctamente");
  } else {
    Serial.printf("[HTTP] Error al enviar imagen: %d\n", httpCode);
  }
  
  http.end();  // Aseguramos que http.end() siempre se ejecute
  return success;
}

void setup() {
    Serial.begin(115200); // Start serial / Inicia serial
    delay(2000);
    Serial.println("Setup started / Inicio setup");

    // --- WiFi connection / Conexión WiFi ---
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    Serial.println("\nWiFi connected. IP: / WiFi conectado. IP: " + WiFi.localIP().toString());

    // --- HTTP configuration / Configuración HTTP ---
    Serial.println("[HTTP] URL comando: " + commandUrl);
    Serial.println("[HTTP] URL foto: " + photoUrl);
    Serial.println("[HTTP] URL estado: " + statusUrl);

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
        
        // Configurar rotación de la imagen 180 grados
        sensor_t * s = esp_camera_sensor_get();
        if (s) {
            s->set_hmirror(s, 1);   // Espejo horizontal / Horizontal mirror
            s->set_vflip(s, 1);      // Volteo vertical / Vertical flip
            Serial.println("Camera rotation set to 180 degrees / Rotación de cámara configurada a 180 grados");
        }
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
    // Dar tiempo al sistema para evitar watchdog
    delay(50);
    
    // Verificar estado de la bandera take_photo_flag
    static unsigned long lastDebugTime = 0;
    if (millis() - lastDebugTime > 10000) { // Cada 10 segundos
        Serial.printf("[DEBUG] Estado actual de take_photo_flag: %d\n", take_photo_flag);
        lastDebugTime = millis();
    }
    
    // Verificar conexión WiFi y reconectar si es necesario
    static unsigned long lastConnectionCheck = 0;
    static int reconnectAttempts = 0;
    
    // Si no estamos conectados y ha pasado suficiente tiempo desde el último intento
    if (WiFi.status() != WL_CONNECTED) {
        if (millis() - lastConnectionCheck > (reconnectAttempts < 5 ? 3000 : 10000)) { // Backoff exponencial
            // Encender LED en azul para indicar reconexión
            pixels.setPixelColor(0, pixels.Color(0, 0, 255));
            pixels.show();
            
            // Usar nuestra función mejorada de reconexión
            bool connected = reconnectWiFi(3); // 3 intentos máximo
            
            // Incrementar contador de intentos (para backoff)
            reconnectAttempts++;
            lastConnectionCheck = millis();
            
            // Apagar LED después del intento
            pixels.setPixelColor(0, pixels.Color(0, 0, 0));
            pixels.show();
            
            // Si no pudimos conectar después de varios intentos, esperar más tiempo
            if (!connected && reconnectAttempts > 10) {
                Serial.println("[WiFi] Demasiados intentos fallidos, esperando más tiempo...");
                delay(30000); // Esperar 30 segundos antes de seguir intentando
                reconnectAttempts = 0; // Reiniciar contador después de la espera larga
            }
            
            // Si no hay conexión, salir del loop y volver a intentar en el siguiente ciclo
            if (!connected) {
                return;
            }
        } else {
            // Si no es tiempo de reconectar, no hacer nada más en este ciclo
            return;
        }
    } else {
        // Si estamos conectados, reiniciar contador de intentos
        reconnectAttempts = 0;
        
        // Verificar comandos periódicamente
        static unsigned long lastCommandCheck = 0;
        if (millis() - lastCommandCheck > 5000) { // Cada 5 segundos
            String command = checkForCommands();
            Serial.printf("[DEBUG] Valor crudo de comando: '%s'\n", command.c_str());
            command.trim(); // Elimina espacios y saltos de línea
            Serial.printf("[DEBUG] Valor de comando tras trim(): '%s'\n", command.c_str());
            command.replace("\"", ""); // Elimina comillas dobles
            Serial.printf("[DEBUG] Valor de comando final para comparar: '%s'\n", command.c_str());
            if (command == "TAKE_PHOTO") {
                Serial.println("[DEBUG] Comando TAKE_PHOTO recibido, activando bandera");
                take_photo_flag = true;
                Serial.printf("[DEBUG] Estado de take_photo_flag: %d\n", take_photo_flag);
            } else if (command == "STATUS") {
                sendStatus();
            } else if (command == "REBOOT") {
                reboot_flag = true;
            }
            
            lastCommandCheck = millis();
        }
        
        // Enviar estado periódicamente (heartbeat)
        static unsigned long lastStatusTime = 0;
        if (millis() - lastStatusTime > 30000) { // Cada 30 segundos
            sendStatus();
            lastStatusTime = millis();
        }
    }
    
    // Comando: Tomar foto y enviar
    if (take_photo_flag) {
        Serial.println("[Accion] Capturando y enviando foto...");
        Serial.printf("[DEBUG] Memoria libre: %d bytes\n", ESP.getFreeHeap());
        
        // Asegurarse de que estamos conectados antes de intentar capturar
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[Error] WiFi no conectado, abortando captura");
            take_photo_flag = false;
            return;
        }
        
        Serial.printf("[DEBUG] Estado WiFi: conectado, IP: %s\n", WiFi.localIP().toString().c_str());
        
        // Encender LED para indicar captura
        pixels.setPixelColor(0, pixels.Color(255, 255, 0)); // Amarillo durante captura
        pixels.show();
        
        // Capturar foto
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb && fb->len > 0) {
            Serial.printf("[Foto] Capturada (%d bytes), enviando...\n", fb->len);
            
            // Guardar en SD como respaldo
            bool saved_to_sd = false;
            if (SD_MMC.cardType() != CARD_NONE) {
                // Guardar imagen en la SD
                String path = "/imagen.jpg";
                File file = SD_MMC.open(path.c_str(), FILE_WRITE);
                if (file) {
                    file.write(fb->buf, fb->len);
                    file.close();
                    saved_to_sd = true;
                    Serial.println("[Foto] Guardada en SD como respaldo");
                }
            }
            
            // Enviar la imagen al servidor
            bool success = sendPhoto(fb->buf, fb->len);
            
            if (success) {
                Serial.println("[Foto] Enviada correctamente");
                pixels.setPixelColor(0, pixels.Color(0, 255, 0)); // Verde = éxito
            } else {
                Serial.println("[Error] No se pudo enviar la imagen");
                pixels.setPixelColor(0, pixels.Color(255, 0, 0)); // Rojo = error
            }
            
            // Liberar buffer de la cámara
            esp_camera_fb_return(fb);
            
            // Si se guardó en SD, informar al usuario
            if (saved_to_sd) {
                Serial.println("[Info] La imagen está disponible en http://" + 
                               WiFi.localIP().toString() + "/imagen.jpg");
            }
        } else {
            Serial.println("[Error] No se pudo capturar la imagen o está vacía");
            if (fb) esp_camera_fb_return(fb);
            pixels.setPixelColor(0, pixels.Color(255, 0, 0)); // Rojo = error
        }
        
        pixels.show();
        delay(500); // Mantener LED encendido brevemente
        pixels.setPixelColor(0, pixels.Color(0, 0, 0)); // Apagar LED
        pixels.show();
        
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