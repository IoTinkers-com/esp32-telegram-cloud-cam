# cloud_server.py
# FastAPI + Telegram + WebSocket server for Render.com
# Servidor FastAPI + Telegram + WebSocket para Render.com
# - Receives Telegram messages / Recibe mensajes de Telegram
# - Sends commands to ESP32 via WebSocket / Envía comandos al ESP32 vía WebSocket
# - Receives images from ESP32 and sends to Telegram / Recibe imágenes del ESP32 y las reenvía a Telegram

import os
import asyncio
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv
load_dotenv()  # Load .env file / Carga el archivo .env

# Get Telegram credentials from environment variables
# Obtiene credenciales de Telegram desde variables de entorno
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Initialize Telegram bot
# Inicializa el bot de Telegram
bot = Bot(token=TELEGRAM_TOKEN)
# Create FastAPI app
# Crea la app FastAPI
app = FastAPI()
# Store connected ESP32 clients (WebSocket)
# Almacena clientes ESP32 conectados (WebSocket)
esp32_clients = set()

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()  # Accept client / Acepta cliente
    esp32_clients.add(websocket)  # Add to set / Agrega al conjunto
    try:
        while True:
            data = await websocket.receive_bytes()  # Receive image / Recibe imagen
            if data and CHAT_ID:
                # Send photo to Telegram / Envía foto a Telegram
                await bot.send_photo(chat_id=CHAT_ID, photo=data)
    except WebSocketDisconnect:
        # Remove client on disconnect / Elimina cliente al desconectar
        pass
    finally:
        esp32_clients.remove(websocket)

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()  # Get Telegram message / Obtiene mensaje de Telegram
    msg = data.get("message", {}).get("text", "")
    chat_id = data.get("message", {}).get("chat", {}).get("id")
    if msg and chat_id:
        # Relay command to all ESP32 / Reenvía comando a todos los ESP32
        for ws in list(esp32_clients):
            await ws.send_text("TAKE_PHOTO")
        # Confirm to user / Confirma al usuario
        await bot.send_message(chat_id=chat_id, text="¡Tomando foto! / Taking photo!")
    return {"ok": True}

@app.post("/upload")
async def upload_photo(req: Request):
    form = await req.form()  # Receive form / Recibe formulario
    photo = await form["photo"].read()  # Read photo / Lee la foto
    await bot.send_photo(chat_id=CHAT_ID, photo=photo)  # Send to Telegram / Envía a Telegram
    return {"ok": True}

# To run locally: / Para correr local:
# uvicorn cloud_server:app --reload --port 8000
