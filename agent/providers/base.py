# agent/providers/base.py — Clase base para proveedores de WhatsApp

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from fastapi import Request


@dataclass
class MensajeEntrante:
    """Mensaje normalizado — mismo formato sin importar el proveedor."""
    telefono: str
    texto: str
    mensaje_id: str
    es_propio: bool
    audio_url: str = field(default="")  # URL del audio si el mensaje es de voz


class ProveedorWhatsApp(ABC):

    @abstractmethod
    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        ...

    @abstractmethod
    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        ...

    async def enviar_audio(self, _telefono: str, _audio_bytes: bytes) -> bool:
        """Envía un mensaje de audio. Los proveedores pueden sobreescribir este método."""
        return False

    async def validar_webhook(self, request: Request) -> dict | int | None:
        return None
