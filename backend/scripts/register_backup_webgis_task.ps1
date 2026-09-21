# Đăng ký Windows Scheduled Task "WebGIS-BackupDb" chạy backup_webgis_db.ps1
# mỗi ngày lúc 03:00, giữ 14 bản gần nhất. Chạy 1 lần (đã Administrator) để
# đăng ký; chạy lại để cập nhật nếu đổi giờ/logic.

$ErrorActionPreference = "Stop"
$taskName = "WebGIS-BackupDb"
$scriptDir = $PSScriptRoot
$ps1 = Join-Path $scriptDir "backup_webgis_db.ps1"
$log = Join-Path (Split-Path $scriptDir -Parent) "backup_webgis_db.log"

$action = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ps1`" >> `"$log`" 2>&1"

$trigger = New-ScheduledTaskTrigger -Daily -At "03:00"

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force -Description `
    "Backup hàng ngày database webgis (pg_dump), giữ 14 bản gần nhất"

Write-Output "Đã đăng ký task '$taskName'."
