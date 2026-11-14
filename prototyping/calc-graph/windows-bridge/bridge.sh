#!/usr/bin/env bash
# Mac-side control of the calc-graph Windows bridge.
#
#   ./bridge.sh deploy     copy this package to C:\calcgraph\bridge on the desk
#   ./bridge.sh setup      user-space Python 3.12 + venv under C:\calcgraph (desk/setup.ps1)
#   ./bridge.sh start      start the bridge in the desk user's signed-in session (so the CSI
#                          OAPI can attach to an ETABS started on screen), 127.0.0.1:$PORT
#   ./bridge.sh tunnel     ssh -L $PORT:127.0.0.1:$PORT in the background (pid in $STATE)
#   ./bridge.sh smoke      call the read-only endpoints through the tunnel
#   ./bridge.sh stop       stop the bridge on the desk and close the tunnel
#
# Desk: CALCGRAPH_DESK (default internal-windows-desktop-getst: the inside desk as getst, the
# Windows user who is signed in on screen and owns the ETABS licence sign-in). Port:
# CALCGRAPH_BRIDGE_PORT (8765).
set -euo pipefail
DESK="${CALCGRAPH_DESK:-internal-windows-desktop-getst}"
PORT="${CALCGRAPH_BRIDGE_PORT:-8765}"
HERE="$(cd "$(dirname "$0")" && pwd)"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/calcgraph-bridge"
mkdir -p "$STATE"
URL="http://127.0.0.1:$PORT"

desk_ps() {  # desk_ps <local .ps1> [args...]: scp + run with -File (inline quoting breaks)
  local f="$1"; shift
  local remote="calcgraph-$(basename "$f")"
  scp -q "$f" "$DESK:$remote"
  ssh "$DESK" "powershell -NoProfile -ExecutionPolicy Bypass -File $remote $*; Remove-Item $remote"
}

case "${1:-}" in
  deploy)
    tmp="$(mktemp -d)"
    COPYFILE_DISABLE=1 tar -C "$HERE" --exclude='__pycache__' --exclude='*.pyc' -cf "$tmp/bridge.tar" \
      pyproject.toml calcgraph_bridge desk $( [ -f "$HERE/uv.lock" ] && echo uv.lock )
    ssh "$DESK" "Remove-Item -Recurse -Force C:\\calcgraph\\bridge -ErrorAction SilentlyContinue; New-Item -ItemType Directory -Force -Path C:\\calcgraph\\bridge | Out-Null"
    scp -q "$tmp/bridge.tar" "$DESK:C:/calcgraph/bridge.tar"
    ssh "$DESK" "tar -xf C:\\calcgraph\\bridge.tar -C C:\\calcgraph\\bridge; Remove-Item C:\\calcgraph\\bridge.tar; Get-ChildItem -Recurse C:\\calcgraph\\bridge -File | Measure-Object | ForEach-Object { 'DEPLOYED ' + \$_.Count + ' files' }"
    rm -rf "$tmp" ;;
  setup)  desk_ps "$HERE/desk/setup.ps1" ;;
  start)  desk_ps "$HERE/desk/start.ps1" -Port "$PORT" ;;
  tunnel)
    if [ -f "$STATE/tunnel.pid" ] && kill -0 "$(cat "$STATE/tunnel.pid")" 2>/dev/null; then
      echo "tunnel already up pid=$(cat "$STATE/tunnel.pid")"; exit 0; fi
    ssh -N -o ExitOnForwardFailure=yes -L "$PORT:127.0.0.1:$PORT" "$DESK" &
    echo $! > "$STATE/tunnel.pid"
    for _ in $(seq 1 20); do curl -fsS "$URL/health" >/dev/null 2>&1 && break; sleep 0.5; done
    echo "tunnel pid=$(cat "$STATE/tunnel.pid") -> $DESK 127.0.0.1:$PORT" ;;
  smoke)
    for ep in /health /inventory /dotnet/probe /bhom/status /csi/status; do
      echo "== GET $ep"; curl -sS -w '\nHTTP %{http_code}\n' "$URL$ep"; done ;;
  stop)
    desk_ps "$HERE/desk/stop.ps1" -Port "$PORT" || true
    if [ -f "$STATE/tunnel.pid" ]; then kill "$(cat "$STATE/tunnel.pid")" 2>/dev/null || true; rm -f "$STATE/tunnel.pid"; echo "tunnel closed"; fi ;;
  *) sed -n '2,13p' "$0"; exit 2 ;;
esac
