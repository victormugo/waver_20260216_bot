import os
import asyncio
import httpx
import json
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, ContextTypes, filters

from calendario import (
    obtener_turnos_usuario, agregar_turno, eliminar_turno,
    eliminar_todos_turnos, obtener_turnos_proximos, formatear_calendario,
    validar_hora, validar_dia, DIAS_SEMANA, DIAS_SEMANA_NOMBRE,
)
from notificaciones import notificar_accion

# --- Configuración ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# IDs de administradores (pueden gestionar el bot). Pon tu user ID aquí.
# Para saber tu ID, arranca el bot y escríbele /miid
ADMIN_IDS = set(json.loads(os.getenv("ADMIN_IDS", "[]")))

# Modo de acceso: "abierto" (todos pueden usar), "restringido" (solo whitelist)
MODO_ACCESO = os.getenv("MODO_ACCESO", "abierto")

# Lista blanca de usuarios permitidos (solo aplica en modo restringido)
USUARIOS_PERMITIDOS: set[int] = set(json.loads(os.getenv("USUARIOS_PERMITIDOS", "[]")))

# --- Rate Limiting ---
MAX_PETICIONES_POR_MINUTO = int(os.getenv("MAX_PETICIONES_POR_MINUTO", "10"))
MAX_AVISOS_ANTES_DE_BAN = 3  # Avisos antes de bloqueo automático

# Registro de peticiones por usuario: {user_id: [timestamps]}
peticiones_usuario: dict[int, list[datetime]] = defaultdict(list)
avisos_usuario: dict[int, int] = defaultdict(int)
usuarios_baneados: set[int] = set()

MUSICBRAINZ_BASE = "https://musicbrainz.org/ws/2"
HEADERS_MB = {"User-Agent": "TelegramMusicBot/1.0 (bot_telegram)", "Accept": "application/json"}

# --- API del tiempo (Open-Meteo, gratuita, sin API key) ---
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

# Mapeo de códigos WMO a emojis/descripciones
WMO_CODES = {
    0: ("☀️", "Despejado"),
    1: ("🌤", "Mayormente despejado"),
    2: ("⛅", "Parcialmente nublado"),
    3: ("☁️", "Nublado"),
    45: ("🌫️", "Niebla"),
    48: ("🌫️", "Niebla con escarcha"),
    51: ("🌦", "Llovizna ligera"),
    53: ("🌦", "Llovizna moderada"),
    55: ("🌦", "Llovizna intensa"),
    61: ("🌧", "Lluvia ligera"),
    63: ("🌧", "Lluvia moderada"),
    65: ("🌧", "Lluvia intensa"),
    71: ("❄️", "Nevada ligera"),
    73: ("❄️", "Nevada moderada"),
    75: ("❄️", "Nevada intensa"),
    80: ("🌦", "Chubascos ligeros"),
    81: ("🌧", "Chubascos moderados"),
    82: ("🌧", "Chubascos intensos"),
    95: ("⛈", "Tormenta"),
    96: ("⛈", "Tormenta con granizo ligero"),
    99: ("⛈", "Tormenta con granizo"),
}

# --- Estadísticas ---
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

# Saludos reconocidos y sus respuestas
SALUDOS = {
    "hola": "¡Hola! 👋 ¿Cómo estás?",
    "hi": "Hi there! 👋",
    "hello": "Hello! 👋",
    "buenos días": "¡Buenos días! ☀️",
    "buenos dias": "¡Buenos días! ☀️",
    "buenas tardes": "¡Buenas tardes! 🌤️",
    "buenas noches": "¡Buenas noches! 🌙",
    "qué tal": "¡Muy bien! ¿Y tú? 😊",
    "que tal": "¡Muy bien! ¿Y tú? 😊",
    "hey": "¡Hey! ¿Qué tal? 😄",
    "saludos": "¡Saludos! 🤗",
}


# Nombres legibles para las acciones
ACCIONES_NOMBRE = {
    "saludos": "Saludo",
    "bandas": "Búsqueda de banda",
    "tiempo": "Consulta del tiempo",
    "calendario": "Calendario laboral",
    "comandos_start": "Comando /start",
    "comandos_stats": "Comando /stats",
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


async def control_acceso(update: Update) -> bool:
    """Verifica permisos y rate limit. Devuelve True si puede continuar."""
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
        msg = update.message or (update.callback_query and update.callback_query.message)
        if update.message:
            await update.message.reply_text("⛔ No tienes permiso para usar este bot.")
        return False

    # Rate limiting
    permitido, conteo = verificar_rate_limit(user_id)
    if not permitido:
        avisos_usuario[user_id] += 1
        if avisos_usuario[user_id] >= MAX_AVISOS_ANTES_DE_BAN:
            usuarios_baneados.add(user_id)
            STATS.setdefault("baneados", 0)
            STATS["baneados"] = STATS.get("baneados", 0) + 1
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


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /stats — muestra estadísticas del bot."""
    if not await control_acceso(update):
        return
    registrar("comandos_stats", update)
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
        f"🚫 Usuarios baneados: {len(usuarios_baneados)}\n"
        f"🔔 Notificaciones enviadas: {STATS['notificaciones_enviadas']}\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def miid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /miid — muestra tu ID de Telegram."""
    user = update.effective_user
    await update.message.reply_text(
        f"🆔 Tu ID de Telegram es: `{user.id}`\n"
        f"👤 Nombre: {user.full_name}\n\n"
        f"Añade este número a ADMIN\\_IDS en el archivo .env para ser administrador.",
        parse_mode="Markdown",
    )


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /admin — panel de administración (solo admins)."""
    user = update.effective_user
    if not user or not es_admin(user.id):
        await update.message.reply_text("⛔ No tienes permisos de administrador.")
        return

    if not context.args:
        await update.message.reply_text(
            "🛠 *Comandos de administración:*\n\n"
            "/admin ban <user\\_id> — Bloquear usuario\n"
            "/admin unban <user\\_id> — Desbloquear usuario\n"
            "/admin allow <user\\_id> — Añadir a lista blanca\n"
            "/admin deny <user\\_id> — Quitar de lista blanca\n"
            "/admin modo <abierto|restringido> — Cambiar modo\n"
            "/admin baneados — Ver usuarios bloqueados\n"
            "/admin ratelimit <número> — Cambiar límite/minuto",
            parse_mode="Markdown",
        )
        return

    accion = context.args[0].lower()

    if accion == "ban" and len(context.args) >= 2:
        try:
            uid = int(context.args[1])
            usuarios_baneados.add(uid)
            await update.message.reply_text(f"🚫 Usuario {uid} bloqueado.")
        except ValueError:
            await update.message.reply_text("❌ ID inválido.")

    elif accion == "unban" and len(context.args) >= 2:
        try:
            uid = int(context.args[1])
            usuarios_baneados.discard(uid)
            avisos_usuario.pop(uid, None)
            await update.message.reply_text(f"✅ Usuario {uid} desbloqueado.")
        except ValueError:
            await update.message.reply_text("❌ ID inválido.")

    elif accion == "allow" and len(context.args) >= 2:
        try:
            uid = int(context.args[1])
            USUARIOS_PERMITIDOS.add(uid)
            await update.message.reply_text(f"✅ Usuario {uid} añadido a la lista blanca.")
        except ValueError:
            await update.message.reply_text("❌ ID inválido.")

    elif accion == "deny" and len(context.args) >= 2:
        try:
            uid = int(context.args[1])
            USUARIOS_PERMITIDOS.discard(uid)
            await update.message.reply_text(f"❌ Usuario {uid} eliminado de la lista blanca.")
        except ValueError:
            await update.message.reply_text("❌ ID inválido.")

    elif accion == "modo" and len(context.args) >= 2:
        global MODO_ACCESO
        nuevo_modo = context.args[1].lower()
        if nuevo_modo in ("abierto", "restringido"):
            MODO_ACCESO = nuevo_modo
            emoji = "🔓" if nuevo_modo == "abierto" else "🔒"
            await update.message.reply_text(f"{emoji} Modo cambiado a: *{nuevo_modo}*", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Modos válidos: abierto, restringido")

    elif accion == "baneados":
        if usuarios_baneados:
            lista = "\n".join(f"  • {uid}" for uid in usuarios_baneados)
            await update.message.reply_text(f"🚫 *Usuarios bloqueados:*\n{lista}", parse_mode="Markdown")
        else:
            await update.message.reply_text("✅ No hay usuarios bloqueados.")

    elif accion == "ratelimit" and len(context.args) >= 2:
        global MAX_PETICIONES_POR_MINUTO
        try:
            nuevo = int(context.args[1])
            if nuevo < 1:
                raise ValueError
            MAX_PETICIONES_POR_MINUTO = nuevo
            await update.message.reply_text(f"✅ Límite cambiado a {nuevo} peticiones/minuto.")
        except ValueError:
            await update.message.reply_text("❌ Número inválido. Usa un entero positivo.")

    else:
        await update.message.reply_text("❌ Comando no reconocido. Escribe /admin para ver la ayuda.")


def get_main_keyboard():
    """Devuelve el teclado inline con los botones principales."""
    keyboard = [
        [
            InlineKeyboardButton("🎸 Buscar banda", callback_data="btn_banda"),
            InlineKeyboardButton("🌤 Tiempo", callback_data="btn_tiempo"),
        ],
        [
            InlineKeyboardButton("� Calendario", callback_data="btn_calendario"),
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde al comando /start."""
    if not await control_acceso(update):
        return
    registrar("comandos_start", update)
    await update.message.reply_text(
        "¡Hola! 👋 Soy un bot multifunción.\n\n"
        "🎵 /banda <nombre> — Discografía de un grupo\n"
        "🌤 /tiempo <ciudad> — Tiempo actual y previsión\n"
        "� /horario — Calendario laboral\n"
        "�📊 /stats — Estadísticas del bot\n"
        "👋 O escríbeme un saludo\n\n"
        "También puedes usar los botones de abajo:",
        reply_markup=get_main_keyboard(),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones inline."""
    if not await control_acceso(update):
        return
    query = update.callback_query
    await query.answer()

    if query.data == "btn_stats":
        registrar("comandos_stats", update)
        uptime = datetime.now() - STATS["inicio"]
        horas, resto = divmod(int(uptime.total_seconds()), 3600)
        minutos, segundos = divmod(resto, 60)

        msg = (
            "📊 *Estadísticas del bot*\n\n"
            f"⏱ Uptime: {horas}h {minutos}m {segundos}s\n"
            f"📨 Peticiones totales: {STATS['total']}\n\n"
            f"👋 Saludos: {STATS['saludos']}\n"
            f"🎸 Búsquedas de bandas: {STATS['bandas']}\n"        f"🌤 Consultas de tiempo: {STATS['tiempo']}\n"
        f"📅 Calendario: {STATS['calendario']}\n"
        f"▶️ Comandos /start: {STATS['comandos_start']}\n"
            f"📊 Comandos /stats: {STATS['comandos_stats']}\n\n"
            f"👥 Usuarios únicos: {len(STATS['usuarios'])}\n"
        )
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif query.data == "btn_banda":
        context.user_data["esperando_banda"] = True
        await query.edit_message_text(
            "🎵 Escribe el nombre del grupo que quieres buscar:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="btn_cancelar")]]),
        )

    elif query.data == "btn_tiempo":
        context.user_data["esperando_ciudad"] = True
        await query.edit_message_text(
            "🌤 Escribe el nombre de la ciudad o envía tu ubicación 📍:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="btn_cancelar")]]),
        )

    elif query.data == "btn_calendario":
        registrar("calendario", update)
        await query.edit_message_text(
            "📅 *Calendario laboral*\n\n"
            "Gestiona tus turnos de entrada y salida.\n"
            "Recibirás una notificación 10 minutos antes.",
            parse_mode="Markdown",
            reply_markup=get_calendario_keyboard(),
        )

    elif query.data == "btn_volver":
        await query.edit_message_text(
            "Elige una opción:",
            reply_markup=get_main_keyboard(),
        )

    elif query.data == "cal_ver":
        texto = formatear_calendario(update.effective_user.id)
        await query.edit_message_text(
            texto,
            parse_mode="Markdown",
            reply_markup=get_calendario_keyboard(),
        )

    elif query.data == "cal_add":
        context.user_data["cal_paso"] = "dia"
        dias_btns = [
            [InlineKeyboardButton(d.capitalize(), callback_data=f"caldia_{d}")]
            for d in ["lunes", "martes", "mi\u00e9rcoles", "jueves", "viernes", "s\u00e1bado", "domingo"]
        ]
        dias_btns.append([InlineKeyboardButton("❌ Cancelar", callback_data="btn_calendario")])
        await query.edit_message_text(
            "➕ *A\u00f1adir turno*\n\n"
            "Selecciona el d\u00eda de la semana:\n\n"
            "_Tambi\u00e9n puedes escribir una fecha espec\u00edfica (ej: 20/03/2026)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(dias_btns),
        )

    elif query.data.startswith("caldia_"):
        dia = query.data.replace("caldia_", "")
        context.user_data["cal_dia"] = dia
        context.user_data["cal_paso"] = "hora"
        await query.edit_message_text(
            f"➕ D\u00eda: *{dia.capitalize()}*\n\n"
            "⏰ Escribe la hora (formato HH:MM):\n"
            "Ejemplo: 08:00, 14:30, 17:00",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="btn_calendario")]]),
        )

    elif query.data.startswith("caltipo_"):
        tipo = query.data.replace("caltipo_", "")
        dia = context.user_data.get("cal_dia", "")
        hora = context.user_data.get("cal_hora", "")
        context.user_data["cal_paso"] = None

        ok = agregar_turno(update.effective_user.id, dia, hora, tipo)
        if ok:
            emoji = "🟢" if tipo == "entrada" else "🔴"
            await query.edit_message_text(
                f"✅ Turno a\u00f1adido:\n\n"
                f"📆 D\u00eda: {dia.capitalize()}\n"
                f"⏰ Hora: {hora}\n"
                f"{emoji} Tipo: {tipo.capitalize()}\n\n"
                f"_Recibir\u00e1s notificaci\u00f3n a las {hora} (10 min antes)_",
                parse_mode="Markdown",
                reply_markup=get_calendario_keyboard(),
            )
        else:
            await query.edit_message_text(
                "⚠\ufe0f Ese turno ya existe en tu calendario.",
                reply_markup=get_calendario_keyboard(),
            )

    elif query.data == "cal_del":
        turnos = obtener_turnos_usuario(update.effective_user.id)
        if not turnos:
            await query.edit_message_text(
                "No tienes turnos para eliminar.",
                reply_markup=get_calendario_keyboard(),
            )
        else:
            btns = []
            for i, t in enumerate(turnos):
                emoji = "🟢" if t["tipo"] == "entrada" else "🔴"
                label = f"{emoji} {t['dia'].capitalize()} {t['hora']} - {t['tipo']}"
                btns.append([InlineKeyboardButton(label, callback_data=f"caldel_{i}")])
            btns.append([InlineKeyboardButton("◀\ufe0f Volver", callback_data="btn_calendario")])
            await query.edit_message_text(
                "❌ *Eliminar turno*\n\nSelecciona el turno a eliminar:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(btns),
            )

    elif query.data.startswith("caldel_"):
        idx = int(query.data.replace("caldel_", ""))
        turno = eliminar_turno(update.effective_user.id, idx)
        if turno:
            await query.edit_message_text(
                f"✅ Turno eliminado: {turno['dia'].capitalize()} {turno['hora']} ({turno['tipo']})",
                reply_markup=get_calendario_keyboard(),
            )
        else:
            await query.edit_message_text(
                "❌ No se pudo eliminar el turno.",
                reply_markup=get_calendario_keyboard(),
            )

    elif query.data == "cal_clear":
        context.user_data["cal_confirmar_borrado"] = True
        await query.edit_message_text(
            "⚠\ufe0f \u00bfEst\u00e1s seguro de que quieres borrar TODOS tus turnos?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ S\u00ed, borrar todo", callback_data="cal_clear_si"),
                    InlineKeyboardButton("❌ No", callback_data="btn_calendario"),
                ]
            ]),
        )

    elif query.data == "cal_clear_si":
        cantidad = eliminar_todos_turnos(update.effective_user.id)
        await query.edit_message_text(
            f"🗑 Se eliminaron {cantidad} turnos.",
            reply_markup=get_calendario_keyboard(),
        )

    elif query.data == "btn_cancelar":
        context.user_data["esperando_banda"] = False
        context.user_data["esperando_ciudad"] = False
        context.user_data["cal_paso"] = None
        await query.edit_message_text(
            "👌 Cancelado. Usa los botones o escribe un comando.",
            reply_markup=get_main_keyboard(),
        )


# --- Funcionalidad del calendario ---

async def horario_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                f"⏰ \u00a1Faltan 10 minutos! Prep\u00e1rate."
            )
        else:
            emoji = "🔴"
            msg = (
                f"🔔 *Recordatorio de SALIDA*\n\n"
                f"{emoji} Tu turno de *salida* es a las *{hora}*\n"
                f"📅 {dia}\n\n"
                f"⏰ \u00a1Faltan 10 minutos! Ve terminando."
            )

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=msg,
                parse_mode="Markdown",
            )
            STATS["notificaciones_enviadas"] += 1
        except Exception as e:
            print(f"⚠️ Error enviando notificación a {user_id}: {e}")


# --- Funcionalidad del tiempo ---

async def obtener_tiempo(lat: float, lon: float) -> dict | None:
    """Consulta Open-Meteo y devuelve tiempo actual + previsión horaria."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "hourly": "temperature_2m,weather_code,precipitation_probability",
                "forecast_hours": 12,
                "timezone": "auto",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def geocodificar(ciudad: str) -> tuple[float, float, str] | None:
    """Busca coordenadas de una ciudad. Devuelve (lat, lon, nombre_completo)."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            GEOCODING_URL,
            params={"name": ciudad, "count": 1, "language": "es"},
        )
        resp.raise_for_status()
        data = resp.json()
        resultados = data.get("results", [])
        if not resultados:
            return None
        r = resultados[0]
        nombre = r.get("name", ciudad)
        pais = r.get("country", "")
        admin = r.get("admin1", "")
        nombre_completo = f"{nombre}, {admin}, {pais}" if admin else f"{nombre}, {pais}"
        return r["latitude"], r["longitude"], nombre_completo


def formatear_tiempo(data: dict, ubicacion: str) -> str:
    """Formatea la respuesta del tiempo para Telegram."""
    current = data.get("current", {})
    hourly = data.get("hourly", {})

    temp = current.get("temperature_2m", "?")
    sensacion = current.get("apparent_temperature", "?")
    humedad = current.get("relative_humidity_2m", "?")
    viento = current.get("wind_speed_10m", "?")
    code = current.get("weather_code", 0)
    emoji, desc = WMO_CODES.get(code, ("❓", "Desconocido"))

    lineas = [
        f"📍 *{ubicacion}*",
        "",
        f"{emoji} *{desc}*",
        f"🌡 Temperatura: *{temp}°C*",
        f"🥵 Sensación térmica: {sensacion}°C",
        f"💧 Humedad: {humedad}%",
        f"💨 Viento: {viento} km/h",
        "",
        "🕒 *Previsión próximas horas:*",
    ]

    tiempos = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    codes = hourly.get("weather_code", [])
    precip = hourly.get("precipitation_probability", [])

    for i in range(min(12, len(tiempos))):
        hora = tiempos[i].split("T")[1] if "T" in tiempos[i] else tiempos[i]
        t = temps[i] if i < len(temps) else "?"
        c = codes[i] if i < len(codes) else 0
        p = precip[i] if i < len(precip) else 0
        e, _ = WMO_CODES.get(c, ("❓", ""))
        lineas.append(f"  {hora} — {e} {t}°C  🌧{p}%")

    return "\n".join(lineas)


async def enviar_tiempo(update_or_query, lat: float, lon: float, ubicacion: str, es_boton: bool = False):
    """Obtiene y envía el tiempo. Funciona tanto con mensajes como con botones."""
    try:
        data = await obtener_tiempo(lat, lon)
    except Exception as e:
        msg_err = f"❌ Error al obtener el tiempo: {e}"
        if es_boton:
            await update_or_query.message.reply_text(msg_err, reply_markup=get_main_keyboard())
        else:
            await update_or_query.reply_text(msg_err)
        return

    if not data:
        msg_err = "❌ No se pudo obtener información del tiempo."
        if es_boton:
            await update_or_query.message.reply_text(msg_err, reply_markup=get_main_keyboard())
        else:
            await update_or_query.reply_text(msg_err)
        return

    mensaje = formatear_tiempo(data, ubicacion)
    if es_boton:
        await update_or_query.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=get_main_keyboard())
    else:
        await update_or_query.reply_text(mensaje, parse_mode="Markdown")


async def tiempo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /tiempo <ciudad> — consulta el tiempo."""
    if not await control_acceso(update):
        return
    registrar("tiempo", update)

    if not context.args:
        await update.message.reply_text(
            "Uso: /tiempo <ciudad>\n"
            "Ejemplo: /tiempo Madrid\n\n"
            "También puedes enviar tu ubicación 📍 directamente."
        )
        return

    ciudad = " ".join(context.args)
    await update.message.reply_text(f"🔍 Buscando el tiempo en *{ciudad}*...", parse_mode="Markdown")

    geo = await geocodificar(ciudad)
    if not geo:
        await update.message.reply_text(f"❌ No encontré la ciudad \u00ab{ciudad}\u00bb.")
        return

    lat, lon, nombre = geo
    await enviar_tiempo(update.message, lat, lon, nombre)


async def ubicacion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja ubicaciones enviadas por el usuario."""
    if not await control_acceso(update):
        return
    registrar("tiempo", update)

    loc = update.message.location
    await update.message.reply_text("🔍 Consultando el tiempo en tu ubicación...")
    await enviar_tiempo(update.message, loc.latitude, loc.longitude, "Tu ubicación")


# --- Funcionalidad de música ---

async def buscar_banda_en_musicbrainz(nombre: str) -> dict | None:
    """Busca un artista en MusicBrainz y devuelve info + discografía."""
    async with httpx.AsyncClient(headers=HEADERS_MB, timeout=15) as client:
        # 1. Buscar el artista
        resp = await client.get(
            f"{MUSICBRAINZ_BASE}/artist/",
            params={"query": nombre, "limit": 1, "fmt": "json"},
        )
        resp.raise_for_status()
        data = resp.json()

        artistas = data.get("artists", [])
        if not artistas:
            return None

        artista = artistas[0]
        artist_id = artista["id"]
        nombre_oficial = artista.get("name", nombre)
        pais = artista.get("country", "Desconocido")
        tipo = artista.get("type", "")

        # Determinar si sigue activo
        life_span = artista.get("life-span", {})
        activo = not life_span.get("ended", False)
        inicio = life_span.get("begin", "?")
        fin = life_span.get("end", None)

        # 2. Obtener discografía (release-groups = álbumes)
        resp2 = await client.get(
            f"{MUSICBRAINZ_BASE}/release-group/",
            params={
                "artist": artist_id,
                "type": "album",
                "limit": 50,
                "fmt": "json",
            },
        )
        resp2.raise_for_status()
        rg_data = resp2.json()

        albumes = []
        for rg in rg_data.get("release-groups", []):
            titulo = rg.get("title", "Sin título")
            fecha = rg.get("first-release-date", "?")
            albumes.append((fecha, titulo))

        # Ordenar por fecha
        albumes.sort(key=lambda x: x[0] if x[0] != "?" else "9999")

        return {
            "nombre": nombre_oficial,
            "pais": pais,
            "tipo": tipo,
            "activo": activo,
            "inicio": inicio,
            "fin": fin,
            "albumes": albumes,
        }


async def banda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /banda <nombre> — busca discografía y estado."""
    if not await control_acceso(update):
        return
    registrar("bandas", update)
    if not context.args:
        await update.message.reply_text("Uso: /banda <nombre del grupo>\nEjemplo: /banda Metallica")
        return

    nombre = " ".join(context.args)
    await update.message.reply_text(f"🔍 Buscando información sobre *{nombre}*...", parse_mode="Markdown")

    try:
        info = await buscar_banda_en_musicbrainz(nombre)
    except Exception as e:
        await update.message.reply_text(f"❌ Error al consultar MusicBrainz: {e}")
        return

    if not info:
        await update.message.reply_text(f"No encontré ningún artista con el nombre «{nombre}».")
        return

    # Construir respuesta
    estado = "✅ Activo" if info["activo"] else f"❌ Inactivo (disuelto en {info['fin'] or '?'})"
    lineas = [
        f"🎸 *{info['nombre']}*",
        f"🌍 País: {info['pais']}",
        f"📅 Inicio: {info['inicio']}",
        f"📌 Estado: {estado}",
        "",
        f"💿 *Discografía ({len(info['albumes'])} álbumes):*",
    ]

    if info["albumes"]:
        for fecha, titulo in info["albumes"]:
            year = fecha[:4] if fecha and fecha != "?" else "?"
            lineas.append(f"  • {year} — {titulo}")
    else:
        lineas.append("  No se encontraron álbumes.")

    mensaje = "\n".join(lineas)

    # Telegram limita a 4096 caracteres
    if len(mensaje) > 4096:
        mensaje = mensaje[:4090] + "\n..."

    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def responder_saludo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detecta saludos en el mensaje y responde."""
    if not await control_acceso(update):
        return
    # Si estamos esperando hora para el calendario
    if context.user_data.get("cal_paso") == "hora":
        hora = validar_hora(update.message.text.strip())
        if not hora:
            await update.message.reply_text(
                "❌ Formato inválido. Escribe la hora como HH:MM (ej: 08:00, 14:30)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="btn_calendario")]]),
            )
            return

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
        return

    # Si estamos esperando un día escrito (fecha específica)
    if context.user_data.get("cal_paso") == "dia":
        dia = validar_dia(update.message.text.strip())
        if not dia:
            await update.message.reply_text(
                "❌ Día no válido. Usa un día de la semana o una fecha (DD/MM/YYYY)",
            )
            return

        context.user_data["cal_dia"] = dia
        context.user_data["cal_paso"] = "hora"
        await update.message.reply_text(
            f"➕ Día: *{dia.capitalize()}*\n\n"
            "⏰ Escribe la hora (formato HH:MM):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="btn_calendario")]]),
        )
        return

    # Si estamos esperando una ciudad desde el botón de tiempo
    if context.user_data.get("esperando_ciudad"):
        context.user_data["esperando_ciudad"] = False
        registrar("tiempo", update)
        ciudad = update.message.text.strip()
        await update.message.reply_text(f"🔍 Buscando el tiempo en *{ciudad}*...", parse_mode="Markdown")

        geo = await geocodificar(ciudad)
        if not geo:
            await update.message.reply_text(f"❌ No encontré la ciudad \u00ab{ciudad}\u00bb.", reply_markup=get_main_keyboard())
            return

        lat, lon, nombre = geo
        await enviar_tiempo(update, lat, lon, nombre, es_boton=True)
        return

    # Si estamos esperando un nombre de banda desde el botón
    if context.user_data.get("esperando_banda"):
        context.user_data["esperando_banda"] = False
        registrar("bandas", update)
        nombre = update.message.text.strip()
        await update.message.reply_text(f"🔍 Buscando información sobre *{nombre}*...", parse_mode="Markdown")

        try:
            info = await buscar_banda_en_musicbrainz(nombre)
        except Exception as e:
            await update.message.reply_text(f"❌ Error al consultar MusicBrainz: {e}", reply_markup=get_main_keyboard())
            return

        if not info:
            await update.message.reply_text(f"No encontré ningún artista con el nombre «{nombre}».", reply_markup=get_main_keyboard())
            return

        estado = "✅ Activo" if info["activo"] else f"❌ Inactivo (disuelto en {info['fin'] or '?'})"
        lineas = [
            f"🎸 *{info['nombre']}*",
            f"🌍 País: {info['pais']}",
            f"📅 Inicio: {info['inicio']}",
            f"📌 Estado: {estado}",
            "",
            f"💿 *Discografía ({len(info['albumes'])} álbumes):*",
        ]
        if info["albumes"]:
            for fecha, titulo in info["albumes"]:
                year = fecha[:4] if fecha and fecha != "?" else "?"
                lineas.append(f"  • {year} — {titulo}")
        else:
            lineas.append("  No se encontraron álbumes.")

        mensaje = "\n".join(lineas)
        if len(mensaje) > 4096:
            mensaje = mensaje[:4090] + "\n..."

        await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=get_main_keyboard())
        return

    registrar("saludos", update)
    texto = update.message.text.lower().strip()

    for saludo, respuesta in SALUDOS.items():
        if saludo in texto:
            await update.message.reply_text(respuesta)
            return

    # Si no reconoce un saludo, da una respuesta genérica
    await update.message.reply_text("No entendí tu saludo, pero ¡hola de todos modos! 😊")


def main():
    if not TOKEN:
        print("❌ Error: Define la variable de entorno TELEGRAM_BOT_TOKEN con el token de tu bot.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("banda", banda))
    app.add_handler(CommandHandler("tiempo", tiempo_cmd))
    app.add_handler(CommandHandler("horario", horario_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("miid", miid))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, ubicacion_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_saludo))

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
