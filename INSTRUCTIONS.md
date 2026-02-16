# 🤖 Bot de Telegram - Instrucciones

Bot multifuncional de Telegram con calendario laboral, búsqueda de bandas musicales, consulta del tiempo y más.

## 📋 Requisitos

- Python 3.9 o superior
- pip (gestor de paquetes de Python)
- Una cuenta de Telegram y un bot token (obtenido de [@BotFather](https://t.me/botfather))

## 🚀 Instalación

### 1. Clonar o descargar el proyecto

```bash
cd bot_telegram
```

### 2. Instalar dependencias

```powershell
pip install -r requirements.txt
```

Las dependencias incluyen:
- `python-telegram-bot[job-queue]` - Framework para bots de Telegram
- `python-dotenv` - Manejo de variables de entorno

### 3. Configurar variables de entorno

Edita el archivo `.env` con tus credenciales:

```env
# Token del bot (obtenerlo de @BotFather en Telegram)
TELEGRAM_BOT_TOKEN=tu_token_aqui

# IDs de administradores (usar /miid en el bot para obtener tu ID)
ADMIN_IDS=[123456789]

# Modo de acceso: "abierto" o "restringido"
MODO_ACCESO=abierto

# IDs permitidos en modo restringido
USUARIOS_PERMITIDOS=[]

# Límite de peticiones por usuario por minuto
MAX_PETICIONES_POR_MINUTO=10

# Notificaciones por email
EMAIL_ACTIVO=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASS=tu_contraseña_de_aplicacion
```

### 4. Ejecutar el bot

```powershell
python bot.py
```

Verás estos mensajes cuando el bot esté listo:
```
📅 Notificaciones de calendario activadas (cada 60s)
🤖 Bot iniciado. Esperando mensajes...
```

## 📱 Comandos Disponibles

### Comandos Generales

- **`/start`** - Mensaje de bienvenida con opciones principales
- **`/miid`** - Muestra tu ID de usuario de Telegram
- **`/stats`** - Estadísticas de uso del bot (solo admins)
- **`/admin`** - Panel de administración (solo admins)

### Búsqueda de Bandas

- **`/banda [nombre]`** - Busca información de una banda musical en MusicBrainz
  
  Ejemplo: `/banda Radiohead`

### Consulta del Tiempo

- **`/tiempo [ciudad]`** - Muestra el pronóstico del tiempo para una ciudad
  
  Ejemplos:
  - `/tiempo Madrid`
  - `/tiempo Buenos Aires`
  - `/tiempo New York`
  
- **Enviar ubicación** - Comparte tu ubicación en el chat y el bot te mostrará el tiempo actual

### Calendario Laboral

- **`/horario`** - Gestiona tu calendario de trabajo

#### Opciones del calendario:
- **Ver calendario** - Muestra todos tus turnos guardados
- **Agregar turno** - Añade un nuevo turno
  - Selecciona el día de la semana
  - Introduce la hora (formato: `HH:MM` o `HH:MM-HH:MM`)
  - Ejemplo: `09:00-17:00` o `14:30`
- **Eliminar turno** - Borra un turno específico
- **Borrar todo** - Elimina todos los turnos
- **Próximos turnos** - Muestra los próximos 7 días de trabajo

#### Sistema de notificaciones
El bot envía recordatorios automáticos:
- **15 minutos antes** de tu turno
- Las notificaciones se comprueban cada 60 segundos

## 🛡️ Características de Seguridad

### Control de Acceso

1. **Modo Abierto** - Todos pueden usar el bot
2. **Modo Restringido** - Solo usuarios en la lista blanca

### Rate Limiting

- Límite de peticiones por minuto configurable (default: 10)
- Sistema de avisos progresivos
- Bloqueo automático tras 3 avisos por abuso
- Los administradores están exentos de límites

### Notificaciones por Email

El bot puede enviar notificaciones por email cuando los usuarios realizan acciones:
- Búsquedas de bandas
- Consultas del tiempo
- Uso del calendario
- Comandos ejecutados

## 📊 Sistema de Estadísticas

El comando `/stats` (solo admins) muestra:
- Tiempo de actividad del bot
- Total de peticiones recibidas
- Desglose por tipo de acción
- Número de usuarios únicos
- Notificaciones enviadas
- Usuarios baneados (si hay)

## ⚙️ Administración

Los administradores pueden:
- Ver estadísticas completas
- Gestionar usuarios baneados (próximamente)
- Acceder sin restricciones de rate limit
- Recibir notificaciones por email de todas las acciones

## 📁 Estructura del Proyecto

El proyecto ahora está organizado en **módulos independientes** para facilitar el mantenimiento:

```
bot_telegram/
├── bot.py                 # Archivo principal (orquestador)
├── acceso.py              # Control de acceso, rate limiting y permisos
├── estadisticas.py        # Sistema de estadísticas y registro
├── bandas.py              # Búsqueda de bandas en MusicBrainz
├── tiempo.py              # Consulta del tiempo (Open-Meteo)
├── saludos.py             # Respuestas a saludos
├── admin.py               # Comandos administrativos
├── comandos.py            # Comandos principales (/start, /stats, /miid)
├── calendario_cmd.py      # Interacción del calendario
├── calendario.py          # Lógica del calendario laboral
├── notificaciones.py      # Sistema de notificaciones por email
├── calendario.json        # Almacenamiento de turnos (se crea automáticamente)
├── requirements.txt       # Dependencias del proyecto
├── .env                   # Variables de entorno (configuración)
└── INSTRUCTIONS.md        # Este archivo
```

### 🏗️ Arquitectura Modular

Cada funcionalidad está separada en su propio módulo:

- **`bot.py`** - Coordina todos los módulos y registra handlers
- **`acceso.py`** - Seguridad y control de acceso
- **`estadisticas.py`** - Seguimiento de uso
- **`bandas.py`** - API de MusicBrainz
- **`tiempo.py`** - API de Open-Meteo
- **`saludos.py`** - Procesamiento de mensajes de texto
- **`admin.py`** - Gestión administrativa
- **`comandos.py`** - Comandos del bot
- **`calendario_cmd.py`** - Interfaz de usuario del calendario

Esta arquitectura permite:
- ✅ **Mantenimiento más fácil** - Cada módulo es independiente
- ✅ **Mejor organización** - Código separado por responsabilidades
- ✅ **Escalabilidad** - Fácil agregar nuevas funcionalidades
- ✅ **Testing** - Cada módulo se puede probar por separado

## 🔧 Resolución de Problemas

### El bot no responde

1. Verifica que el token en `.env` sea correcto
2. Asegúrate de que el bot esté ejecutándose
3. Comprueba que no hay errores en la terminal

### Errores de "Query is too old"

- Estos errores son normales al reiniciar el bot
- Se deben a callbacks antiguos que expiraron
- No afectan el funcionamiento del bot
- Las nuevas interacciones funcionarán correctamente

### Problemas con notificaciones por email

1. Si usas Gmail, necesitas una "Contraseña de aplicación":
   - Ve a tu cuenta de Google → Seguridad
   - Activa la verificación en 2 pasos
   - Genera una contraseña de aplicación
   - Usa esa contraseña en `SMTP_PASS`

2. Verifica que `EMAIL_ACTIVO=true` en `.env`

### El calendario no guarda cambios

- Verifica que el bot tenga permisos de escritura en el directorio
- El archivo `calendario.json` se crea automáticamente
- En caso de error, elimina `calendario.json` y reinicia el bot

## 🆘 Soporte

Para obtener tu ID de usuario y configurar el bot:
1. Inicia el bot con `/start`
2. Usa `/miid` para obtener tu ID
3. Añade tu ID a `ADMIN_IDS` en el archivo `.env`
4. Reinicia el bot

## 📝 Notas Adicionales

- El bot usa la API gratuita de Open-Meteo para el tiempo (no requiere API key)
- Las búsquedas de bandas usan MusicBrainz (servicio gratuito)
- Los datos del calendario se almacenan localmente en `calendario.json`
- Las notificaciones se envían en segundo plano sin afectar el rendimiento

---

¡Disfruta usando tu bot de Telegram! 🎉
