# Script para reiniciar el bot de Telegram
# Uso: .\restart.ps1

Write-Host "🔄 Reiniciando bot de Telegram..." -ForegroundColor Cyan
Write-Host ""

# 1. Detener todas las instancias de Python
Write-Host "⏹️  Deteniendo instancias anteriores..." -ForegroundColor Yellow
taskkill /F /IM python.exe 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Instancias anteriores detenidas" -ForegroundColor Green
} else {
    Write-Host "ℹ️  No había instancias corriendo" -ForegroundColor Gray
}

Write-Host ""

# 2. Esperar un momento para asegurar que los procesos terminaron
Write-Host "⏳ Esperando 2 segundos..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

# 3. Iniciar el bot
Write-Host "🚀 Iniciando bot..." -ForegroundColor Green
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

python bot.py
