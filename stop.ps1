# Script para detener el bot de Telegram
# Uso: .\stop.ps1

Write-Host "🛑 Deteniendo bot de Telegram..." -ForegroundColor Red
Write-Host ""

taskkill /F /IM python.exe 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Bot detenido correctamente" -ForegroundColor Green
} else {
    Write-Host "ℹ️  No había ningún bot corriendo" -ForegroundColor Gray
}

Write-Host ""
