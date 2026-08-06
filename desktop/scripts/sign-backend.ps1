<#
.SYNOPSIS
    Signs the PyInstaller backend executable with SHA256 + a SHA256 timestamp.

.DESCRIPTION
    electron-builder signs the Electron app, the uninstaller and the
    installer - but NOT backend/dist/UFCPredictor/UFCPredictor.exe, which it
    only copies in as a resource. That binary is what actually runs the
    server, so it has to be signed separately, and *before* `npm run dist`
    packages it. Signing afterwards leaves the copy inside the installer
    unsigned.

    Timestamping matters: without it, every signature stops validating the
    day the certificate expires. With it, they stay valid because the
    timestamp proves the file was signed while the cert was live.

.EXAMPLE
    .\scripts\sign-backend.ps1 -Password "your-pfx-password"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Password,
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pfx      = Join-Path $repoRoot "desktop\certs\code-signing.pfx"
$target   = Join-Path $repoRoot "backend\dist\UFCPredictor\UFCPredictor.exe"

# Shipped inside electron-builder rather than the Windows SDK, so this works
# without a separate SDK install.
$signtool = Join-Path $repoRoot "desktop\node_modules\@electron\windows-sign\vendor\signtool.exe"

foreach ($p in @($pfx, $target, $signtool)) {
    if (-not (Test-Path $p)) { throw "Missing: $p" }
}

# Staleness guard. electron-builder copies dist/ in verbatim and cannot tell
# the Python source moved on, so a bundle built before run.py grew a flag
# still packages cleanly - and then dies at runtime when main.js passes it.
# That has now happened twice (--port, then --app-version), and the symptom
# both times was a window that never appears, which points at Electron
# rather than at a stale build. Assert the contract here instead.
$requiredFlags = @("--port", "--no-browser", "--app-version")
$usage = (& $target --help 2>&1) -join "`n"
$missing = $requiredFlags | Where-Object { $usage -notmatch [regex]::Escape($_) }
if ($missing) {
    throw ("The bundled backend does not accept: {0}`n" -f ($missing -join ", ")) +
          "It predates the current run.py. Rebuild it first:`n" +
          "  cd backend; pyinstaller pyinstaller/app.spec"
}
Write-Host "Flag check passed: $($requiredFlags -join ', ')"

Write-Host "Signing $target"
& $signtool sign /fd SHA256 /td SHA256 /tr $TimestampUrl /f $pfx /p $Password $target
if ($LASTEXITCODE -ne 0) { throw "signtool failed with exit code $LASTEXITCODE" }

# /pa = use the Authenticode policy. Exits non-zero until the signing cert's
# root is trusted on this machine, which is expected for a self-signed cert
# before running trust-cert.ps1.
& $signtool verify /pa $target
if ($LASTEXITCODE -eq 0) {
    Write-Host "Verified against a trusted root."
} else {
    Write-Host "Signed, but the root is not trusted on this machine yet - run .\scripts\trust-cert.ps1"
}
