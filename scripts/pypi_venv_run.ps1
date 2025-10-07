# Bootstrap a local venv, install codex-cli-linker from PyPI, then run it.
# Uses $CODEX_HOME\venv by default to keep the environment isolated.

$ErrorActionPreference = 'Stop'

$base = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$venv = Join-Path $base 'venv\codex-cli-linker'

if (-not (Test-Path $venv)) {
  New-Item -ItemType Directory -Force -Path (Split-Path $venv) | Out-Null
  python -m venv $venv
}

$py = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Python not found in venv: $venv" }

& $py -m pip -q install --upgrade pip | Out-Null
& $py -m pip install -q -U codex-cli-linker | Out-Null

$exe = Join-Path $venv 'Scripts\codex-cli-linker.exe'
if (-not (Test-Path $exe)) { $exe = Join-Path $venv 'Scripts\codex-cli-linker' }
& $exe @args

