import os
import asyncio
import httpx
import json
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, ContextTypes, filters

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

# --- Estadísticas ---
STATS = {
    "inicio": datetime.now(),
    "total": 0,
    "saludos": 0,
    "bandas": 0,
    "comandos_start": 0,
    "comandos_stats": 0,
    "usuarios": set(),
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


def registrar(tipo: str, update: Update):
    """Registra una petición en las estadísticas."""
    STATS["total"] += 1
    STATS[tipo] += 1
    if update.effective_user:
        STATS["usuarios"].add(update.effective_user.id)


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
        f"▶️ Comandos /start: {STATS['comandos_start']}\n"
        f"📊 Comandos /stats: {STATS['comandos_stats']}\n\n"
        f"👥 Usuarios únicos: {len(STATS['usuarios'])}\n"
        f"🚫 Usuarios baneados: {len(usuarios_baneados)}\n"
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
            InlineKeyboardButton("📊 Estadísticas", callback_data="btn_stats"),
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
        "🎵 Escribe /banda <nombre> para consultar la discografía de un grupo.\n"
        "📊 Escribe /stats para ver las estadísticas del bot.\n"
        "👋 O escríbeme un saludo como «hola», «buenos días» o «hey».\n\n"
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
            f"🎸 Búsquedas de bandas: {STATS['bandas']}\n"
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

    elif query.data == "btn_cancelar":
        context.user_data["esperando_banda"] = False
        await query.edit_message_text(
            "👌 Cancelado. Usa los botones o escribe un comando.",
            reply_markup=get_main_keyboard(),
        )


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
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("miid", miid))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_saludo))

    print("🤖 Bot iniciado. Esperando mensajes...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app.run_polling()


if __name__ == "__main__":
    main()
