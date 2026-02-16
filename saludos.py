"""
Módulo de respuestas a saludos y mensajes de texto general.
"""
from telegram import Update
from telegram.ext import ContextTypes

from acceso import control_acceso
from estadisticas import registrar

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


async def procesar_saludo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detecta y responde a saludos en mensajes de texto."""
    if not await control_acceso(update):
        return
    
    registrar("saludos", update)
    texto = update.message.text.lower().strip()

    for saludo, respuesta in SALUDOS.items():
        if saludo in texto:
            await update.message.reply_text(respuesta)
            return

    # Si no reconoce un saludo, da una respuesta genérica
    await update.message.reply_text("No entendí tu saludo, pero ¡hola de todos modos! 😊")
