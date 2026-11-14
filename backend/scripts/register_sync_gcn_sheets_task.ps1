# Đăng ký Windows Scheduled Task "WebGIS-SyncGcnSheets" chạy
# sync_gcn_sheets.ps1 MỖI 1 GIỜ, vô thời hạn — đồng bộ Google Sheet nguồn
# GCN của các xã ngay trên máy chủ (thay lịch GitHub Actions bị giãn 6–9
# giờ/lần). Một lượt ~102 nguồn mất khoảng 20–30 phút; lượt trước chưa xong
# thì lượt mới bị bỏ qua (MultipleInstances IgnoreNew), quá 55 phút thì dừng.
# Chạy 1 lần bằng PowerShell "Run as Administrator"; chạy lại để cập nhật.

$ErrorActionPreference = "Stop"
$taskName = "WebGIS-SyncGcnSheets"
$scriptDir = $PSScriptRoot
$ps1 = Join-Path $scriptDir "sync_gcn_sheets.ps1"
$log = Join-Path (Split-Path $scriptDir -Parent) "sync_gcn_sheets.log"

$action = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ps1`" >> `"$log`" 2>&1"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 55)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force -Description `
    "Đồng bộ Google Sheet nguồn GCN các xã vào du_lieu_gcn mỗi 1 giờ, rồi tính lại cache Nhóm 3 + GCN theo xã"

Write-Output "Đã đăng ký task '$taskName' — lượt đầu chạy sau 1 phút, log: $log"
