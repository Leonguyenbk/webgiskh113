# Gọi định kỳ POST /api/gcn-stats/refresh để tính lại bảng cache
# gcn_thu_thap_theo_xa_cache (trang /thong-ke-gcn đọc từ bảng này, không
# tính trực tiếp mỗi lần load vì quét toàn bộ thua_dat rất nặng).
#
# Thay cho pg_cron (tính năng riêng của Supabase, dùng khi backend còn
# chạy trên Supabase — xem supabase/schema.sql dòng ~974) — Postgres local
# không có extension này, nên phải gọi từ bên ngoài. Đăng ký chạy mỗi 15
# phút bằng Windows Task Scheduler (xem register_refresh_gcn_stats_task.ps1
# cùng thư mục).
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
    $resp = Invoke-WebRequest -Uri "http://localhost:$port/api/gcn-stats/refresh" `
        -Method POST -Headers @{ "X-Import-Token" = $token } `
        -UseBasicParsing -TimeoutSec 200
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] OK: $($resp.Content)"
} catch {
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] LỖI: $_"
    exit 1
}
