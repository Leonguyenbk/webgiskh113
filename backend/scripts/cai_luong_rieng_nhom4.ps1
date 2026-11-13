# Tạo LUỒNG RIÊNG cho nhập biểu Nhóm 4: service WebGIS-Backend-Nhom4 (port 5001,
# 16 thread) chạy cùng code backend; frontend (vite.config.js) chuyển mọi
# /api/nhom4/* sang port 5001, phần còn lại (bản đồ...) vẫn ở port 5000.
# Chạy bằng PowerShell "Run as Administrator". Lúc khởi động lại có ~10 giây
# web không truy cập được -> nên chạy lúc ít người nộp (VD nghỉ trưa).
$ErrorActionPreference = "Stop"
$nssm = "C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe"
$B = "D:\QUANGTUAN\webgiskh113\backend"
$S = "WebGIS-Backend-Nhom4"

if (-not (Get-Service $S -ErrorAction SilentlyContinue)) {
    & $nssm install $S "$B\.venv\Scripts\python.exe" "run.py --port 5001 --threads 16"
    & $nssm set $S AppDirectory $B
    & $nssm set $S AppStdout "$B\service-nhom4-stdout.log"
    & $nssm set $S AppStderr "$B\service-nhom4-stderr.log"
    & $nssm set $S AppRotateFiles 1
    & $nssm set $S AppRestartDelay 3000
    & $nssm set $S Start SERVICE_AUTO_START
    & $nssm set $S Description "WebGIS KH113 - backend rieng cho nhap bieu Nhom 4 (port 5001)"
}
Start-Service $S
# Chờ port 5001 sẵn sàng trước khi chuyển frontend sang.
for ($i = 0; $i -lt 30; $i++) {
    try { Invoke-WebRequest "http://127.0.0.1:5001/api/nhom4/loai-dat-options" -UseBasicParsing -TimeoutSec 20 | Out-Null; break } catch { Start-Sleep 1 }
}
"Port 5001 OK"

# Backend chính: 16 -> 24 thread (run.py mặc định mới), pool DB 20 -> 32.
# WebGIS-Frontend và WebGIS-Tunnel phụ thuộc WebGIS-Backend -> dừng cả 3
# (-Force) rồi bật lại theo thứ tự; Frontend bật lại sẽ đọc vite.config.js
# mới (route /api/nhom4 -> 5001).
Stop-Service WebGIS-Backend -Force
Start-Service WebGIS-Backend
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest "http://127.0.0.1:5000/api/nhom4/loai-dat-options" -UseBasicParsing -TimeoutSec 20 | Out-Null; break } catch { Start-Sleep 1 }
}
Start-Service WebGIS-Frontend
Start-Service WebGIS-Tunnel
Start-Sleep 5
Get-Service WebGIS-Backend, WebGIS-Backend-Nhom4, WebGIS-Frontend | Format-Table Name, Status
