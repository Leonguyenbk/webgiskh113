# Chép bản backup database mới nhất (backup_webgis_db.ps1, 03:00 hằng ngày)
# sang Google Drive để có 1 bản nằm ngoài máy chủ, giữ 8 bản gần nhất trên
# Drive. Chạy hằng tuần bằng task "WebGIS-CopyBackupGDrive"
# (register_copy_backup_gdrive_task.ps1).
#
# Ổ G: là Google Drive for desktop, chỉ gắn trong phiên đăng nhập của
# Administrator, nên task chạy bằng tài khoản Administrator (không chạy
# được bằng SYSTEM). Administrator đăng xuất thì task không chạy, log ghi lỗi.

$ErrorActionPreference = "Stop"
$srcDir = "D:\QUANGTUAN\db_backups\webgis"
$dstDir = "G:\My Drive\WEBGIS_DB_BACKUP"
$keep = 8
$ts = { Get-Date -Format 'yyyy-MM-dd HH:mm:ss' }

try {
    if (-not (Test-Path "G:\My Drive")) { throw "Không thấy G:\My Drive (Google Drive chưa chạy hoặc Administrator chưa đăng nhập)" }
    if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }

    $src = Get-ChildItem $srcDir -Filter "webgis_*.dump" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $src) { throw "Không có file backup trong $srcDir" }
    if ($src.LastWriteTime -lt (Get-Date).AddDays(-2)) { throw "Bản backup mới nhất đã cũ: $($src.Name)" }

    $dst = Join-Path $dstDir $src.Name
    if ((Test-Path $dst) -and (Get-Item $dst).Length -eq $src.Length) {
        Write-Output "[$(& $ts)] Đã có trên Drive: $($src.Name)"
    } else {
        Copy-Item $src.FullName "$dst.partial" -Force
        if ((Get-Item "$dst.partial").Length -ne $src.Length) { throw "Chép thiếu dung lượng: $($src.Name)" }
        Move-Item "$dst.partial" $dst -Force
        Write-Output "[$(& $ts)] OK: $dst ($([math]::Round($src.Length/1MB,1)) MB)"
    }

    Get-ChildItem $dstDir -Filter "webgis_*.dump" | Sort-Object LastWriteTime -Descending |
        Select-Object -Skip $keep | ForEach-Object {
            Write-Output "[$(& $ts)] Xóa bản cũ trên Drive: $($_.Name)"
            Remove-Item $_.FullName -Force
        }
} catch {
    Write-Output "[$(& $ts)] LỖI: $_"
    exit 1
}
