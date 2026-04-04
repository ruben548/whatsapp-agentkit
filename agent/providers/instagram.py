# agent/providers/instagram.py — Adaptador para Instagram Direct Messages via Meta Graph API

import os
import logging
import httpx
from fastapi import Request

logger = logging.getLogger("agentkit")

INSTAGRAM_API_URL = "https://graph.instagram.com/v21.0"


async def enviar_dm_instagram(recipient_id: str, mensaje: str) -> bool:
    """Envía un mensaje directo a un usuario de Instagram via Meta Graph API."""
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    ig_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

    if not token or not ig_id:
        logger.error("INSTAGRAM_ACCESS_TOKEN o INSTAGRAM_BUSINESS_ACCOUNT_ID no configurados")
        return False

    url = f"{INSTAGRAM_API_URL}/{ig_id}/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": mensaje},
    }
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code != 200:
            logger.error(f"Error enviando DM Instagram: {r.status_code} — {r.text}")
            return False
        logger.info(f"DM Instagram enviado a {recipient_id}")
        return True


def parsear_evento_instagram(body: dict) -> list[dict]:
    """
    Parsea el payload del webhook de Instagram y devuelve lista de mensajes.
    Cada mensaje: {"sender_id": str, "texto": str, "mensaje_id": str}
    """
    mensajes = []
    ig_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

    for entry in body.get("entry", []):
        for evento in entry.get("messaging", []):
            sender = evento.get("sender", {}).get("id", "")
            recipient = evento.get("recipient", {}).get("id", "")

            # Ignorar mensajes que envía el propio bot
            if sender == ig_id or recipient == sender:
                continue

            message = evento.get("message", {})
            texto = message.get("text", "").strip()
            mensaje_id = message.get("mid", "")

            if texto and mensaje_id:
                mensajes.append({
                    "sender_id": sender,
                    "texto": texto,
                    "mensaje_id": mensaje_id,
                })

    return mensajes
