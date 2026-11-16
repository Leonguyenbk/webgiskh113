# Xem LIVE các lượt nộp biểu Nhóm 4 CHỈ của Phường Hòa Hiệp (22261) và
# Xã Hòa Xuân (22291) — đọc backend/logs/nhom4_submit.log (có mã xã; log
# proxy của xem_log_nhom4.ps1 không có). Gồm cả lượt bị chặn ở bước kiểm tra.
# Mỗi dòng: giờ, xã, kết quả, số thửa, dung lượng, thời gian xử lý, nhà mạng,
# IP, lý do lỗi; cuối dòng là số thửa đã lưu HÔM NAY của từng xã.
# Chạy: powershell -ExecutionPolicy Bypass -File backend\scripts\xem_log_nhom4_hoahiep_hoaxuan.ps1 [-Tail 30]
# Ctrl+C để thoát.
param([int]$Tail = 30)

$log = Join-Path $PSScriptRoot "..\logs\nhom4_submit.log"
$XA = @{ '22261' = 'Hoa Hiep'; '22291' = 'Hoa Xuan' }
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$Host.UI.RawUI.WindowTitle = 'Live log Nhom 4 - Hoa Hiep + Hoa Xuan'

function Get-NhaMang($ip) {
    if ($ip -match '^(2402:800|171\.|27\.|116\.)') { return 'Viettel' }
    if ($ip -match '^(2001:ee[01]|14\.|113\.|123\.|222\.)') { return 'VNPT' }
    if ($ip -match '^(2405:48|42\.11)') { return 'FPT' }
    return 'Khac'
}

$homNay = (Get-Date).ToString('yyyy-MM-dd')
$dem = @{ '22261' = 0; '22291' = 0 }

function Show-Line($r) {
    $mb = if ($r.bytes) { $r.bytes / 1MB } else { 0 }
    $giay = if ($r.xu_ly_ms) { $r.xu_ly_ms / 1000 } else { 0 }
    if ($r.buoc -eq 'kiem_tra') { $kq = "CHAN"; $mau = 'Magenta' }
    elseif ($r.status -eq 200) { $kq = 'OK  '; $mau = 'Green' }
    elseif ($r.status -eq 409) { $kq = 'TRUNG'; $mau = 'DarkYellow' }
    else { $kq = "L$($r.status) "; $mau = 'Red' }
    $loi = if ($r.loi) { ' - ' + ($r.loi -replace '\s+', ' ') } else { '' }
    if ($loi.Length -gt 90) { $loi = $loi.Substring(0, 90) + '...' }
    $line = '{0}  {1,-8}  {2,-5}  {3,2} thua  {4,5:N1} MB  {5,5:N1} s  {6,-7}  {7}{8}   [Hom nay: HH {9} | HX {10}]' -f `
        $r.luc.Substring(11), $XA[$r.ma_xa], $kq, $r.so_thua, $mb, $giay, (Get-NhaMang $r.ip), $r.ip, $loi, `
        $dem['22261'], $dem['22291']
    Write-Host $line -ForegroundColor $mau
}

function Read-Row($text) {
    # Lọc chuỗi trước (log ~170 nghìn dòng), chỉ giải JSON dòng của 2 xã.
    if ($text -notmatch '"ma_xa": "(22261|22291)"') { return $null }
    try { $r = $text | ConvertFrom-Json } catch { return $null }
    if (-not $XA.ContainsKey([string]$r.ma_xa)) { return $null }
    $r.ma_xa = [string]$r.ma_xa
    return $r
}

function Add-Count($r) {
    if ($r.status -eq 200 -and $r.buoc -ne 'kiem_tra' -and $r.luc.StartsWith($homNay)) {
        $dem[$r.ma_xa] += [int]$r.so_thua
    }
}

# Lượt 1: đếm số thửa đã lưu hôm nay và in $Tail lượt gần nhất của 2 xã.
$cu = New-Object System.Collections.Generic.List[object]
# Mở chế độ chia sẻ ReadWrite: backend đang giữ file để ghi log.
$fs = New-Object IO.FileStream((Resolve-Path $log).Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
$sr = New-Object IO.StreamReader($fs, [Text.Encoding]::UTF8)
while (($t = $sr.ReadLine()) -ne $null) {
    $r = Read-Row $t
    if ($r) { $cu.Add($r) }
}
$sr.Close()
$batDau = [Math]::Max(0, $cu.Count - $Tail)
for ($i = 0; $i -lt $cu.Count; $i++) {
    Add-Count $cu[$i]
}
Write-Host "=== Hoa Hiep (22261) + Hoa Xuan (22291) — $Tail luot gan nhat, sau do theo doi LIVE (Ctrl+C de thoat) ===" -ForegroundColor Cyan
for ($i = $batDau; $i -lt $cu.Count; $i++) { Show-Line $cu[$i] }
Write-Host "=== LIVE ===" -ForegroundColor Cyan

# Lượt 2: theo dõi dòng mới.
Get-Content $log -Tail 0 -Wait -Encoding utf8 | ForEach-Object {
    $r = Read-Row $_
    if ($r) {
        if (-not $r.luc.StartsWith($homNay)) { $homNay = $r.luc.Substring(0, 10); $dem['22261'] = 0; $dem['22291'] = 0 }
        Add-Count $r
        Show-Line $r
    }
}
