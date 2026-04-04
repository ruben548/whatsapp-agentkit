# agent/voice.py — Transcripción de audio y síntesis de voz
# Groq Whisper (gratis) para escuchar
# ElevenLabs (voz clonada) o edge-tts (fallback gratis) para hablar

import os
import re
import logging
import tempfile
import httpx
import edge_tts
import emoji
from groq import AsyncGroq

logger = logging.getLogger("agentkit")

VOZ_EDGE_TTS = os.getenv("TTS_VOICE", "es-ES-AlvaroNeural")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))


async def transcribir_audio(url_audio: str, token_whapi: str) -> str:
    """Descarga el audio de Whapi y lo transcribe con Groq Whisper."""
    # Whapi requiere el token como query param para descargar media
    url_con_token = f"{url_audio}?token={token_whapi}"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get(url_con_token)
        if r.status_code != 200:
            logger.error(f"Error descargando audio: {r.status_code} — {r.text[:200]}")
            return ""

        audio_bytes = r.content
        if not audio_bytes:
            logger.error("Audio descargado está vacío")
            return ""

        logger.info(f"Audio descargado: {len(audio_bytes)} bytes, content-type: {r.headers.get('content-type', 'unknown')}")

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
        logger.error(f"Error transcribiendo con Groq: {e}")
        return ""


def _limpiar_para_audio(texto: str) -> str:
    """Elimina emojis y asteriscos de markdown antes de sintetizar voz."""
    texto = emoji.replace_emoji(texto, replace="")
    texto = re.sub(r"\*+", "", texto)   # elimina ** y * del markdown
    texto = re.sub(r"#{1,6} ", "", texto)  # elimina encabezados markdown
    return re.sub(r" {2,}", " ", texto).strip()


async def _elevenlabs_tts(texto: str) -> bytes:
    """Sintetiza voz con ElevenLabs (voz clonada, máxima calidad)."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.25,
            "similarity_boost": 0.90,
            "style": 0.40,
            "use_speaker_boost": True,
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code != 200:
            logger.error(f"Error ElevenLabs: {r.status_code} — {r.text}")
            return b""
        logger.info(f"Audio ElevenLabs generado: {len(r.content)} bytes")
        return r.content


async def _edge_tts_fallback(texto: str) -> bytes:
    """Sintetiza voz con edge-tts (Microsoft, gratis) como fallback."""
    comunicador = edge_tts.Communicate(texto, VOZ_EDGE_TTS)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        ruta_temp = f.name
    await comunicador.save(ruta_temp)
    with open(ruta_temp, "rb") as f:
        audio_bytes = f.read()
    os.unlink(ruta_temp)
    return audio_bytes


async def texto_a_audio(texto: str) -> bytes:
    """
    Convierte texto a audio.
    Usa ElevenLabs si está configurado, edge-tts como fallback.
    """
    texto_limpio = _limpiar_para_audio(texto)
    if not texto_limpio:
        return b""

    try:
        if ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
            audio = await _elevenlabs_tts(texto_limpio)
            if audio:
                return audio
            logger.warning("ElevenLabs falló, usando edge-tts como fallback")

        return await _edge_tts_fallback(texto_limpio)

    except Exception as e:
        logger.error(f"Error generando audio: {e}")
        return b""
