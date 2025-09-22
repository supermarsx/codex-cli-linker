# Scoop Support

## Installing via Scoop

```powershell
scoop bucket add codex-cli-linker https://github.com/supermarsx/codex-cli-linker
scoop install codex-cli-linker
codex-cli-linker --auto
```

Scoop installs the Windows binary in `~/scoop/apps/codex-cli-linker/current/` and
symlinks `codex-cli-linker.exe` onto your PATH. The CLI detects Scoop installs and
checks GitHub Releases for updates accordingly.

To update after a new release lands:

```powershell
scoop update codex-cli-linker
```

## Maintaining the Manifest

The Scoop manifest lives at `scoop/codex-cli-linker.json`. When cutting a new release:

1. Ensure a Windows binary is published in the GitHub release assets (e.g. `codex-cli-linker-windows-x64.exe`).
2. Update the manifest `version` field.
3. Point the download `url` to the new release asset (usually `https://github.com/.../releases/download/v<version>/codex-cli-linker-windows-x64.exe`).
4. Refresh the SHA256 with:
   ```powershell
   Invoke-WebRequest -Uri "https://github.com/.../codex-cli-linker-windows-x64.exe" -OutFile codex-cli-linker.exe
   Get-FileHash -Algorithm SHA256 .\codex-cli-linker.exe
   Remove-Item .\codex-cli-linker.exe
   ```
5. Commit the updated manifest alongside the new release tag.

If you maintain a Scoop bucket separately, you can copy this manifest there or
use this repository as a bucket by adding it via `scoop bucket add` (as shown above).
