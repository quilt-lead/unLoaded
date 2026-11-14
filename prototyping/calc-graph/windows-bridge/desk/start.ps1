# Start the bridge INSIDE the signed-in desktop session of the ssh user, bound to 127.0.0.1.
#
# Why not straight from ssh: a process started over ssh (or via WMI Win32_Process.Create) runs in
# Windows session 0. The CSI OAPI attach (cHelper.GetObject) reads the Running Object Table, which
# is per session, so a session-0 bridge can never attach to an ETABS someone started on screen
# (session 1): /csi/start {"attach": true} fails with "could not attach to CSI.ETABS.API.ETABSObject"
# (seen 2026-11-14). A one-shot scheduled task with /it ("only when the user is logged on") runs
# in that user's interactive session instead; pythonw keeps it windowless. It outlives the ssh
# that started it, and the task definition is deleted once the bridge listens.
param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$root = 'C:\calcgraph'
$pidFile = "$root\bridge.pid"
$task = 'calcgraph-bridge'
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    if (Get-Process -Id $old -ErrorAction SilentlyContinue) { "ALREADY RUNNING pid=$old"; exit 0 }
    Remove-Item $pidFile
}
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) { "PORT $Port BUSY (pid $($busy.OwningProcess))"; exit 2 }
$me = $env:USERNAME
$desk = Get-CimInstance Win32_Process -Filter "Name='explorer.exe'" | Where-Object {
    $_.SessionId -gt 0 -and (Invoke-CimMethod -InputObject $_ -MethodName GetOwner).User -eq $me }
if (-not $desk) { "NO INTERACTIVE SESSION for $me (nobody signed in on screen as $me): the bridge must run in that session to attach to ETABS"; exit 3 }
$log = "$root\logs\bridge-$(Get-Date -Format yyyyMMdd-HHmmss).log"
$tr = "$root\venv\Scripts\pythonw.exe $root\bridge\desk\run_bridge.py --port $Port --log $log"
schtasks /create /tn $task /tr $tr /sc once /st 23:59 /it /f /rl LIMITED | Out-Null
if ($LASTEXITCODE -ne 0) { "SCHTASKS CREATE FAILED code=$LASTEXITCODE"; exit 1 }
schtasks /run /tn $task | Out-Null
try {
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        $l = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($l) {
            $sess = (Get-Process -Id $l.OwningProcess).SessionId
            "LISTENING $($l.LocalAddress):$($l.LocalPort) pid=$($l.OwningProcess) session=$sess"
            Set-Content $pidFile $l.OwningProcess
            "STARTED log=$log"
            exit 0
        }
    }
    "NOT LISTENING after 30 s; log:"; if (Test-Path $log) { Get-Content $log -Tail 40 }
    exit 1
} finally {
    schtasks /delete /tn $task /f | Out-Null
}
