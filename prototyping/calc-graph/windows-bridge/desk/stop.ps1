# Stop the bridge started by start.ps1: kill the recorded cmd.exe and its python children.
param([int]$Port = 8765)
$root = 'C:\calcgraph'
$pidFile = "$root\bridge.pid"
$killed = @()
if (Test-Path $pidFile) {
    $p = [int](Get-Content $pidFile)
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$p" | ForEach-Object {
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$($_.ProcessId)" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $killed += $_.ProcessId }
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $killed += $_.ProcessId
    }
    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; $killed += $p
    Remove-Item $pidFile
}
# Belt and braces: anything of OURS still listening on the port (only python from C:\calcgraph).
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    if ($proc -and $proc.Path -like "$root\*") { Stop-Process -Id $proc.Id -Force; $killed += $proc.Id }
}
Start-Sleep -Milliseconds 500
$still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
"killed: $($killed -join ',')"
if ($still) { "STILL LISTENING pid=$($still.OwningProcess)"; exit 1 } else { "STOPPED (port $Port free)" }
