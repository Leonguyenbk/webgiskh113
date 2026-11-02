# Đăng ký Windows Scheduled Task "WebGIS-SyncDanhMucKho" chạy
# sync_danh_muc_kho.ps1 mỗi 1 giờ, vô thời hạn (đồng bộ danh mục trong kho từ
# Google Sheet). Chạy 1 lần (đã Administrator) để đăng ký; chạy lại để cập
# nhật nếu đổi giờ/logic.

$ErrorActionPreference = "Stop"
$taskName = "WebGIS-SyncDanhMucKho"
$scriptDir = $PSScriptRoot
$ps1 = Join-Path $scriptDir "sync_danh_muc_kho.ps1"
$log = Join-Path (Split-Path $scriptDir -Parent) "sync_danh_muc_kho.log"

$action = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ps1`" >> `"$log`" 2>&1"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force -Description `
    "Gọi POST /api/danh-muc-trong-kho/sync mỗi 1 giờ — đồng bộ danh mục trong kho từ Google Sheet"

Write-Output "Đã đăng ký task '$taskName'."
