import os
import asyncio
import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

# --- Configuración ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

MUSICBRAINZ_BASE = "https://musicbrainz.org/ws/2"
HEADERS_MB = {"User-Agent": "TelegramMusicBot/1.0 (bot_telegram)", "Accept": "application/json"}

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde al comando /start."""
    await update.message.reply_text(
        "¡Hola! 👋 Soy un bot multifunción.\n\n"
        "🎵 Escribe /banda <nombre> para consultar la discografía de un grupo.\n"
        "👋 O escríbeme un saludo como «hola», «buenos días» o «hey»."
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_saludo))

    print("🤖 Bot iniciado. Esperando mensajes...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app.run_polling()


if __name__ == "__main__":
    main()
