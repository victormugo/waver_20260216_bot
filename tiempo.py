"""
Módulo de consulta del tiempo usando Open-Meteo.
"""
import httpx
from telegram import Update
from telegram.ext import ContextTypes

from acceso import control_acceso
from estadisticas import registrar

# API del tiempo (Open-Meteo, gratuita, sin API key)
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

# Mapeo de códigos WMO a emojis/descripciones
WMO_CODES = {
    0: ("☀️", "Despejado"),
    1: ("🌤", "Principalmente despejado"),
    2: ("⛅", "Parcialmente nublado"),
    3: ("☁️", "Nublado"),
    45: ("🌫", "Niebla"),
    48: ("🌫", "Niebla con escarcha"),
    51: ("🌦", "Llovizna ligera"),
    53: ("🌦", "Llovizna moderada"),
    55: ("🌦", "Llovizna densa"),
    61: ("🌧", "Lluvia ligera"),
    63: ("🌧", "Lluvia moderada"),
    65: ("🌧", "Lluvia fuerte"),
    71: ("🌨", "Nevada ligera"),
    73: ("🌨", "Nevada moderada"),
    75: ("🌨", "Nevada fuerte"),
    77: ("❄️", "Granizo"),
    80: ("🌦", "Chubascos ligeros"),
    81: ("🌧", "Chubascos moderados"),
    82: ("🌧", "Chubascos fuertes"),
    85: ("🌨", "Chubascos de nieve ligeros"),
    86: ("🌨", "Chubascos de nieve fuertes"),
    95: ("⛈", "Tormenta"),
    96: ("⛈", "Tormenta con granizo ligero"),
    99: ("⛈", "Tormenta con granizo"),
}


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


async def enviar_tiempo(update_or_query, lat: float, lon: float, ubicacion: str, es_boton: bool = False, get_main_keyboard_func=None):
    """Obtiene y envía el tiempo. Funciona tanto con mensajes como con botones."""
    try:
        data = await obtener_tiempo(lat, lon)
    except Exception as e:
        msg_err = f"❌ Error al obtener el tiempo: {e}"
        if es_boton and get_main_keyboard_func:
            await update_or_query.message.reply_text(msg_err, reply_markup=get_main_keyboard_func())
        else:
            await update_or_query.reply_text(msg_err)
        return

    if not data:
        msg_err = "❌ No se pudo obtener información del tiempo."
        if es_boton and get_main_keyboard_func:
            await update_or_query.message.reply_text(msg_err, reply_markup=get_main_keyboard_func())
        else:
            await update_or_query.reply_text(msg_err)
        return

    mensaje = formatear_tiempo(data, ubicacion)
    if es_boton and get_main_keyboard_func:
        await update_or_query.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=get_main_keyboard_func())
    else:
        await update_or_query.reply_text(mensaje, parse_mode="Markdown")


async def tiempo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text(f"❌ No encontré la ciudad «{ciudad}».")
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
