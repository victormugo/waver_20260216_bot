═══════════════════════════════════════════════════════════════
   🤖 BOT DE TELEGRAM - GUÍA RÁPIDA DE SCRIPTS
═══════════════════════════════════════════════════════════════

📋 SCRIPTS DISPONIBLES:

  ✅ start.ps1    → Inicia el bot
  🛑 stop.ps1     → Detiene el bot
  🔄 restart.ps1  → Reinicia el bot (mata instancias anteriores)


🚀 CÓMO USAR:

  1️⃣  Abre PowerShell en esta carpeta
  2️⃣  Ejecuta el script que necesites:

      .\start.ps1       # Para iniciar
      .\stop.ps1        # Para detener
      .\restart.ps1     # Para reiniciar


💡 CUÁNDO USAR CADA UNO:

  🟢 start.ps1
     - Primera vez que inicias el bot
     - Cuando sabes que no hay instancias corriendo

  🔴 stop.ps1
     - Solo quieres detener el bot temporalmente
     - Antes de hacer cambios en el código

  🔵 restart.ps1  ⭐ RECOMENDADO
     - Después de hacer cambios en el código
     - Cuando hay errores de instancias duplicadas
     - Para un reinicio limpio garantizado


⚠️  PROBLEMAS CON PERMISOS:

Si ves un error sobre "ejecución de scripts deshabilitada":

  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

Solo necesitas hacerlo UNA VEZ.


🔧 ALTERNATIVA MANUAL:

Si no quieres usar scripts:

  # Detener
  taskkill /F /IM python.exe

  # Iniciar
  python bot.py


═══════════════════════════════════════════════════════════════
Para más información, consulta: README.md o INSTRUCTIONS.md
═══════════════════════════════════════════════════════════════
