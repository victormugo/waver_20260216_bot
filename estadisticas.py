"""
Módulo de estadísticas y registro de actividad.
"""
import asyncio
from datetime import datetime
from telegram import Update
from notificaciones import notificar_accion

# Nombres legibles para las acciones
ACCIONES_NOMBRE = {
    "saludos": "Saludo",
    "bandas": "Búsqueda de banda",
    "tiempo": "Consulta del tiempo",
    "calendario": "Calendario laboral",
    "comandos_start": "Comando /start",
    "comandos_stats": "Comando /stats",
}

# Estadísticas globales
STATS = {
    "inicio": datetime.now(),
    "total": 0,
    "saludos": 0,
    "bandas": 0,
    "tiempo": 0,
    "calendario": 0,
    "comandos_start": 0,
    "comandos_stats": 0,
    "usuarios": set(),
    "notificaciones_enviadas": 0,
}


def registrar(tipo: str, update: Update):
    """Registra una petición en las estadísticas y notifica por email."""
    STATS["total"] += 1
    STATS[tipo] += 1
    if update.effective_user:
        STATS["usuarios"].add(update.effective_user.id)
        # Enviar email de notificación (transparente, en background)
        nombre = update.effective_user.full_name or "Desconocido"
        user_id = update.effective_user.id
        accion = ACCIONES_NOMBRE.get(tipo, tipo)
        asyncio.create_task(notificar_accion(nombre, user_id, accion))


def obtener_estadisticas() -> dict:
    """Devuelve una copia de las estadísticas actuales."""
    return STATS.copy()


def incrementar_contador(tipo: str):
    """Incrementa un contador específico."""
    if tipo in STATS:
        STATS[tipo] += 1


def formatear_estadisticas() -> str:
    """Formatea las estadísticas para mostrar en Telegram."""
    uptime = datetime.now() - STATS["inicio"]
    horas, resto = divmod(int(uptime.total_seconds()), 3600)
    minutos, segundos = divmod(resto, 60)

    msg = (
        "📊 *Estadísticas del bot*\n\n"
        f"⏱ Uptime: {horas}h {minutos}m {segundos}s\n"
        f"📨 Peticiones totales: {STATS['total']}\n\n"
        f"👋 Saludos: {STATS['saludos']}\n"
        f"🎸 Búsquedas de bandas: {STATS['bandas']}\n"
        f"🌤 Consultas de tiempo: {STATS['tiempo']}\n"
        f"📅 Calendario: {STATS['calendario']}\n"
        f"▶️ Comandos /start: {STATS['comandos_start']}\n"
        f"📊 Comandos /stats: {STATS['comandos_stats']}\n\n"
        f"👥 Usuarios únicos: {len(STATS['usuarios'])}\n"
        f"🔔 Notificaciones enviadas: {STATS['notificaciones_enviadas']}\n"
    )
    return msg
