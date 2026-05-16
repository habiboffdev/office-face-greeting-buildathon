# Port 8000 dagi eski jarayonni to'xtatib, backendni qayta ishga tushiradi
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    $conn | ForEach-Object {
        Write-Host "Stopping PID $($_.OwningProcess) on port 8000"
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}
Set-Location $PSScriptRoot
& .\venv\Scripts\Activate.ps1
Write-Host "Starting backend on http://127.0.0.1:8000"
uvicorn main:app --host 127.0.0.1 --port 8000
