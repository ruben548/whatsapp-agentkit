# agent/providers/whapi.py — Adaptador para Whapi.cloud

import os
import base64
import logging
import httpx
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")


class ProveedorWhapi(ProveedorWhatsApp):

    def __init__(self):
        self.token = os.getenv("WHAPI_TOKEN")
        self.url_base = "https://gate.whapi.cloud"

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        body = await request.json()
        logger.info(f"Webhook payload: {body}")
        mensajes = []
        for msg in body.get("messages", []):
            tipo = msg.get("type", "")
            es_propio = msg.get("from_me", False)
            telefono = msg.get("chat_id", "")
            mensaje_id = msg.get("id", "")

            if tipo == "text":
                mensajes.append(MensajeEntrante(
                    telefono=telefono,
                    texto=msg.get("text", {}).get("body", ""),
                    mensaje_id=mensaje_id,
                    es_propio=es_propio,
                ))
            elif tipo in ("audio", "voice"):
                # Mensaje de voz — construir URL de descarga con el ID de media
                audio = msg.get("voice") or msg.get("audio") or {}
                media_id = audio.get("id", "")
                if media_id:
                    audio_url = f"{self.url_base}/media/{media_id}"
                else:
                    audio_url = audio.get("link", "")
                mensajes.append(MensajeEntrante(
                    telefono=telefono,
                    texto="",
                    mensaje_id=mensaje_id,
                    es_propio=es_propio,
                    audio_url=audio_url,
                ))

        return mensajes

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        if not self.token:
            logger.warning("WHAPI_TOKEN no configurado")
            return False
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url_base}/messages/text",
                json={"to": telefono, "body": mensaje},
                headers=headers,
            )
            if r.status_code != 200:
                logger.error(f"Error Whapi texto: {r.status_code} — {r.text}")
            return r.status_code == 200

    async def enviar_audio(self, telefono: str, audio_bytes: bytes) -> bool:
        if not self.token:
            logger.warning("WHAPI_TOKEN no configurado")
            return False
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.url_base}/messages/voice",
                json={"to": telefono, "media": f"data:audio/mpeg;base64,{audio_b64}"},
                headers=headers,
            )
            if r.status_code != 200:
                logger.error(f"Error Whapi audio: {r.status_code} — {r.text}")
            return r.status_code == 200
