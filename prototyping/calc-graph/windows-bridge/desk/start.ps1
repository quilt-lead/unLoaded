# Start the bridge DETACHED (Win32_Process.Create puts it outside the SSH session's job
# object, so it survives the ssh that started it), bound to 127.0.0.1 only.
param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$root = 'C:\calcgraph'
$pidFile = "$root\bridge.pid"
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    if (Get-Process -Id $old -ErrorAction SilentlyContinue) { "ALREADY RUNNING pid=$old"; exit 0 }
    Remove-Item $pidFile
}
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) { "PORT $Port BUSY (pid $($busy.OwningProcess))"; exit 2 }
$log = "$root\logs\bridge-$(Get-Date -Format yyyyMMdd-HHmmss).log"
$cmd = "cmd.exe /c `"cd /d $root\bridge && $root\venv\Scripts\python.exe -m calcgraph_bridge --port $Port > `"$log`" 2>&1`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = "$root\bridge" }
if ($r.ReturnValue -ne 0) { "START FAILED code=$($r.ReturnValue)"; exit 1 }
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    $l = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($l) {
        $l | ForEach-Object { "LISTENING $($_.LocalAddress):$($_.LocalPort) pid=$($_.OwningProcess)" }
        Set-Content $pidFile $r.ProcessId
        "STARTED cmd-pid=$($r.ProcessId) log=$log"
        exit 0
    }
}
"NOT LISTENING after 30 s; log:"; Get-Content $log -Tail 40
exit 1
