"""
Módulo de control de acceso, permisos y rate limiting.
"""
import os
import json
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from telegram import Update

load_dotenv()

# Configuración de acceso
ADMIN_IDS = set(json.loads(os.getenv("ADMIN_IDS", "[]")))
MODO_ACCESO = os.getenv("MODO_ACCESO", "abierto")
USUARIOS_PERMITIDOS = set(json.loads(os.getenv("USUARIOS_PERMITIDOS", "[]")))

# Rate Limiting
MAX_PETICIONES_POR_MINUTO = int(os.getenv("MAX_PETICIONES_POR_MINUTO", "10"))
MAX_AVISOS_ANTES_DE_BAN = 3

# Estado del sistema de rate limiting
peticiones_usuario: dict[int, list[datetime]] = defaultdict(list)
avisos_usuario: dict[int, int] = defaultdict(int)
usuarios_baneados: set[int] = set()


def es_admin(user_id: int) -> bool:
    """Comprueba si un usuario es administrador."""
    return user_id in ADMIN_IDS


def verificar_rate_limit(user_id: int) -> tuple[bool, int]:
    """Verifica si el usuario ha superado el límite de peticiones.
    Devuelve (permitido, peticiones_en_ultimo_minuto)."""
    ahora = datetime.now()
    # Limpiar peticiones antiguas (> 60 segundos)
    peticiones_usuario[user_id] = [
        t for t in peticiones_usuario[user_id]
        if (ahora - t).total_seconds() < 60
    ]
    conteo = len(peticiones_usuario[user_id])

    if conteo >= MAX_PETICIONES_POR_MINUTO:
        return False, conteo

    peticiones_usuario[user_id].append(ahora)
    return True, conteo + 1


async def control_acceso(update: Update, stats_callback=None) -> bool:
    """Verifica permisos y rate limit. Devuelve True si puede continuar.
    
    Args:
        update: Update de Telegram
        stats_callback: Función opcional para registrar usuarios baneados
    """
    user = update.effective_user
    if not user:
        return False

    user_id = user.id

    # Los admins nunca son bloqueados
    if es_admin(user_id):
        return True

    # ¿Está baneado?
    if user_id in usuarios_baneados:
        return False  # Silencio total para baneados

    # Modo restringido: solo usuarios permitidos
    if MODO_ACCESO == "restringido" and user_id not in USUARIOS_PERMITIDOS:
        if update.message:
            await update.message.reply_text("⛔ No tienes permiso para usar este bot.")
        return False

    # Rate limiting
    permitido, conteo = verificar_rate_limit(user_id)
    if not permitido:
        avisos_usuario[user_id] += 1
        if avisos_usuario[user_id] >= MAX_AVISOS_ANTES_DE_BAN:
            usuarios_baneados.add(user_id)
            # Notificar al callback de stats si existe
            if stats_callback:
                stats_callback("baneados")
            if update.message:
                await update.message.reply_text(
                    "🚫 Has sido bloqueado por uso abusivo del bot.\n"
                    "Contacta con un administrador si crees que es un error."
                )
            return False
        else:
            if update.message:
                await update.message.reply_text(
                    f"⚠️ Demasiadas peticiones. Límite: {MAX_PETICIONES_POR_MINUTO}/minuto.\n"
                    f"Aviso {avisos_usuario[user_id]}/{MAX_AVISOS_ANTES_DE_BAN}. "
                    f"Si continúas serás bloqueado."
                )
            return False

    return True


# Variables mutables para comandos de admin
def obtener_modo_acceso():
    """Obtiene el modo de acceso actual."""
    global MODO_ACCESO
    return MODO_ACCESO


def establecer_modo_acceso(nuevo_modo: str):
    """Establece un nuevo modo de acceso."""
    global MODO_ACCESO
    MODO_ACCESO = nuevo_modo


def obtener_max_peticiones():
    """Obtiene el límite actual de peticiones."""
    global MAX_PETICIONES_POR_MINUTO
    return MAX_PETICIONES_POR_MINUTO


def establecer_max_peticiones(nuevo_limite: int):
    """Establece un nuevo límite de peticiones."""
    global MAX_PETICIONES_POR_MINUTO
    MAX_PETICIONES_POR_MINUTO = nuevo_limite


def banear_usuario(user_id: int):
    """Añade un usuario a la lista de baneados."""
    usuarios_baneados.add(user_id)


def desbanear_usuario(user_id: int):
    """Elimina un usuario de la lista de baneados."""
    usuarios_baneados.discard(user_id)
    avisos_usuario.pop(user_id, None)


def permitir_usuario(user_id: int):
    """Añade un usuario a la lista blanca."""
    USUARIOS_PERMITIDOS.add(user_id)


def denegar_usuario(user_id: int):
    """Elimina un usuario de la lista blanca."""
    USUARIOS_PERMITIDOS.discard(user_id)


def obtener_usuarios_baneados() -> set[int]:
    """Devuelve el conjunto de usuarios baneados."""
    return usuarios_baneados
