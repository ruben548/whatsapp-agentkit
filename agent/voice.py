# agent/voice.py — Transcripción de audio y síntesis de voz
# Groq Whisper (gratis) para escuchar, edge-tts (gratis) para hablar

import os
import logging
import tempfile
import httpx
import edge_tts
from groq import AsyncGroq

logger = logging.getLogger("agentkit")

# Voz en español de Microsoft (edge-tts) — suena natural
VOZ_ESPAÑOL = os.getenv("TTS_VOICE", "es-ES-AlvaroNeural")

groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))


async def transcribir_audio(url_audio: str, token_whapi: str) -> str:
    """
    Descarga el audio de Whapi y lo transcribe con Groq Whisper.
    Retorna el texto transcrito.
    """
    # Descargar audio de Whapi
    headers = {"Authorization": f"Bearer {token_whapi}"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url_audio, headers=headers)
        if r.status_code != 200:
            logger.error(f"Error descargando audio: {r.status_code}")
            return ""
        audio_bytes = r.content

    # Transcribir con Groq Whisper
    try:
        transcripcion = await groq_client.audio.transcriptions.create(
            file=("audio.ogg", audio_bytes, "audio/ogg"),
            model="whisper-large-v3",
            language="es",
        )
        texto = transcripcion.text.strip()
        logger.info(f"Audio transcrito: {texto}")
        return texto
    except Exception as e:
        logger.error(f"Error transcribiendo audio con Groq: {e}")
        return ""


async def texto_a_audio(texto: str) -> bytes:
    """
    Convierte texto a audio MP3 usando edge-tts (Microsoft, completamente gratis).
    Retorna los bytes del audio en formato MP3.
    """
    try:
        comunicador = edge_tts.Communicate(texto, VOZ_ESPAÑOL)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            ruta_temp = f.name

        await comunicador.save(ruta_temp)

        with open(ruta_temp, "rb") as f:
            audio_bytes = f.read()

        os.unlink(ruta_temp)
        logger.info(f"Audio generado: {len(audio_bytes)} bytes")
        return audio_bytes

    except Exception as e:
        logger.error(f"Error generando audio con edge-tts: {e}")
        return b""
