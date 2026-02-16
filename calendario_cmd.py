"""
Módulo de interacción del calendario laboral.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from acceso import control_acceso
from estadisticas import registrar, incrementar_contador
from calendario import (
    obtener_turnos_usuario, 
    agregar_turno, 
    eliminar_turno,
    eliminar_todos_turnos, 
    obtener_turnos_proximos, 
    formatear_calendario,
    validar_hora, 
    validar_dia,
)


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


async def horario_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /horario — gestiona tu calendario laboral."""
    if not await control_acceso(update):
        return
    registrar("calendario", update)

    await update.message.reply_text(
        "📅 *Calendario laboral*\n\n"
        "Gestiona tus turnos de entrada y salida.\n"
        "Recibirás una notificación 10 minutos antes.",
        parse_mode="Markdown",
        reply_markup=get_calendario_keyboard(),
    )


async def comprobar_notificaciones(context: ContextTypes.DEFAULT_TYPE):
    """Job que se ejecuta cada minuto para enviar notificaciones."""
    turnos = obtener_turnos_proximos(minutos_antes=10)

    for turno in turnos:
        user_id = turno["user_id"]
        tipo = turno["tipo"]
        hora = turno["hora"]
        dia = turno["dia"].capitalize()

        if tipo == "entrada":
            emoji = "🟢"
            msg = (
                f"🔔 *Recordatorio de ENTRADA*\n\n"
                f"{emoji} Tu turno de *entrada* es a las *{hora}*\n"
                f"📅 {dia}\n\n"
                f"⏰ ¡Faltan 10 minutos! Prepárate."
            )
        else:
            emoji = "🔴"
            msg = (
                f"🔔 *Recordatorio de SALIDA*\n\n"
                f"{emoji} Tu turno de *salida* es a las *{hora}*\n"
                f"📅 {dia}\n\n"
                f"⏰ ¡Faltan 10 minutos! Ve terminando."
            )

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=msg,
                parse_mode="Markdown",
            )
            incrementar_contador("notificaciones_enviadas")
        except Exception as e:
            print(f"⚠️ Error enviando notificación a {user_id}: {e}")


# Funciones auxiliares para manejo de callbacks del calendario

async def calendario_ver_callback(query, get_calendario_keyboard_func):
    """Muestra los turnos del calendario."""
    texto = formatear_calendario(query.from_user.id)
    await query.edit_message_text(
        texto,
        parse_mode="Markdown",
        reply_markup=get_calendario_keyboard_func(),
    )


async def calendario_add_callback(query):
    """Inicia el proceso de añadir un turno."""
    dias_btns = [
        [InlineKeyboardButton(d.capitalize(), callback_data=f"caldia_{d}")]
        for d in ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    ]
    dias_btns.append([InlineKeyboardButton("❌ Cancelar", callback_data="btn_calendario")])
    await query.edit_message_text(
        "➕ *Añadir turno*\n\n"
        "Selecciona el día de la semana:\n\n"
        "_También puedes escribir una fecha específica (ej: 20/03/2026)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(dias_btns),
    )


async def calendario_del_callback(query, get_calendario_keyboard_func):
    """Muestra los turnos para eliminar."""
    turnos = obtener_turnos_usuario(query.from_user.id)
    if not turnos:
        await query.edit_message_text(
            "No tienes turnos para eliminar.",
            reply_markup=get_calendario_keyboard_func(),
        )
    else:
        btns = []
        for i, t in enumerate(turnos):
            emoji = "🟢" if t["tipo"] == "entrada" else "🔴"
            label = f"{emoji} {t['dia'].capitalize()} {t['hora']} - {t['tipo']}"
            btns.append([InlineKeyboardButton(label, callback_data=f"caldel_{i}")])
        btns.append([InlineKeyboardButton("◀️ Volver", callback_data="btn_calendario")])
        await query.edit_message_text(
            "❌ *Eliminar turno*\n\nSelecciona el turno a eliminar:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(btns),
        )


async def calendario_clear_callback(query):
    """Confirma el borrado de todos los turnos."""
    await query.edit_message_text(
        "⚠️ ¿Estás seguro de que quieres borrar TODOS tus turnos?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Sí, borrar todo", callback_data="cal_clear_si"),
                InlineKeyboardButton("❌ No", callback_data="btn_calendario"),
            ]
        ]),
    )


async def calendario_clear_si_callback(query, get_calendario_keyboard_func):
    """Ejecuta el borrado de todos los turnos."""
    cantidad = eliminar_todos_turnos(query.from_user.id)
    await query.edit_message_text(
        f"🗑 Se eliminaron {cantidad} turnos.",
        reply_markup=get_calendario_keyboard_func(),
    )


async def calendario_dia_callback(query, dia, context):
    """Procesa la selección de día."""
    context.user_data["cal_dia"] = dia
    context.user_data["cal_paso"] = "hora"
    await query.edit_message_text(
        f"➕ Día: *{dia.capitalize()}*\n\n"
        "⏰ Escribe la hora (formato HH:MM):\n"
        "Ejemplo: 08:00, 14:30, 17:00",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="btn_calendario")]]),
    )


async def calendario_tipo_callback(query, tipo, context, get_calendario_keyboard_func):
    """Procesa la selección de tipo (entrada/salida)."""
    dia = context.user_data.get("cal_dia", "")
    hora = context.user_data.get("cal_hora", "")
    context.user_data["cal_paso"] = None

    ok = agregar_turno(query.from_user.id, dia, hora, tipo)
    if ok:
        emoji = "🟢" if tipo == "entrada" else "🔴"
        await query.edit_message_text(
            f"✅ Turno añadido:\n\n"
            f"📆 Día: {dia.capitalize()}\n"
            f"⏰ Hora: {hora}\n"
            f"{emoji} Tipo: {tipo.capitalize()}\n\n"
            f"_Recibirás notificación a las {hora} (10 min antes)_",
            parse_mode="Markdown",
            reply_markup=get_calendario_keyboard_func(),
        )
    else:
        await query.edit_message_text(
            "⚠️ Ese turno ya existe en tu calendario.",
            reply_markup=get_calendario_keyboard_func(),
        )


async def calendario_del_idx_callback(query, idx, get_calendario_keyboard_func):
    """Elimina un turno específico."""
    turno = eliminar_turno(query.from_user.id, idx)
    if turno:
        await query.edit_message_text(
            f"✅ Turno eliminado: {turno['dia'].capitalize()} {turno['hora']} ({turno['tipo']})",
            reply_markup=get_calendario_keyboard_func(),
        )
    else:
        await query.edit_message_text(
            "❌ No se pudo eliminar el turno.",
            reply_markup=get_calendario_keyboard_func(),
        )


async def procesar_hora_texto(update, context, text):
    """Procesa la hora ingresada como texto."""
    hora = validar_hora(text.strip())
    if not hora:
        await update.message.reply_text(
            "❌ Formato inválido. Escribe la hora como HH:MM (ej: 08:00, 14:30)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="btn_calendario")]]),
        )
        return False

    context.user_data["cal_hora"] = hora
    context.user_data["cal_paso"] = "tipo"
    dia = context.user_data.get("cal_dia", "")
    await update.message.reply_text(
        f"➕ Día: *{dia.capitalize()}* | Hora: *{hora}*\n\n"
        "¿Es una *entrada* o una *salida*?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 Entrada", callback_data="caltipo_entrada"),
                InlineKeyboardButton("🔴 Salida", callback_data="caltipo_salida"),
            ],
            [InlineKeyboardButton("❌ Cancelar", callback_data="btn_calendario")],
        ]),
    )
    return True


async def procesar_dia_texto(update, context, text):
    """Procesa el día ingresado como texto."""
    dia = validar_dia(text.strip())
    if not dia:
        await update.message.reply_text(
            "❌ Día no válido. Usa un día de la semana o una fecha (DD/MM/YYYY)",
        )
        return False

    context.user_data["cal_dia"] = dia
    context.user_data["cal_paso"] = "hora"
    await update.message.reply_text(
        f"➕ Día: *{dia.capitalize()}*\n\n"
        "⏰ Escribe la hora (formato HH:MM):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="btn_calendario")]]),
    )
    return True
