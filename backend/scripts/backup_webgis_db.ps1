# Backup hàng ngày database webgis (pg_dump custom format -Fc), giữ 14
# bản gần nhất rồi tự xóa bản cũ hơn.
#
# Trước đây chạy trên Supabase, backup managed tự động. Chuyển sang
# Postgres local (xem README của backend/gcn_sync.py, mplis_sync.py) thì
# không còn gì lo việc này nữa nếu không tự thiết lập — script này +
# register_backup_webgis_task.ps1 (Task Scheduler, chạy mỗi ngày) thay
# thế phần đó.
#
# Khôi phục 1 bản: pg_restore -h localhost -p 5433 -U postgres -d webgis
# --clean --if-exists "<file>.dump"

$ErrorActionPreference = "Stop"

$envPath = Join-Path $PSScriptRoot "..\.env"
$dbUrlLine = Get-Content $envPath | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
if (-not $dbUrlLine) {
    Write-Error "Không tìm thấy DATABASE_URL trong $envPath"
    exit 1
}
$dbUrl = ($dbUrlLine -replace '^DATABASE_URL=', '').Trim()

if ($dbUrl -notmatch '^postgresql://(?<user>[^:]+):(?<pass>[^@]+)@(?<host>[^:/]+):(?<port>\d+)/(?<db>.+)$') {
    Write-Error "Không đọc được DATABASE_URL: $dbUrl"
    exit 1
}
$dbUser = $matches['user']
$dbPass = $matches['pass']
$dbHost = $matches['host']
$dbPort = $matches['port']
$dbName = $matches['db']

$backupDir = "D:\QUANGTUAN\db_backups\webgis"
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $backupDir "webgis_$stamp.dump"

$pgDump = "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"
$env:PGPASSWORD = $dbPass

try {
    & $pgDump -h $dbHost -p $dbPort -U $dbUser -d $dbName -Fc -f $outFile
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump thoát với mã $LASTEXITCODE"
    }
    $size = (Get-Item $outFile).Length
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] OK: $outFile ($([math]::Round($size/1MB,1)) MB)"
} catch {
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] LỖI: $_"
    exit 1
} finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

# Giữ 14 bản gần nhất — xóa file cũ hơn 14 ngày.
Get-ChildItem $backupDir -Filter "webgis_*.dump" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } |
    ForEach-Object {
        Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Xóa bản cũ: $($_.Name)"
        Remove-Item $_.FullName -Force
    }
