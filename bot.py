"""
Bot de Telegram multifuncional - Archivo principal.
Coordina todos los módulos y maneja los handlers.
"""
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, ContextTypes, filters

# Importar módulos propios
from acceso import control_acceso
from estadisticas import registrar, formatear_estadisticas
from bandas import banda_handler, procesar_busqueda_banda_boton
from tiempo import tiempo_handler, ubicacion_handler, enviar_tiempo, geocodificar
from saludos import procesar_saludo
from admin import admin_handler
from comandos import start_handler, stats_handler, miid_handler, get_main_keyboard, get_calendario_keyboard
from calendario_cmd import (
    horario_handler, comprobar_notificaciones,
    calendario_ver_callback, calendario_add_callback, calendario_del_callback,
    calendario_clear_callback, calendario_clear_si_callback,
    calendario_dia_callback, calendario_tipo_callback, calendario_del_idx_callback,
    procesar_hora_texto, procesar_dia_texto,
)

# Configuración
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones inline."""
    if not await control_acceso(update):
        return
    query = update.callback_query
    await query.answer()

    # Botón de estadísticas
    if query.data == "btn_stats":
        registrar("comandos_stats", update)
        msg = formatear_estadisticas()
        from acceso import obtener_usuarios_baneados
        msg += f"🚫 Usuarios baneados: {len(obtener_usuarios_baneados())}\n"
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

    # Botón de búsqueda de banda
    elif query.data == "btn_banda":
        context.user_data["esperando_banda"] = True
        await query.edit_message_text(
            "🎵 Escribe el nombre del grupo que quieres buscar:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="btn_cancelar")]]),
        )

    # Botón de consulta del tiempo
    elif query.data == "btn_tiempo":
        context.user_data["esperando_ciudad"] = True
        await query.edit_message_text(
            "🌤 Escribe el nombre de la ciudad o envía tu ubicación 📍:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="btn_cancelar")]]),
        )

    # Botón de calendario
    elif query.data == "btn_calendario":
        registrar("calendario", update)
        await query.edit_message_text(
            "📅 *Calendario laboral*\n\n"
            "Gestiona tus turnos de entrada y salida.\n"
            "Recibirás una notificación 10 minutos antes.",
            parse_mode="Markdown",
            reply_markup=get_calendario_keyboard(),
        )

    # Botón volver
    elif query.data == "btn_volver":
        await query.edit_message_text(
            "Elige una opción:",
            reply_markup=get_main_keyboard(),
        )

    # Botón cancelar
    elif query.data == "btn_cancelar":
        context.user_data["esperando_banda"] = False
        context.user_data["esperando_ciudad"] = False
        context.user_data["cal_paso"] = None
        await query.edit_message_text(
            "👌 Cancelado. Usa los botones o escribe un comando.",
            reply_markup=get_main_keyboard(),
        )

    # --- Callbacks del calendario ---
    elif query.data == "cal_ver":
        await calendario_ver_callback(query, get_calendario_keyboard)

    elif query.data == "cal_add":
        context.user_data["cal_paso"] = "dia"
        await calendario_add_callback(query)

    elif query.data.startswith("caldia_"):
        dia = query.data.replace("caldia_", "")
        await calendario_dia_callback(query, dia, context)

    elif query.data.startswith("caltipo_"):
        tipo = query.data.replace("caltipo_", "")
        await calendario_tipo_callback(query, tipo, context, get_calendario_keyboard)

    elif query.data == "cal_del":
        await calendario_del_callback(query, get_calendario_keyboard)

    elif query.data.startswith("caldel_"):
        idx = int(query.data.replace("caldel_", ""))
        await calendario_del_idx_callback(query, idx, get_calendario_keyboard)

    elif query.data == "cal_clear":
        await calendario_clear_callback(query)

    elif query.data == "cal_clear_si":
        await calendario_clear_si_callback(query, get_calendario_keyboard)


async def responder_mensaje_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto generales, incluyendo flujos de conversación."""
    if not await control_acceso(update):
        return

    # Si estamos esperando hora para el calendario
    if context.user_data.get("cal_paso") == "hora":
        await procesar_hora_texto(update, context, update.message.text)
        return

    # Si estamos esperando un día escrito (fecha específica)
    if context.user_data.get("cal_paso") == "dia":
        await procesar_dia_texto(update, context, update.message.text)
        return

    # Si estamos esperando una ciudad desde el botón de tiempo
    if context.user_data.get("esperando_ciudad"):
        context.user_data["esperando_ciudad"] = False
        registrar("tiempo", update)
        ciudad = update.message.text.strip()
        await update.message.reply_text(f"🔍 Buscando el tiempo en *{ciudad}*...", parse_mode="Markdown")

        geo = await geocodificar(ciudad)
        if not geo:
            await update.message.reply_text(f"❌ No encontré la ciudad «{ciudad}».", reply_markup=get_main_keyboard())
            return

        lat, lon, nombre = geo
        await enviar_tiempo(update, lat, lon, nombre, es_boton=True, get_main_keyboard_func=get_main_keyboard)
        return

    # Si estamos esperando un nombre de banda desde el botón
    if context.user_data.get("esperando_banda"):
        context.user_data["esperando_banda"] = False
        nombre = update.message.text.strip()
        await procesar_busqueda_banda_boton(update, context, nombre, get_main_keyboard)
        return

    # Si no hay ningún flujo activo, procesar como saludo
    await procesar_saludo(update, context)


def main():
    """Función principal que inicia el bot."""
    if not TOKEN:
        print("❌ Error: Define la variable de entorno TELEGRAM_BOT_TOKEN con el token de tu bot.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    # Registrar handlers de comandos
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("banda", banda_handler))
    app.add_handler(CommandHandler("tiempo", tiempo_handler))
    app.add_handler(CommandHandler("horario", horario_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CommandHandler("miid", miid_handler))
    app.add_handler(CommandHandler("admin", admin_handler))

    # Handlers de interacción
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, ubicacion_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_mensaje_texto))

    # Programar comprobación de notificaciones cada 60 segundos
    job_queue = app.job_queue
    job_queue.run_repeating(comprobar_notificaciones, interval=60, first=10)
    print("📅 Notificaciones de calendario activadas (cada 60s)")

    print("🤖 Bot iniciado. Esperando mensajes...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app.run_polling()


if __name__ == "__main__":
    main()
