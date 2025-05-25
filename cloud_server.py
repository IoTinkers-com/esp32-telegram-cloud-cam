# cloud_server.py
# FastAPI + Telegram + WebSocket server for Render.com
# Servidor FastAPI + Telegram + WebSocket para Render.com
# - Receives Telegram messages / Recibe mensajes de Telegram
# - Sends commands to ESP32 via WebSocket / Envía comandos al ESP32 vía WebSocket
# - Receives images from ESP32 and sends to Telegram / Recibe imágenes del ESP32 y las reenvía a Telegram

import os
import json
import logging
from typing import Set
import asyncio
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Dict, Optional
import asyncio
import base64
import os
import time
from datetime import datetime
import uuid
import json

app = FastAPI()

# Configuración de carpetas estáticas y plantillas
static_folder = "static"
os.makedirs(static_folder, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_folder), name="static")
templates = Jinja2Templates(directory="templates")

# Clientes ESP32 conectados para mantener compatibilidad con el endpoint /test
esp32_clients = set()

# Variables para seguimiento de imágenes
last_image_timestamp = None
last_image_path = None
pending_commands = []  # Cola de comandos pendientes

# Load environment variables from .env file
# Cargar variables de entorno desde el archivo .env
from dotenv import load_dotenv
load_dotenv()

# Get Telegram credentials from environment variables
# Obtiene credenciales de Telegram desde variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

# Initialize Telegram bot if token is available
# Inicializa el bot de Telegram si el token está disponible
bot = None
if TELEGRAM_TOKEN:
    try:
        from telegram import Bot
        bot = Bot(token=TELEGRAM_TOKEN)
        print("Telegram bot initialized successfully")
    except Exception as e:
        print(f"Error initializing Telegram bot: {e}")
        print("Telegram integration will be disabled")
else:
    print("No Telegram token found, Telegram integration will be disabled")

# Ruta principal - Interfaz web
@app.get("/", response_class=HTMLResponse)
async def get_html(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# API para obtener comandos pendientes
@app.get("/api/command")
async def get_command():
    if pending_commands:
        return pending_commands.pop(0)
    return "NONE"

# API para recibir estado del ESP32
@app.post("/api/status")
async def receive_status(request: Request):
    data = await request.json()
    status = data.get("status", "")
    print(f"[ESP32] Estado recibido: {status}")
    return {"status": "ok"}

# API para recibir fotos
@app.post("/api/photo")
async def receive_photo(request: Request, background_tasks: BackgroundTasks):
    print("[DEBUG] Recibiendo solicitud en /api/photo")
    try:
        # Leer los datos de la imagen
        image_data = await request.body()
        content_type = request.headers.get("content-type", "")
        content_length = request.headers.get("content-length", "desconocido")
        
        print(f"[DEBUG] Content-Type: {content_type}")
        print(f"[DEBUG] Content-Length: {content_length}")
        print(f"[DEBUG] Tamaño real de datos recibidos: {len(image_data)} bytes")
        
        if not image_data:
            print("[ERROR] No se recibieron datos de imagen")
            raise HTTPException(status_code=400, detail="No image data received")
        
        # Verificar que los datos parecen ser una imagen JPEG válida
        if len(image_data) < 10 or not (image_data[0:2] == b'\xff\xd8' and image_data[-2:] == b'\xff\xd9'):
            print("[ERROR] Los datos no parecen ser una imagen JPEG válida")
            if len(image_data) >= 10:
                print(f"[DEBUG] Primeros bytes: {image_data[0:10].hex()}")
                print(f"[DEBUG] Últimos bytes: {image_data[-10:].hex()}")
            return {"status": "error", "detail": "Invalid JPEG data"}
        
        # Crear un nombre de archivo único basado en la fecha y hora
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Guardar la imagen con nombre único
        filename = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join("images", filename)
        with open(filepath, "wb") as f:
            f.write(image_data)
        print(f"[DEBUG] Imagen guardada en {filepath}")

        # Sobrescribir la última imagen fija para el endpoint
        ultima_path = os.path.join("images", "ultima_imagen.jpg")
        import shutil
        shutil.copy(filepath, ultima_path)
        print(f"[DEBUG] Copiada como última imagen a {ultima_path}")

        # Actualizar variables globales
        global last_image_timestamp, last_image_path
        last_image_timestamp = datetime.now().isoformat()
        last_image_path = ultima_path
        
        print(f"[Servidor] Imagen recibida y guardada como {filename} ({len(image_data)} bytes)")
        
        # Si hay un bot de Telegram configurado, enviar la imagen
        if bot and CHAT_ID:
            try:
                with open(filepath, "rb") as photo_file:
                    background_tasks.add_task(bot.send_photo, chat_id=CHAT_ID, photo=photo_file)
                print("[DEBUG] Imagen programada para envío a Telegram")
            except Exception as e:
                print(f"[ERROR] Error al enviar a Telegram: {e}")
        
        return {"status": "ok", "filename": filename}
    
    except Exception as e:
        print(f"[ERROR] Error al procesar la imagen: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint para ver la última imagen
@app.get("/ultima_imagen")
@app.head("/ultima_imagen")
async def get_last_image():
    if last_image_path and os.path.exists(last_image_path):
        return FileResponse(last_image_path)
    raise HTTPException(status_code=404, detail="No hay imagen disponible")

# Endpoint para enviar comando de captura de foto
@app.get("/capturar_foto")
async def capture_photo():
    pending_commands.append("TAKE_PHOTO")
    return {"status": "comando enviado"}

# Endpoint para solicitar estado
@app.get("/solicitar_estado")
async def request_status():
    pending_commands.append("STATUS")
    return {"status": "comando enviado"}

# Endpoint para obtener información del estado
@app.get("/status")
async def get_status():
    return {
        "status": "online",
        "last_image": last_image_timestamp,
        "pending_commands": len(pending_commands)
    }

# Mantener compatibilidad con el endpoint de prueba anterior
@app.websocket("/test")
async def test_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("WELCOME")
    try:
        while True:
            await asyncio.sleep(5)
            await websocket.send_text("STATUS")
    except Exception as e:
        print(f"[Test] Detectada desconexión de {websocket.client.host}, cerrando sesión")
        print(f"[Test] Conexión con {websocket.client.host} cerrada")

@app.post("/webhook")
async def telegram_webhook(req: Request):
    # Si el bot no está inicializado, devolver error
    if not bot:
        return {"error": "Telegram bot not initialized"}
        
    try:
        from telegram import Update
        data = await req.json()
        update = Update.de_json(data, bot)
        if update.message and update.message.text == "/foto":
            # Enviar comando a todos los ESP32 conectados
            pending_commands.append("TAKE_PHOTO")
            await bot.send_message(chat_id=update.message.chat_id, text="Comando enviado. Espera un momento...")
        
        return {"ok": True}
    except Exception as e:
        print(f"Error in webhook: {e}")
        return {"error": str(e)}


@app.post("/upload")
async def upload_photo(req: Request):
    form = await req.form()  # Receive form / Recibe formulario
    photo = await form["photo"].read()  # Read photo / Lee la foto
    await bot.send_photo(chat_id=CHAT_ID, photo=photo)  # Send to Telegram / Envía a Telegram
    return {"ok": True}

@app.get("/ultima_imagen")
async def get_last_image():
    """Endpoint para ver la última imagen capturada"""
    # Verificar si existe una imagen
    if not os.path.exists("images/ultima_imagen.jpg"):
        return {"error": "No hay imágenes disponibles"}
    
    # Devolver la imagen como respuesta
    return FileResponse(
        "images/ultima_imagen.jpg",
        media_type="image/jpeg",
        filename="ultima_imagen.jpg"
    )

@app.get("/")
async def root():
    """Página principal con enlaces a las funciones disponibles"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ESP32-S3-CAM Control</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; }
            .button { display: inline-block; background-color: #4CAF50; color: white; padding: 10px 20px; 
                    margin: 10px 2px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; }
            .button:hover { background-color: #45a049; }
            .button.refresh { background-color: #2196F3; }
            .button.refresh:hover { background-color: #0b7dda; }
            .image-container { margin-top: 20px; text-align: center; }
            img { max-width: 100%; border: 1px solid #ddd; border-radius: 4px; padding: 5px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .status.connected { background-color: #dff0d8; color: #3c763d; border: 1px solid #d6e9c6; }
            .status.disconnected { background-color: #f2dede; color: #a94442; border: 1px solid #ebccd1; }
            .status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; }
            .status-dot.connected { background-color: #5cb85c; }
            .status-dot.disconnected { background-color: #d9534f; }
            #loading { display: none; margin: 20px 0; }
            .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 20px; height: 20px; 
                     animation: spin 2s linear infinite; display: inline-block; margin-right: 10px; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        </style>
    </head>
    <body>
        <h1>ESP32-S3-CAM Control</h1>
        <p>Controla tu cámara ESP32-S3 y visualiza las imágenes capturadas</p>
        
        <div id="connection-status" class="status disconnected">
            <span class="status-dot disconnected"></span> Estado: Verificando conexión...
        </div>
        
        <button onclick="takePhoto()" class="button">Tomar Foto</button>
        <button onclick="checkStatus()" class="button">Ver Estado</button>
        <button onclick="refreshImage()" class="button refresh">Actualizar Imagen</button>
        
        <div id="loading">
            <div class="spinner"></div> Procesando solicitud...
        </div>
        
        <div id="status-response" style="margin-top: 15px; display: none;"></div>
        
        <div class="image-container">
            <h2>Última Imagen Capturada</h2>
            <img src="/ultima_imagen" alt="Última imagen capturada" id="last-image">
            <p><small id="image-timestamp">Actualiza la página para ver la imagen más reciente</small></p>
        </div>
        
        <script>
            // Verificar estado de conexión del ESP32
            function updateConnectionStatus() {
                fetch('/status')
                    .then(response => response.json())
                    .then(data => {
                        const statusDiv = document.getElementById('connection-status');
                        const statusDot = statusDiv.querySelector('.status-dot');
                        
                        if (data.error) {
                            statusDiv.className = 'status disconnected';
                            statusDot.className = 'status-dot disconnected';
                            statusDiv.innerHTML = `<span class="status-dot disconnected"></span> ESP32 desconectado`;
                        } else {
                            statusDiv.className = 'status connected';
                            statusDot.className = 'status-dot connected';
                            statusDiv.innerHTML = `<span class="status-dot connected"></span> ESP32 conectado`;
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        const statusDiv = document.getElementById('connection-status');
                        statusDiv.className = 'status disconnected';
                        statusDiv.innerHTML = `<span class="status-dot disconnected"></span> Error de conexión al servidor`;
                    });
            }
            
            // Tomar foto
            function takePhoto() {
                showLoading();
                fetch('/take_photo')
                    .then(response => response.json())
                    .then(data => {
                        hideLoading();
                        if (data.error) {
                            alert('Error: ' + data.error);
                        } else {
                            const statusDiv = document.getElementById('status-response');
                            statusDiv.style.display = 'block';
                            statusDiv.innerHTML = `<div class="status connected">Comando enviado. La foto se enviará cuando esté lista.</div>`;
                            
                            // Esperar 5 segundos y luego intentar actualizar la imagen
                            setTimeout(refreshImage, 5000);
                        }
                    })
                    .catch(error => {
                        hideLoading();
                        alert('Error de conexión: ' + error);
                    });
            }
            
            // Verificar estado
            function checkStatus() {
                showLoading();
                fetch('/status')
                    .then(response => response.json())
                    .then(data => {
                        hideLoading();
                        const statusDiv = document.getElementById('status-response');
                        statusDiv.style.display = 'block';
                        
                        if (data.error) {
                            statusDiv.innerHTML = `<div class="status disconnected">Error: ${data.error}</div>`;
                        } else {
                            statusDiv.innerHTML = `<div class="status connected">Comando enviado. El estado se enviará cuando esté listo.</div>`;
                        }
                    })
                    .catch(error => {
                        hideLoading();
                        alert('Error de conexión: ' + error);
                    });
            }
            
            // Actualizar imagen
            function refreshImage() {
                const img = document.getElementById('last-image');
                const timestamp = new Date().getTime();
                img.src = `/ultima_imagen?t=${timestamp}`;
                document.getElementById('image-timestamp').textContent = `Última actualización: ${new Date().toLocaleTimeString()}`;
            }
            
            // Mostrar indicador de carga
            function showLoading() {
                document.getElementById('loading').style.display = 'block';
            }
            
            // Ocultar indicador de carga
            function hideLoading() {
                document.getElementById('loading').style.display = 'none';
            }
            
            // Manejar errores de carga de imagen
            document.getElementById('last-image').onerror = function() {
                this.style.display = 'none';
                document.querySelector('.image-container').innerHTML += '<p>No hay imágenes disponibles</p>';
            };
            
            // Verificar estado de conexión cada 10 segundos
            updateConnectionStatus();
            setInterval(updateConnectionStatus, 10000);
        </script>
    </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")

# To run locally: / Para correr local:
# uvicorn cloud_server:app --reload --port 8000
