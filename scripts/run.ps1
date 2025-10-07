# Run the repository version of codex-cli-linker directly.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Resolve-Path (Join-Path $scriptDir '..')
python "$repoDir\codex-cli-linker.py" @args

