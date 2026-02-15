"""
Módulo de calendario laboral con notificaciones.
Almacena horarios de entrada/salida y notifica 10 minutos antes.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

CALENDARIO_FILE = Path(__file__).parent / "calendario.json"

# Días de la semana en español
DIAS_SEMANA = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}

DIAS_SEMANA_NOMBRE = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


def cargar_calendario() -> dict:
    """Carga el calendario desde el archivo JSON."""
    if CALENDARIO_FILE.exists():
        try:
            with open(CALENDARIO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def guardar_calendario(data: dict):
    """Guarda el calendario en el archivo JSON."""
    with open(CALENDARIO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def obtener_turnos_usuario(user_id: int) -> list[dict]:
    """Obtiene los turnos de un usuario."""
    cal = cargar_calendario()
    return cal.get(str(user_id), [])


def agregar_turno(user_id: int, dia: str, hora: str, tipo: str) -> bool:
    """Agrega un turno al calendario del usuario.
    dia: nombre del día (lunes-domingo) o fecha (YYYY-MM-DD)
    hora: HH:MM
    tipo: 'entrada' o 'salida'
    """
    cal = cargar_calendario()
    uid = str(user_id)

    if uid not in cal:
        cal[uid] = []

    # Verificar que no existe ya un turno idéntico
    for turno in cal[uid]:
        if turno["dia"] == dia and turno["hora"] == hora and turno["tipo"] == tipo:
            return False  # Ya existe

    cal[uid].append({
        "dia": dia,
        "hora": hora,
        "tipo": tipo,
    })

    # Ordenar por día y hora
    orden_dias = {v: k for k, v in DIAS_SEMANA_NOMBRE.items()}
    cal[uid].sort(key=lambda t: (
        _orden_dia(t["dia"]),
        t["hora"],
    ))

    guardar_calendario(cal)
    return True


def eliminar_turno(user_id: int, indice: int) -> dict | None:
    """Elimina un turno por índice (0-based). Devuelve el turno eliminado."""
    cal = cargar_calendario()
    uid = str(user_id)

    if uid not in cal or indice < 0 or indice >= len(cal[uid]):
        return None

    turno = cal[uid].pop(indice)

    if not cal[uid]:
        del cal[uid]

    guardar_calendario(cal)
    return turno


def eliminar_todos_turnos(user_id: int) -> int:
    """Elimina todos los turnos de un usuario. Devuelve cantidad eliminada."""
    cal = cargar_calendario()
    uid = str(user_id)

    if uid not in cal:
        return 0

    cantidad = len(cal[uid])
    del cal[uid]
    guardar_calendario(cal)
    return cantidad


def obtener_turnos_proximos(minutos_antes: int = 10) -> list[dict]:
    """Devuelve turnos que ocurren exactamente en `minutos_antes` minutos.
    Cada resultado incluye: user_id, dia, hora, tipo.
    """
    ahora = datetime.now()
    objetivo = ahora + timedelta(minutes=minutos_antes)

    dia_semana_actual = ahora.weekday()
    hora_objetivo = objetivo.strftime("%H:%M")
    fecha_hoy = ahora.strftime("%Y-%m-%d")

    cal = cargar_calendario()
    resultado = []

    for uid, turnos in cal.items():
        for turno in turnos:
            dia = turno["dia"]
            hora = turno["hora"]

            # Comprobar si el turno coincide
            coincide = False

            # ¿Es un día de la semana recurrente?
            dia_lower = dia.lower()
            if dia_lower in DIAS_SEMANA:
                if DIAS_SEMANA[dia_lower] == dia_semana_actual and hora == hora_objetivo:
                    coincide = True
            # ¿Es una fecha específica?
            elif dia == fecha_hoy and hora == hora_objetivo:
                coincide = True

            if coincide:
                resultado.append({
                    "user_id": int(uid),
                    "dia": dia,
                    "hora": hora,
                    "tipo": turno["tipo"],
                })

    return resultado


def formatear_calendario(user_id: int) -> str:
    """Formatea el calendario de un usuario para mostrar en Telegram."""
    turnos = obtener_turnos_usuario(user_id)

    if not turnos:
        return "📅 No tienes turnos configurados.\n\nUsa /horario para añadir uno."

    lineas = ["📅 *Tu calendario laboral:*\n"]

    dia_actual = None
    for i, turno in enumerate(turnos):
        dia = turno["dia"]
        hora = turno["hora"]
        tipo = turno["tipo"]
        emoji = "🟢" if tipo == "entrada" else "🔴"

        # Nombre bonito del día
        dia_nombre = _nombre_dia(dia)

        if dia_nombre != dia_actual:
            dia_actual = dia_nombre
            lineas.append(f"\n📆 *{dia_nombre}*")

        lineas.append(f"  {emoji} {hora} — {tipo.capitalize()}  (#{i + 1})")

    lineas.append(f"\n_Total: {len(turnos)} turnos configurados_")
    lineas.append("_Recibirás notificación 10 min antes de cada turno_")

    return "\n".join(lineas)


def _orden_dia(dia: str) -> int:
    """Devuelve un número para ordenar días."""
    dia_lower = dia.lower()
    if dia_lower in DIAS_SEMANA:
        return DIAS_SEMANA[dia_lower]
    # Fechas específicas van al final, ordenadas
    try:
        return 100 + int(dia.replace("-", ""))
    except ValueError:
        return 999


def _nombre_dia(dia: str) -> str:
    """Convierte un día a nombre bonito."""
    dia_lower = dia.lower()
    if dia_lower in DIAS_SEMANA:
        return DIAS_SEMANA_NOMBRE[DIAS_SEMANA[dia_lower]]
    # Es una fecha
    try:
        fecha = datetime.strptime(dia, "%Y-%m-%d")
        nombre = DIAS_SEMANA_NOMBRE[fecha.weekday()]
        return f"{nombre} {fecha.strftime('%d/%m/%Y')}"
    except ValueError:
        return dia


def validar_hora(hora_str: str) -> str | None:
    """Valida formato HH:MM. Devuelve la hora normalizada o None."""
    try:
        partes = hora_str.strip().split(":")
        if len(partes) != 2:
            return None
        h, m = int(partes[0]), int(partes[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    except ValueError:
        pass
    return None


def validar_dia(dia_str: str) -> str | None:
    """Valida un día (nombre o fecha YYYY-MM-DD). Devuelve normalizado o None."""
    dia = dia_str.strip().lower()

    # Día de la semana
    if dia in DIAS_SEMANA:
        return dia

    # Fecha específica
    try:
        datetime.strptime(dia, "%Y-%m-%d")
        return dia
    except ValueError:
        pass

    # Intentar DD/MM/YYYY
    try:
        fecha = datetime.strptime(dia, "%d/%m/%Y")
        return fecha.strftime("%Y-%m-%d")
    except ValueError:
        pass

    return None
