# Chạy theo lịch (Task Scheduler "WebGIS-SyncGcnSheets", xem
# register_sync_gcn_sheets_task.ps1): đồng bộ tuần tự mọi Google Sheet
# nguồn GCN vào du_lieu_gcn (sync_gcn_sheets.py), xong thì tính lại ngay 2
# bảng cache số liệu (Nhóm 3 + GCN theo xã) qua endpoint của backend đang
# chạy — để trang /nhom-3-con-thieu thấy số mới luôn, không phải chờ lịch
# refresh riêng (và backend tự xoá cache trong bộ nhớ của nó).

$backend = Split-Path $PSScriptRoot -Parent
Set-Location $backend

& "$backend\.venv\Scripts\python.exe" "$PSScriptRoot\sync_gcn_sheets.py"
$code = $LASTEXITCODE

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\refresh_nhom3_stats.ps1"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\refresh_gcn_stats.ps1"

exit $code
