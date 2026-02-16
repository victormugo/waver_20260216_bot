# 🤖 Bot de Telegram - Arquitectura Modular

Bot multifuncional de Telegram completamente refactorizado con arquitectura modular para facilitar el mantenimiento y escalabilidad.

## ✨ Nueva Arquitectura

El proyecto ahora está organizado en **módulos independientes**, cada uno con una responsabilidad específica:

### 📦 Módulos del Sistema

| Módulo | Descripción |
|--------|-------------|
| **`bot.py`** | Archivo principal que orquesta todos los módulos |
| **`acceso.py`** | Control de acceso, rate limiting y permisos |
| **`estadisticas.py`** | Sistema de registro y estadísticas |
| **`bandas.py`** | Búsqueda de bandas musicales (MusicBrainz) |
| **`tiempo.py`** | Consulta del tiempo (Open-Meteo) |
| **`saludos.py`** | Procesamiento de saludos y mensajes |
| **`admin.py`** | Comandos administrativos |
| **`comandos.py`** | Comandos principales del bot |
| **`calendario_cmd.py`** | Interacción del calendario laboral |
| **`calendario.py`** | Lógica del calendario |
| **`notificaciones.py`** | Sistema de notificaciones por email |

## 🎯 Ventajas de la Nueva Arquitectura

- ✅ **Mantenimiento simplificado** - Cada funcionalidad en su propio archivo
- ✅ **Código organizado** - Separación clara de responsabilidades
- ✅ **Fácil de extender** - Agregar nuevas funcionalidades sin afectar el resto
- ✅ **Testing individual** - Cada módulo se puede probar por separado
- ✅ **Mejor legibilidad** - Archivos más pequeños y enfocados
- ✅ **Reutilización** - Módulos pueden ser importados donde se necesiten

## 🚀 Inicio Rápido

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar .env con tu token
# TELEGRAM_BOT_TOKEN=tu_token_aqui

# 3. Ejecutar el bot
python bot.py
```

## 📋 Flujo de Datos

```
Usuario → Telegram API → bot.py (orquestador)
                            ↓
            ┌───────────────┼───────────────┐
            ↓               ↓               ↓
      acceso.py      estadisticas.py   comandos.py
            ↓               ↓               ↓
      Validación      Registro        Procesamiento
            ↓               ↓               ↓
      ┌─────┴─────┬────────┴────────┬──────┴─────┐
      ↓           ↓                 ↓            ↓
  bandas.py   tiempo.py        saludos.py   admin.py
      ↓           ↓                 ↓            ↓
  MusicBrainz  Open-Meteo      Respuesta   Gestión
```

## 🛠️ Agregar Nueva Funcionalidad

Para agregar una nueva funcionalidad (ejemplo: traductor):

1. **Crear módulo** `traductor.py`:
```python
async def traducir_handler(update, context):
    """Comando /traducir"""
    # Tu lógica aquí
    pass
```

2. **Importar en** `bot.py`:
```python
from traductor import traducir_handler
```

3. **Registrar handler en** `bot.py` (función `main`):
```python
app.add_handler(CommandHandler("traducir", traducir_handler))
```

¡Listo! Sin modificar código existente.

## 📝 Ejemplos de Uso

### Búsqueda de Bandas
```
/banda Metallica
```
Usa el módulo `bandas.py` → API de MusicBrainz

### Consulta del Tiempo
```
/tiempo Madrid
```
Usa el módulo `tiempo.py` → API de Open-Meteo

### Calendario Laboral
```
/horario
```
Usa `calendario_cmd.py` + `calendario.py`

### Administración
```
/admin ban 123456789
```
Usa el módulo `admin.py` + `acceso.py`

## 📁 Estructura Completa

```
bot_telegram/
├── 🎯 ARCHIVOS PRINCIPALES
│   ├── bot.py                    # Orquestador principal
│   ├── .env                      # Configuración
│   ├── requirements.txt          # Dependencias
│   └── calendario.json           # Datos persistentes
│
├── 🔒 SEGURIDAD Y CONTROL
│   ├── acceso.py                 # Rate limiting, permisos
│   └── admin.py                  # Comandos administrativos
│
├── 📊 ESTADÍSTICAS
│   ├── estadisticas.py           # Registro de actividad
│   └── notificaciones.py         # Emails de notificación
│
├── 🎵 FUNCIONALIDADES
│   ├── bandas.py                 # MusicBrainz API
│   ├── tiempo.py                 # Open-Meteo API
│   ├── saludos.py                # Procesamiento de texto
│   ├── calendario.py             # Lógica del calendario
│   └── calendario_cmd.py         # UI del calendario
│
├── 💬 INTERFAZ
│   └── comandos.py               # Comandos principales
│
└── 📚 DOCUMENTACIÓN
    ├── INSTRUCTIONS.md           # Guía completa
    ├── README.md                 # Este archivo
    └── bot_original.py           # Backup código original
```

## 🔍 Detalles de los Módulos

### `acceso.py` - Control de Acceso
- Verificación de permisos
- Rate limiting (límite de peticiones)
- Sistema de baneos automáticos
- Whitelist de usuarios

### `estadisticas.py` - Estadísticas
- Contador de peticiones globales
- Registro por tipo de acción
- Usuarios únicos
- Notificaciones enviadas

### `bandas.py` - Búsqueda Musical
- Integración con MusicBrainz
- Búsqueda de artistas
- Discografía completa
- Estado (activo/inactivo)

### `tiempo.py` - Pronóstico del Tiempo
- Integración con Open-Meteo
- Geocodificación de ciudades
- Temperatura, humedad, viento
- Previsión horaria

### `calendario_cmd.py` - Calendario Laboral
- Gestión de turnos
- Recordatorios automáticos
- Interfaz conversacional
- Callbacks de botones

## 🧪 Testing

Cada módulo puede probarse de forma independiente:

```python
# test_bandas.py
from bandas import buscar_banda_en_musicbrainz

async def test():
    resultado = await buscar_banda_en_musicbrainz("Metallica")
    assert resultado is not None
```

## 📈 Escalabilidad

La arquitectura modular permite:

1. **Añadir nuevas APIs** sin modificar código existente
2. **Distribuir módulos** en diferentes servicios
3. **Cachear respuestas** a nivel de módulo
4. **Logs específicos** por funcionalidad
5. **Límites independientes** por servicio

## 🤝 Contribuir

Para contribuir una nueva funcionalidad:

1. Crea un nuevo módulo en su propio archivo
2. Implementa los handlers necesarios
3. Importa y registra en `bot.py`
4. Documenta en README.md

## 📞 Soporte

Consulta [INSTRUCTIONS.md](INSTRUCTIONS.md) para:
- Instalación detallada
- Configuración de .env
- Comandos disponibles
- Resolución de problemas

---

**Versión Modular** - Febrero 2026
