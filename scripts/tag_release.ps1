param(
  [Parameter(Mandatory=$true)][string]$Tag
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Usage {
  @'
Usage: scripts\tag_release.ps1 vX.Y.Z

Creates an annotated tag (vX.Y.Z) and pushes it to origin.

Examples:
  scripts\tag_release.ps1 v0.2.1
'@
}

if (-not $Tag) {
  Usage
  exit 1
}

# Accept vX.Y.Z and optional pre-release/build metadata
$pattern = '^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z\.-]+)?$'
if (-not ($Tag -match $pattern)) {
  Write-Error "Tag must match vX.Y.Z (optionally with -prerelease/+build)."
}

# Ensure clean working tree
git diff --quiet | Out-Null
$code1 = $LASTEXITCODE
git diff --cached --quiet | Out-Null
$code2 = $LASTEXITCODE
if ($code1 -ne 0 -or $code2 -ne 0) {
  Write-Error "Working tree not clean. Commit or stash changes first."
}

# Ensure tag does not already exist
git rev-parse -q --verify "refs/tags/$Tag" 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
  Write-Error "Tag $Tag already exists."
}

Write-Host "Creating annotated tag $Tag..."
git tag -a "$Tag" -m "Release $Tag"

Write-Host "Pushing tag $Tag to origin..."
git push origin "$Tag"

Write-Host "Done. Now publish the GitHub Release for $Tag."

