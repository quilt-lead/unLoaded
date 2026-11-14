# Stop the bridge started by start.ps1: kill the recorded (listening) python, its children and
# its pythonw launcher parent - only processes running from C:\calcgraph.
param([int]$Port = 8765)
$root = 'C:\calcgraph'
$pidFile = "$root\bridge.pid"
$killed = @()
function Stop-Ours([int]$id) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$id"
    if ($p -and $p.ExecutablePath -like "$root\*") { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue; $script:killed += $id }
}
if (Test-Path $pidFile) {
    $p = [int](Get-Content $pidFile)
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$p"
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$p" | ForEach-Object { Stop-Ours $_.ProcessId }
    Stop-Ours $p
    if ($proc) { Stop-Ours $proc.ParentProcessId }
    Remove-Item $pidFile
}
# Belt and braces: anything of OURS still listening on the port (only python from C:\calcgraph).
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($_.OwningProcess)"
    Stop-Ours $_.OwningProcess
    if ($proc) { Stop-Ours $proc.ParentProcessId }
}
Start-Sleep -Milliseconds 500
$still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
"killed: $($killed -join ',')"
if ($still) { "STILL LISTENING pid=$($still.OwningProcess)"; exit 1 } else { "STOPPED (port $Port free)" }
