"""
Módulo de notificaciones por email.
Envía un email al administrador cada vez que un usuario realiza una acción.
"""

import os
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def _get_email_config():
    """Lee la configuración SMTP en el momento de usarla (tras load_dotenv)."""
    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASS", ""),
        "destino": os.getenv("EMAIL_DESTINO", ""),
        "activo": os.getenv("EMAIL_ACTIVO", "false").lower() == "true",
    }


def _enviar_email_sync(asunto: str, cuerpo: str):
    """Envía un email de forma síncrona (se ejecuta en un thread)."""
    cfg = _get_email_config()
    if not cfg["activo"] or not cfg["user"] or not cfg["password"] or not cfg["destino"]:
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = cfg["user"]
        msg["To"] = cfg["destino"]
        msg["Subject"] = asunto

        msg.attach(MIMEText(cuerpo, "html"))

        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)

    except Exception as e:
        print(f"⚠️ Error enviando email: {e}")


async def notificar_accion(nombre_usuario: str, user_id: int, accion: str):
    """Envía un email notificando una acción de usuario (en background)."""
    cfg = _get_email_config()
    if not cfg["activo"]:
        return

    ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    asunto = f"🤖 Bot Telegram — {accion}"

    cuerpo = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #2196F3;">🤖 Notificación del Bot</h2>
        <table style="border-collapse: collapse; width: 100%; max-width: 500px;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">👤 Usuario</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{nombre_usuario}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">🆔 ID</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{user_id}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">⚡ Acción</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{accion}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">🕐 Fecha/Hora</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{ahora}</td>
            </tr>
        </table>
    </body>
    </html>
    """

    # Ejecutar en thread aparte para no bloquear el bot
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _enviar_email_sync, asunto, cuerpo)
