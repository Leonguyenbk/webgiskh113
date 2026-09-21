# Đăng ký Windows Scheduled Task "WebGIS-RefreshGcnStats" chạy
# refresh_gcn_stats.ps1 mỗi 15 phút, vô thời hạn — thay pg_cron đã mất khi
# chuyển từ Supabase sang Postgres local. Chạy 1 lần (đã Administrator) để
# đăng ký; chạy lại để cập nhật nếu đổi giờ/logic.

$ErrorActionPreference = "Stop"
$taskName = "WebGIS-RefreshGcnStats"
$scriptDir = $PSScriptRoot
$ps1 = Join-Path $scriptDir "refresh_gcn_stats.ps1"
$log = Join-Path (Split-Path $scriptDir -Parent) "refresh_gcn_stats.log"

$action = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ps1`" >> `"$log`" 2>&1"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force -Description `
    "Gọi POST /api/gcn-stats/refresh mỗi 15 phút — thay pg_cron cho trang /thong-ke-gcn"

Write-Output "Đã đăng ký task '$taskName'."
