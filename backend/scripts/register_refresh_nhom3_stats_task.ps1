# Đăng ký Windows Scheduled Task "WebGIS-RefreshNhom3Stats" chạy
# refresh_nhom3_stats.ps1 mỗi 3 giờ, vô thời hạn. Cùng kiểu với
# WebGIS-RefreshGcnStats (register_refresh_gcn_stats_task.ps1) nhưng cho
# cache Nhóm 3 (nhom3_trang_thai_cache) — chu kỳ thưa hơn (3 giờ so với 15
# phút) vì danh sách Nhóm 3 chỉ nạp thủ công, không đổi liên tục; cần gấp
# thì gọi tay refresh_nhom3_stats.ps1 hoặc POST thẳng endpoint, không cần
# chờ lịch. Chạy 1 lần (đã Administrator) để đăng ký; chạy lại để cập
# nhật nếu đổi giờ/logic.

$ErrorActionPreference = "Stop"
$taskName = "WebGIS-RefreshNhom3Stats"
$scriptDir = $PSScriptRoot
$ps1 = Join-Path $scriptDir "refresh_nhom3_stats.ps1"
$log = Join-Path (Split-Path $scriptDir -Parent) "refresh_nhom3_stats.log"

$action = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ps1`" >> `"$log`" 2>&1"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours 3) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force -Description `
    "Gọi POST /api/nhom3-con-thieu/refresh mỗi 3 giờ — tính lại cache nhom3_trang_thai_cache cho trang /nhom-3-con-thieu"

Write-Output "Đã đăng ký task '$taskName'."
