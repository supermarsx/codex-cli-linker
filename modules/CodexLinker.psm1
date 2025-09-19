function Get-CodexLinkerCommand {
    <#
    .SYNOPSIS
        Resolve the codex-cli-linker executable path.
    #>
    if ($env:CODEX_LINKER_CMD) {
        return $env:CODEX_LINKER_CMD
    }
    foreach ($candidate in @("codex-cli-linker", "codex-cli-linker.py")) {
        $resolved = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($resolved) {
            return $resolved.Source
        }
    }
    return $null
}

function Invoke-CodexCommand {
    <#
    .SYNOPSIS
        Invoke the Codex CLI (prefers `codex`, falls back to `npx codex`).
    #>
    param(
        [string[]]$Arguments
    )

    $codex = Get-Command codex -ErrorAction SilentlyContinue
    if ($codex) {
        & $codex.Source @Arguments
        return
    }

    $npx = Get-Command npx -ErrorAction SilentlyContinue
    if ($npx) {
        & $npx.Source @('codex') + $Arguments
        return
    }

    throw "Codex CLI not found. Install codex globally or ensure npx is available."
}

function Get-CodexConfigPaths {
    <#
    .SYNOPSIS
        Return the config directory and state file locations.

    .PARAMETER WorkspaceState
        Switch to prefer the workspace `.codex-linker.json` file.
    #>
    param([switch]$WorkspaceState)

    $home = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path ([Environment]::GetFolderPath('ApplicationData')) '.codex' }
    $state = if ($WorkspaceState) { Join-Path (Get-Location) '.codex-linker.json' } else { Join-Path $home 'linker_config.json' }

    [pscustomobject]@{
        Home        = $home
        State       = $state
        ConfigToml  = Join-Path $home 'config.toml'
        ConfigJson  = Join-Path $home 'config.json'
        ConfigYaml  = Join-Path $home 'config.yaml'
    }
}

function Save-CodexProfile {
    <#
    .SYNOPSIS
        Run codex-cli-linker to generate configuration files.

    .PARAMETER BaseUrl
        Base URL for the target server (e.g., http://localhost:1234/v1).
    .PARAMETER Profile
        Profile name to write (passes --profile).
    .PARAMETER Model
        Model identifier when skipping interactive selection.
    .PARAMETER Json
        Switch: also write config.json.
    .PARAMETER Yaml
        Switch: also write config.yaml.
    .PARAMETER Doctor
        Switch: run `--doctor` before saving and stop on failure.
    .PARAMETER WorkspaceState
        Switch: prefer workspace `.codex-linker.json` instead of `$CODEX_HOME/linker_config.json`.
    .PARAMETER AdditionalArgs
        Extra arguments forwarded to codex-cli-linker.
    #>
    [CmdletBinding()]
    param(
        [string]$BaseUrl,
        [string]$Profile,
        [string]$Model,
        [switch]$Json,
        [switch]$Yaml,
        [switch]$Doctor,
        [switch]$WorkspaceState,
        [string[]]$AdditionalArgs
    )

    $cliPath = Get-CodexLinkerCommand
    if (-not $cliPath) {
        throw "codex-cli-linker executable not found on PATH."
    }

    $args = @()
    if ($BaseUrl) { $args += @('--base-url', $BaseUrl) }
    if ($Profile) { $args += @('--profile', $Profile) }
    if ($Model) { $args += @('--model', $Model) }
    if ($Json) { $args += '--json' }
    if ($Yaml) { $args += '--yaml' }
    if ($WorkspaceState) { $args += '--workspace-state' }

    if ($Doctor) {
        & $cliPath @('--doctor') + $args + $AdditionalArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Doctor checks failed (exit code $LASTEXITCODE)."
        }
    }

    & $cliPath @args + $AdditionalArgs
    if ($LASTEXITCODE -ne 0) {
        throw "codex-cli-linker exited with code $LASTEXITCODE."
    }
}

function Use-CodexProfile {
    <#
    .SYNOPSIS
        Launch the Codex CLI for a given profile, optionally ensuring config first.

    .PARAMETER Profile
        Profile name to pass to `codex --profile`.
    .PARAMETER LinkerArgs
        Extra arguments forwarded to `Save-CodexProfile` when `-Ensure` is specified.
    .PARAMETER CodexArgs
        Extra arguments forwarded to the Codex CLI.
    .PARAMETER Ensure
        Run Save-CodexProfile first before launching Codex.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Profile,
        [string[]]$LinkerArgs,
        [string[]]$CodexArgs,
        [switch]$Ensure
    )

    if ($Ensure) {
        Save-CodexProfile -Profile $Profile -AdditionalArgs $LinkerArgs
    }

    Invoke-CodexCommand -Arguments @('--profile', $Profile) + $CodexArgs
}

function Open-CodexConfig {
    <#
    .SYNOPSIS
        Open generated config files in the default editor.

    .PARAMETER WorkspaceState
        Switch: use workspace `.codex-linker.json` when locating files.
    .PARAMETER IncludeJson
        Switch: open config.json.
    .PARAMETER IncludeYaml
        Switch: open config.yaml.
    #>
    [CmdletBinding()]
    param(
        [switch]$WorkspaceState,
        [switch]$IncludeJson,
        [switch]$IncludeYaml
    )

    $paths = Get-CodexConfigPaths -WorkspaceState:$WorkspaceState
    $targets = @($paths.ConfigToml)
    if ($IncludeJson) { $targets += $paths.ConfigJson }
    if ($IncludeYaml) { $targets += $paths.ConfigYaml }

    foreach ($item in $targets | Where-Object { $_ }) {
        if (Test-Path $item) {
            Invoke-Item $item
        }
    }
}

Export-ModuleMember -Function `
    Get-CodexConfigPaths,
    Save-CodexProfile,
    Use-CodexProfile,
    Open-CodexConfig
