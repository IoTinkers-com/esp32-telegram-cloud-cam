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
import os
from io import BytesIO

# Crear la carpeta 'images' si no existe
if not os.path.exists("images"):
    os.makedirs("images")

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
pending_photo_requests = []  # Lista de chat_ids que han solicitado fotos

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
        from telegram import Bot, Update
        from telegram.ext import Application, CommandHandler, ContextTypes
        
        # Crear instancia del bot
        bot = Bot(token=TELEGRAM_TOKEN)
        print("Telegram bot initialized successfully")
        
        # Función para manejar el comando /foto
        async def handle_foto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            chat_id = update.effective_chat.id
            await update.message.reply_text("📸 Solicitando foto al ESP32... Espera un momento.")
            # Agregar comando a la cola para que el ESP32 lo recoja
            pending_commands.append("TAKE_PHOTO")
            # Guardar el chat_id del solicitante para enviarle la foto cuando llegue
            pending_photo_requests.append(str(chat_id))
            print(f"[Telegram] Comando TAKE_PHOTO agregado a la cola desde chat {chat_id}")
        
        # Función para manejar el comando /status
        async def handle_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            chat_id = update.effective_chat.id
            await update.message.reply_text("📊 Solicitando estado al ESP32... Espera un momento.")
            # Agregar comando a la cola para que el ESP32 lo recoja
            pending_commands.append("STATUS")
            print(f"[Telegram] Comando STATUS agregado a la cola desde chat {chat_id}")
        
        # Función para manejar el comando /help
        async def handle_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            help_text = """📷 *ESP32 Telegram Cloud Cam* 📷

Comandos disponibles:
/foto - Captura una foto con la cámara
/status - Solicita el estado actual del ESP32
/help - Muestra este mensaje de ayuda"""
            await update.message.reply_text(help_text, parse_mode="Markdown")
        
    except Exception as e:
        print(f"Error initializing Telegram bot: {e}")
        print("Telegram integration will be disabled")
else:
    print("No Telegram token found, Telegram integration will be disabled")

# Endpoint para recibir actualizaciones de Telegram (webhook)
@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    if not bot:
        raise HTTPException(status_code=404, detail="Telegram bot not configured")
    
    try:
        data = await request.json()
        update = Update.de_json(data=data, bot=bot)
        
        # Procesar comandos
        if update and update.message and update.message.text:
            text = update.message.text
            chat_id = str(update.effective_chat.id)
            
            # En modo de pruebas, permitir acceso a cualquier usuario pero registrar el acceso
            if CHAT_ID and chat_id != CHAT_ID:
                print(f"[Seguridad] Acceso de usuario no registrado desde chat_id: {chat_id} - PERMITIDO EN MODO PRUEBAS")
                # Informar al chat principal que alguien más está usando el bot
                if bot and CHAT_ID:
                    try:
                        # Corregido el formato del mensaje para evitar errores de parsing
                        await bot.send_message(
                            chat_id=CHAT_ID,
                            text=f"🚨 Alerta de Seguridad: Un usuario con chat_id {chat_id} está usando tu bot. En modo producción, este acceso sería bloqueado."
                        )
                    except Exception as e:
                        print(f"Error al enviar alerta de seguridad: {e}")
                # En modo pruebas, continuamos con el procesamiento
            
            # Procesar comandos solo de usuarios autorizados
            if text == "/foto":
                await handle_foto_command(update, None)
                return {"status": "ok"}
            elif text == "/status":
                await handle_status_command(update, None)
                return {"status": "ok"}
            elif text == "/help":
                await handle_help_command(update, None)
                return {"status": "ok"}
        
        return {"status": "ok"}
    except Exception as e:
        print(f"Error processing Telegram webhook: {e}")
        return {"status": "error", "detail": str(e)}

# Ruta principal - Interfaz web
@app.get("/", response_class=HTMLResponse)
async def get_html(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Ruta para configurar el webhook de Telegram (solo para setup inicial)
@app.get("/setup-telegram-webhook")
async def setup_webhook():
    if not bot or not TELEGRAM_TOKEN:
        return {"status": "error", "detail": "Telegram bot not configured"}
    
    # URL del webhook (debe ser HTTPS)
    webhook_url = f"https://esp32-telegram-cloud-cam-backend.onrender.com/telegram-webhook"
    
    try:
        # Configurar el webhook
        result = await bot.set_webhook(url=webhook_url)
        if result:
            return {"status": "ok", "message": f"Webhook configurado en {webhook_url}"}
        else:
            return {"status": "error", "detail": "No se pudo configurar el webhook"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

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
        if bot:
            try:
                with open(filepath, "rb") as photo_file:
                    photo_bytes = photo_file.read()
                from io import BytesIO
                bio = BytesIO(photo_bytes)
                bio.name = os.path.basename(filepath)
                
                # Enviar al chat principal configurado
                if CHAT_ID:
                    background_tasks.add_task(bot.send_photo, chat_id=CHAT_ID, photo=bio)
                    print(f"[DEBUG] Imagen programada para envío a chat principal {CHAT_ID}")
                
                # Enviar a todos los chats que solicitaron la foto
                global pending_photo_requests
                if pending_photo_requests:
                    for requester_chat_id in pending_photo_requests:
                        # Evitar duplicados si el solicitante es el chat principal
                        if requester_chat_id != CHAT_ID:
                            # Crear una nueva copia del BytesIO para cada envío
                            requester_bio = BytesIO(photo_bytes)
                            requester_bio.name = os.path.basename(filepath)
                            background_tasks.add_task(bot.send_photo, chat_id=requester_chat_id, photo=requester_bio)
                            print(f"[DEBUG] Imagen programada para envío a solicitante {requester_chat_id}")
                    
                    # Limpiar la lista de solicitudes pendientes
                    pending_photo_requests = []
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
# To run locally: / Para correr local:
# uvicorn cloud_server:app --reload --port 8000
