# One-time, user-space setup on the desk. Everything lands under C:\calcgraph (no admin,
# no PATH or registry changes, existing Python/uv installs untouched):
#   C:\calcgraph\bin\uv.exe       copy of an existing uv, or downloaded if none is found
#   C:\calcgraph\python\          uv-managed CPython 3.12
#   C:\calcgraph\venv\            the bridge's environment (fastapi, uvicorn, pythonnet)
#   C:\calcgraph\bridge\          this package (copied by bridge.sh deploy; run from source, not installed)
$ErrorActionPreference = 'Stop'
$root = 'C:\calcgraph'
New-Item -ItemType Directory -Force -Path "$root\bin", "$root\logs", "$root\work", "$root\cache" | Out-Null
$uv = "$root\bin\uv.exe"
if (-not (Test-Path $uv)) {
    $existing = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $existing) { $existing = Get-Item "$env:USERPROFILE\.local\bin\uv.exe" -ErrorAction SilentlyContinue }
    if ($existing) {
        $src = if ($existing.Source) { $existing.Source } else { $existing.FullName }
        Copy-Item $src $uv
    } else {
        $zip = "$root\cache\uv.zip"
        Invoke-WebRequest -UseBasicParsing 'https://github.com/astral-sh/uv/releases/download/0.11.16/uv-x86_64-pc-windows-msvc.zip' -OutFile $zip
        Expand-Archive $zip -DestinationPath "$root\bin" -Force
    }
}
$env:UV_PYTHON_INSTALL_DIR = "$root\python"
$env:UV_CACHE_DIR = "$root\cache\uv"
$env:UV_PROJECT_ENVIRONMENT = "$root\venv"
$env:UV_PYTHON_PREFERENCE = 'only-managed'
& $uv --version
& $uv python install 3.12
Push-Location "$root\bridge"
try { & $uv sync --python 3.12 --frozen --no-install-project } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { "SETUP FAILED: uv sync exit $LASTEXITCODE"; exit 1 }
& "$root\venv\Scripts\python.exe" -c "import sys; from importlib.metadata import version as v; print('python', sys.version.split()[0], sys.executable); print(*(f'{p} {v(p)}' for p in ('fastapi', 'uvicorn', 'pythonnet', 'clr-loader')))"
if ($LASTEXITCODE -ne 0) { "SETUP FAILED: import check"; exit 1 }
"SETUP OK"
