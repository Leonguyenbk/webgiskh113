# Gọi định kỳ POST /api/nhom3-con-thieu/refresh để tính lại bảng cache
# nhom3_trang_thai_cache (trang /nhom-3-con-thieu đọc từ bảng này, không
# tính trực tiếp mỗi lần load vì quét toàn bộ nhom3_can_thu_thap rất nặng
# khi bảng lên tới hàng triệu dòng — xem supabase/schema.sql).
#
# Đăng ký chạy mỗi 3 giờ bằng Windows Task Scheduler (xem
# register_refresh_nhom3_stats_task.ps1 cùng thư mục). Gọi gấp ngay khi
# cần (vừa nạp danh sách mới) thì gọi tay script này hoặc POST thẳng
# endpoint, không cần chờ tới lượt chạy theo lịch.
#
# IMPORT_TOKEN đọc thẳng từ backend/.env — không hardcode ở đây.

$ErrorActionPreference = "Stop"

$envPath = Join-Path $PSScriptRoot "..\.env"
$tokenLine = Get-Content $envPath | Where-Object { $_ -match '^IMPORT_TOKEN=' } | Select-Object -First 1
if (-not $tokenLine) {
    Write-Error "Không tìm thấy IMPORT_TOKEN trong $envPath"
    exit 1
}
$token = ($tokenLine -replace '^IMPORT_TOKEN=', '').Trim()

$portLine = Get-Content $envPath | Where-Object { $_ -match '^PORT=' } | Select-Object -First 1
$port = if ($portLine) { ($portLine -replace '^PORT=', '').Trim() } else { "5000" }

try {
    $resp = Invoke-WebRequest -Uri "http://localhost:$port/api/nhom3-con-thieu/refresh" `
        -Method POST -Headers @{ "X-Import-Token" = $token } `
        -UseBasicParsing -TimeoutSec 320
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] OK: $($resp.Content)"
} catch {
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] LỖI: $_"
    exit 1
}
