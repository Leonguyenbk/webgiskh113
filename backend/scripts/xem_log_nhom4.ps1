# Xem LIVE các lượt nộp biểu Nhóm 4 (đọc log proxy frontend — có cả lượt bị
# đứt giữa chừng, khác backend/logs/nhom4_submit.log chỉ có lượt tới được
# backend). Mỗi dòng: giờ, kết quả, nhà mạng, dung lượng, thời gian, tốc độ, IP.
# Chạy: powershell -File backend\scripts\xem_log_nhom4.ps1 [-Tail 20]
# Ctrl+C để thoát.
param([int]$Tail = 20)

$log = Join-Path $PSScriptRoot "..\..\frontend\service-stdout.log"

function Get-NhaMang($ip) {
    if ($ip -match '^(2402:800|171\.|27\.|116\.)') { return 'Viettel' }
    if ($ip -match '^(2001:ee[01]|14\.|113\.|123\.|222\.)') { return 'VNPT' }
    if ($ip -match '^(2405:48|42\.11)') { return 'FPT' }
    return 'Khac'
}

Get-Content $log -Tail $Tail -Wait -Encoding utf8 | Where-Object { $_ -like '{*tong_ms*' } | ForEach-Object {
    $r = $_ | ConvertFrom-Json
    $mb = if ($r.bytes) { $r.bytes / 1MB } else { 0 }
    $giay = $r.tong_ms / 1000
    $mbs = if ($giay -gt 0) { $mb / $giay } else { 0 }
    if ($r.bi_huy) { $kq = 'DUT'; $mau = 'Red' }
    elseif ($r.status -eq 200) { $kq = 'OK '; $mau = if ($mbs -lt 0.5) { 'Yellow' } else { 'Green' } }
    else { $kq = "L$($r.status)"; $mau = 'Magenta' }
    $line = '{0}  {1}  {2,-7}  {3,6:N1} MB  {4,6:N1} s  {5,6:N2} MB/s  {6}' -f `
        $r.luc.Substring(11), $kq, (Get-NhaMang $r.ip), $mb, $giay, $mbs, $r.ip
    Write-Host $line -ForegroundColor $mau
}
