# Kurulumdan once bu klasordeki acik Kafe Kamera panelini kapatir: once panelin kendi Kapat istegiyle (Studio kosulari da
# duzgunce durur), kapanmazsa yalnizca bu exe'nin sureclerini sonlandirarak. Kapat istegi yalnizca bu sureclerin
# dinledigi portlara gider. Cikis kodu: 0 kapali, 1 hala acik.
param([Parameter(Mandatory = $true)][string]$Uygulama)
$ErrorActionPreference = 'SilentlyContinue'
$hedef = [IO.Path]::GetFullPath($Uygulama)
function Surecler { @(Get-Process -Name KafeKamera -ErrorAction SilentlyContinue | Where-Object { $_.Path -and ($_.Path -ieq $hedef) }) }
$ilk = Surecler
if ($ilk.Count -eq 0) { exit 0 }
$portlar = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $ilk.Id -contains $_.OwningProcess } | Select-Object -ExpandProperty LocalPort -Unique)
foreach ($p in $portlar) {
  try {
    Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Method Post -Uri "http://127.0.0.1:$p/api/kapat" `
      -ContentType 'application/json' -Body '{}' | Out-Null
  } catch {}
}
for ($i = 0; $i -lt 40 -and (Surecler).Count -gt 0; $i++) { Start-Sleep -Milliseconds 500 }
foreach ($s in Surecler) { & taskkill.exe /PID $s.Id /T /F | Out-Null }
for ($i = 0; $i -lt 10 -and (Surecler).Count -gt 0; $i++) { Start-Sleep -Milliseconds 500 }
if ((Surecler).Count -gt 0) { exit 1 }
exit 0
