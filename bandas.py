"""
Módulo de búsqueda de bandas musicales usando MusicBrainz.
"""
import httpx
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from acceso import control_acceso
from estadisticas import registrar

# Configuración de MusicBrainz
MUSICBRAINZ_BASE = "https://musicbrainz.org/ws/2"
HEADERS_MB = {"User-Agent": "TelegramMusicBot/1.0 (bot_telegram)", "Accept": "application/json"}


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


def generar_enlace_youtube(nombre_banda: str) -> str:
    """Genera un enlace de búsqueda de YouTube para la banda."""
    query = urllib.parse.quote(f"{nombre_banda} official")
    return f"https://www.youtube.com/results?search_query={query}"


def crear_teclado_banda(nombre_banda: str) -> InlineKeyboardMarkup:
    """Crea teclado inline con enlaces a YouTube y más info."""
    youtube_url = generar_enlace_youtube(nombre_banda)
    keyboard = [
        [
            InlineKeyboardButton("▶️ Ver en YouTube", url=youtube_url),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def formatear_info_banda(info: dict, incluir_enlace_youtube: bool = True) -> str:
    """Formatea la información de la banda para Telegram."""
    estado = "✅ Activo" if info["activo"] else f"❌ Inactivo (disuelto en {info['fin'] or '?'})"
    lineas = [
        f"🎸 *{info['nombre']}*",
        f"🌍 País: {info['pais']}",
        f"📅 Inicio: {info['inicio']}",
        f"📌 Estado: {estado}",
    ]
    
    # Añadir enlace a YouTube si se solicita
    if incluir_enlace_youtube:
        youtube_url = generar_enlace_youtube(info['nombre'])
        lineas.append(f"▶️ [Buscar en YouTube]({youtube_url})")
    
    lineas.extend([
        "",
        f"💿 *Discografía ({len(info['albumes'])} álbumes):*",
    ])

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

    return mensaje


async def banda_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    mensaje = formatear_info_banda(info)
    teclado = crear_teclado_banda(info['nombre'])
    await update.message.reply_text(
        mensaje, 
        parse_mode="Markdown",
        reply_markup=teclado,
        disable_web_page_preview=True
    )


async def procesar_busqueda_banda_boton(update: Update, context: ContextTypes.DEFAULT_TYPE, nombre: str, get_main_keyboard_func):
    """Procesa la búsqueda de banda desde el botón inline."""
    registrar("bandas", update)
    await update.message.reply_text(f"🔍 Buscando información sobre *{nombre}*...", parse_mode="Markdown")

    try:
        info = await buscar_banda_en_musicbrainz(nombre)
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error al consultar MusicBrainz: {e}", 
            reply_markup=get_main_keyboard_func()
        )
        return

    if not info:
        await update.message.reply_text(
            f"No encontré ningún artista con el nombre «{nombre}».", 
            reply_markup=get_main_keyboard_func()
        )
        return

    mensaje = formatear_info_banda(info)
    teclado = crear_teclado_banda(info['nombre'])
    await update.message.reply_text(
        mensaje, 
        parse_mode="Markdown",
        reply_markup=teclado,
        disable_web_page_preview=True
    )
    # Mostrar el teclado principal después
    await update.message.reply_text(
        "¿Qué más quieres hacer?",
        reply_markup=get_main_keyboard_func()
    )
