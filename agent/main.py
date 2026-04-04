# agent/main.py — Servidor FastAPI + Webhook de WhatsApp

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
from agent.providers import obtener_proveedor
from agent.providers.instagram import parsear_evento_instagram, enviar_dm_instagram
from agent.voice import transcribir_audio, texto_a_audio

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield


app = FastAPI(
    title="AgentKit — Rubén Gil Pérez",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "agentkit-rubengil"}


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            if msg.es_propio:
                continue

            es_audio = bool(msg.audio_url)

            if es_audio:
                # Mensaje de voz — transcribir primero
                whapi_token = os.getenv("WHAPI_TOKEN", "")
                texto_usuario = await transcribir_audio(msg.audio_url, whapi_token)
                if not texto_usuario:
                    logger.warning(f"No se pudo transcribir audio de {msg.telefono}")
                    continue
                logger.info(f"Audio de {msg.telefono} transcrito: {texto_usuario}")
            elif msg.texto:
                texto_usuario = msg.texto
            else:
                continue

            historial = await obtener_historial(msg.telefono)
            respuesta = await generar_respuesta(texto_usuario, historial)

            await guardar_mensaje(msg.telefono, "user", texto_usuario)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)

            if es_audio:
                # Responder con voz
                audio_bytes = await texto_a_audio(respuesta)
                if audio_bytes:
                    await proveedor.enviar_audio(msg.telefono, audio_bytes)
                else:
                    # Fallback a texto si falla el TTS
                    await proveedor.enviar_mensaje(msg.telefono, respuesta)
            else:
                await proveedor.enviar_mensaje(msg.telefono, respuesta)

            logger.info(f"Respuesta a {msg.telefono} ({'audio' if es_audio else 'texto'}): {respuesta}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/instagram-query")
async def instagram_query_handler(request: Request):
    """Endpoint alternativo para ManyChat — acepta variables como query parameters."""
    try:
        params = request.query_params
        user_id = params.get("subscriber_id", "desconocido")
        mensaje = params.get("message", "").strip()
        nombre = params.get("first_name", "")

        if not mensaje:
            return {"response": "Disculpa, no entendí tu mensaje. ¿Puedes contarme más?"}

        clave = f"ig_{user_id}"
        logger.info(f"Instagram DM (query) de {nombre} ({user_id}): {mensaje}")

        historial = await obtener_historial(clave)
        respuesta = await generar_respuesta(mensaje, historial)

        await guardar_mensaje(clave, "user", mensaje)
        await guardar_mensaje(clave, "assistant", respuesta)

        logger.info(f"Respuesta Instagram a {user_id}: {respuesta}")
        return {"response": respuesta}

    except Exception as e:
        logger.error(f"Error en Instagram query handler: {e}")
        return {"response": "Estoy teniendo un pequeño problema técnico. Vuelvo en un momento."}


@app.get("/webhook/instagram")
async def instagram_verificacion(request: Request):
    """Verificación del webhook de Meta — devuelve el hub.challenge."""
    params = request.query_params
    verify_token = os.getenv("INSTAGRAM_VERIFY_TOKEN", "agentkit_instagram")
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == verify_token
    ):
        return PlainTextResponse(params.get("hub.challenge", ""))
    raise HTTPException(status_code=403, detail="Token de verificación incorrecto")


@app.post("/webhook/instagram")
async def instagram_webhook_handler(request: Request):
    """Recibe eventos de Instagram Direct Messages via Meta Graph API."""
    try:
        body = await request.json()
        mensajes = parsear_evento_instagram(body)

        for msg in mensajes:
            sender_id = msg["sender_id"]
            texto = msg["texto"]

            clave = f"ig_{sender_id}"
            logger.info(f"Instagram DM de {sender_id}: {texto}")

            historial = await obtener_historial(clave)
            respuesta = await generar_respuesta(texto, historial)

            await guardar_mensaje(clave, "user", texto)
            await guardar_mensaje(clave, "assistant", respuesta)

            await enviar_dm_instagram(sender_id, respuesta)
            logger.info(f"Respuesta Instagram a {sender_id}: {respuesta}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook Instagram: {e}")
        return {"status": "ok"}  # Siempre devolver 200 a Meta
