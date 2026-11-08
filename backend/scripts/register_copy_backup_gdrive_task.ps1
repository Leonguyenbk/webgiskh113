# Đăng ký task "WebGIS-CopyBackupGDrive" chạy copy_backup_to_gdrive.ps1 lúc
# 04:00 Chủ nhật hằng tuần (sau backup 03:00). Chạy bằng tài khoản
# Administrator, chỉ khi đang đăng nhập, vì ổ G: (Google Drive) chỉ có
# trong phiên đó. Chạy lại để cập nhật.

$ErrorActionPreference = "Stop"
$taskName = "WebGIS-CopyBackupGDrive"
$scriptDir = $PSScriptRoot
$ps1 = Join-Path $scriptDir "copy_backup_to_gdrive.ps1"
$log = Join-Path (Split-Path $scriptDir -Parent) "copy_backup_to_gdrive.log"

$action = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ps1`" >> `"$log`" 2>&1"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "04:00"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\Administrator" -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force -Description `
    "Chép bản backup database webgis mới nhất sang Google Drive mỗi Chủ nhật, giữ 8 bản"

Write-Output "Đã đăng ký task '$taskName'."
