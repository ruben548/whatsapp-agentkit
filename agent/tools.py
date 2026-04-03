# agent/tools.py — Herramientas del agente
# Generado por AgentKit

import os
import yaml
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")


def cargar_info_negocio() -> dict:
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> dict:
    info = cargar_info_negocio()
    return {
        "horario": info.get("negocio", {}).get("horario", "No disponible"),
        "esta_abierto": True,
    }


def buscar_en_knowledge(consulta: str) -> str:
    resultados = []
    knowledge_dir = "knowledge"

    if not os.path.exists(knowledge_dir):
        return "No hay archivos de conocimiento disponibles."

    for archivo in os.listdir(knowledge_dir):
        ruta = os.path.join(knowledge_dir, archivo)
        if archivo.startswith(".") or not os.path.isfile(ruta):
            continue
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
                if consulta.lower() in contenido.lower():
                    resultados.append(f"[{archivo}]: {contenido[:500]}")
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        return "\n---\n".join(resultados)
    return "No encontré información específica sobre eso en mis archivos."


def registrar_lead(telefono: str, nombre: str, interes: str) -> str:
    """Registra un lead cualificado para seguimiento."""
    timestamp = datetime.utcnow().isoformat()
    logger.info(f"LEAD REGISTRADO — {timestamp} | {telefono} | {nombre} | {interes}")
    return f"Lead registrado: {nombre}"


def calificar_lead(tiene_audiencia: bool, tiene_negocio: bool, facturacion_actual: str) -> str:
    """Determina si el lead es apto para una llamada con Rubén."""
    if tiene_audiencia or tiene_negocio:
        return "CALIFICADO — Agendar llamada de diagnóstico"
    return "NURTURING — Continuar educando sobre el método"


def escalar_a_ruben(telefono: str, contexto: str) -> str:
    """Escala la conversación a Rubén para cierre o llamada."""
    logger.info(f"ESCALAR A RUBÉN — {telefono}: {contexto}")
    return "Voy a conectarte directamente con Rubén. Te contactará en breve."
