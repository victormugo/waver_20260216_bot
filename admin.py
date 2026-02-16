"""
Módulo de comandos administrativos.
"""
from telegram import Update
from telegram.ext import ContextTypes

from acceso import (
    es_admin, 
    banear_usuario, 
    desbanear_usuario,
    permitir_usuario,
    denegar_usuario,
    obtener_usuarios_baneados,
    obtener_modo_acceso,
    establecer_modo_acceso,
    obtener_max_peticiones,
    establecer_max_peticiones,
)


async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            banear_usuario(uid)
            await update.message.reply_text(f"🚫 Usuario {uid} bloqueado.")
        except ValueError:
            await update.message.reply_text("❌ ID inválido.")

    elif accion == "unban" and len(context.args) >= 2:
        try:
            uid = int(context.args[1])
            desbanear_usuario(uid)
            await update.message.reply_text(f"✅ Usuario {uid} desbloqueado.")
        except ValueError:
            await update.message.reply_text("❌ ID inválido.")

    elif accion == "allow" and len(context.args) >= 2:
        try:
            uid = int(context.args[1])
            permitir_usuario(uid)
            await update.message.reply_text(f"✅ Usuario {uid} añadido a la lista blanca.")
        except ValueError:
            await update.message.reply_text("❌ ID inválido.")

    elif accion == "deny" and len(context.args) >= 2:
        try:
            uid = int(context.args[1])
            denegar_usuario(uid)
            await update.message.reply_text(f"❌ Usuario {uid} eliminado de la lista blanca.")
        except ValueError:
            await update.message.reply_text("❌ ID inválido.")

    elif accion == "modo" and len(context.args) >= 2:
        nuevo_modo = context.args[1].lower()
        if nuevo_modo in ("abierto", "restringido"):
            establecer_modo_acceso(nuevo_modo)
            emoji = "🔓" if nuevo_modo == "abierto" else "🔒"
            await update.message.reply_text(f"{emoji} Modo cambiado a: *{nuevo_modo}*", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Modos válidos: abierto, restringido")

    elif accion == "baneados":
        usuarios_baneados = obtener_usuarios_baneados()
        if usuarios_baneados:
            lista = "\n".join(f"  • {uid}" for uid in usuarios_baneados)
            await update.message.reply_text(f"🚫 *Usuarios bloqueados:*\n{lista}", parse_mode="Markdown")
        else:
            await update.message.reply_text("✅ No hay usuarios bloqueados.")

    elif accion == "ratelimit" and len(context.args) >= 2:
        try:
            nuevo = int(context.args[1])
            if nuevo < 1:
                raise ValueError
            establecer_max_peticiones(nuevo)
            await update.message.reply_text(f"✅ Límite cambiado a {nuevo} peticiones/minuto.")
        except ValueError:
            await update.message.reply_text("❌ Número inválido. Usa un entero positivo.")

    else:
        await update.message.reply_text("❌ Comando no reconocido. Escribe /admin para ver la ayuda.")
