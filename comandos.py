"""
Módulo de comandos principales del bot.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from acceso import control_acceso, obtener_usuarios_baneados
from estadisticas import registrar, formatear_estadisticas


def get_main_keyboard():
    """Devuelve el teclado inline con los botones principales."""
    keyboard = [
        [
            InlineKeyboardButton("🎸 Buscar banda", callback_data="btn_banda"),
            InlineKeyboardButton("🌤 Tiempo", callback_data="btn_tiempo"),
        ],
        [
            InlineKeyboardButton("📅 Calendario", callback_data="btn_calendario"),
            InlineKeyboardButton("📊 Estadísticas", callback_data="btn_stats"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_calendario_keyboard():
    """Devuelve el teclado del calendario."""
    keyboard = [
        [
            InlineKeyboardButton("➕ Añadir turno", callback_data="cal_add"),
            InlineKeyboardButton("📄 Ver turnos", callback_data="cal_ver"),
        ],
        [
            InlineKeyboardButton("❌ Eliminar turno", callback_data="cal_del"),
            InlineKeyboardButton("🗑 Borrar todo", callback_data="cal_clear"),
        ],
        [
            InlineKeyboardButton("◀️ Volver", callback_data="btn_volver"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde al comando /start."""
    if not await control_acceso(update):
        return
    registrar("comandos_start", update)
    await update.message.reply_text(
        "¡Hola! 👋 Soy un bot multifunción.\n\n"
        "🎵 /banda <nombre> — Discografía de un grupo\n"
        "🌤 /tiempo <ciudad> — Tiempo actual y previsión\n"
        "📅 /horario — Calendario laboral\n"
        "📊 /stats — Estadísticas del bot\n"
        "👋 O escríbeme un saludo\n\n"
        "También puedes usar los botones de abajo:",
        reply_markup=get_main_keyboard(),
    )


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /stats — muestra estadísticas del bot."""
    if not await control_acceso(update):
        return
    registrar("comandos_stats", update)
    
    msg = formatear_estadisticas()
    
    # Añadir usuarios baneados al mensaje
    usuarios_baneados = obtener_usuarios_baneados()
    msg += f"🚫 Usuarios baneados: {len(usuarios_baneados)}\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def miid_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /miid — muestra tu ID de Telegram."""
    user = update.effective_user
    await update.message.reply_text(
        f"🆔 Tu ID de Telegram es: `{user.id}`\n"
        f"👤 Nombre: {user.full_name}\n\n"
        f"Añade este número a ADMIN\\_IDS en el archivo .env para ser administrador.",
        parse_mode="Markdown",
    )
