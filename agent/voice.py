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
    # Whapi: primero obtener la URL real del media, luego descargarla
    headers_auth = {"Authorization": f"Bearer {token_whapi}"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        # Paso 1: GET con auth para obtener redirect a URL real
        r = await client.get(url_audio, headers=headers_auth)
        logger.info(f"Whapi paso 1: status={r.status_code}, location={r.headers.get('location', 'none')}, size={len(r.content)}")

        if r.status_code in (301, 302, 303, 307, 308):
            # Hay redirección — seguirla sin el header de auth
            redirect_url = r.headers.get("location", "")
            r2 = await client.get(redirect_url)
            logger.info(f"Whapi paso 2 (redirect): status={r2.status_code}, size={len(r2.content)}")
            audio_bytes = r2.content
        elif r.status_code == 200 and len(r.content) > 0:
            audio_bytes = r.content
        else:
            # Intentar con token como query param
            url_con_token = f"{url_audio}?token={token_whapi}"
            r3 = await client.get(url_con_token, follow_redirects=True)
            logger.info(f"Whapi paso 2 (query token): status={r3.status_code}, size={len(r3.content)}")
            audio_bytes = r3.content

        if not audio_bytes:
            logger.error("Audio descargado está vacío después de todos los intentos")
            return ""

        logger.info(f"Audio descargado: {len(audio_bytes)} bytes")

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
