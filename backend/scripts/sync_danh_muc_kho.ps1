# Gọi định kỳ POST /api/danh-muc-trong-kho/sync: tải Google Sheet danh mục
# hồ sơ gốc (DANH_MUC_KHO_SHEET_URL trong backend/.env, mặc định xem
# app/config.py), tách dòng rồi upsert vào bảng danh_muc_trong_kho.
#
# Đăng ký chạy mỗi 1 giờ bằng Windows Task Scheduler (xem
# register_sync_danh_muc_kho_task.ps1 cùng thư mục). Cần gấp thì gọi tay
# script này.
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
    $resp = Invoke-WebRequest -Uri "http://localhost:$port/api/danh-muc-trong-kho/sync" `
        -Method POST -Headers @{ "X-Import-Token" = $token } `
        -UseBasicParsing -TimeoutSec 220
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] OK: $($resp.Content)"
} catch {
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] LỖI: $_"
    exit 1
}
