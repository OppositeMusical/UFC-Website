<#
.SYNOPSIS
    Creates the self-signed code-signing certificate used for local builds.

.DESCRIPTION
    desktop/certs/ is gitignored (it holds a private key), so a fresh clone
    has to regenerate this. Run once per machine.

    What this buys you: signed binaries, and - on machines where you also
    install the .cer into Trusted Root - no "Unknown Publisher" prompt.

    What it does NOT buy you: SmartScreen clearance for the public. That
    reputation is tied to a publicly-trusted certificate with download
    history behind it; a self-signed cert has neither, so anyone
    downloading from the internet still sees "Windows protected your PC".
    Only a purchased (ideally EV) certificate changes that.

.EXAMPLE
    .\scripts\new-signing-cert.ps1 -Password "choose-something"
#>
[CmdletBinding()]
param(
    [string]$Subject = "CN=OppositeMusical, O=UFC Predictor, C=US",
    [Parameter(Mandatory = $true)][string]$Password,
    [int]$Years = 3
)

$ErrorActionPreference = "Stop"

$certDir = Join-Path $PSScriptRoot "..\certs"
if (-not (Test-Path $certDir)) { New-Item -ItemType Directory -Path $certDir | Out-Null }
$certDir = (Resolve-Path $certDir).Path

$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject $Subject `
    -FriendlyName "UFC Predictor Code Signing (self-signed)" `
    -KeyAlgorithm RSA `
    -KeyLength 3072 `
    -HashAlgorithm SHA256 `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyUsage DigitalSignature `
    -KeyExportPolicy Exportable `
    -NotAfter (Get-Date).AddYears($Years)

$secure = ConvertTo-SecureString -String $Password -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath (Join-Path $certDir "code-signing.pfx") -Password $secure | Out-Null
Export-Certificate  -Cert $cert -FilePath (Join-Path $certDir "code-signing.cer") | Out-Null

Write-Host "Created $($cert.Subject)"
Write-Host "  Thumbprint : $($cert.Thumbprint)"
Write-Host "  Algorithm  : $($cert.SignatureAlgorithm.FriendlyName)"
Write-Host "  Expires    : $($cert.NotAfter)"
Write-Host "  PFX        : $certDir\code-signing.pfx   (PRIVATE KEY - never commit)"
Write-Host "  CER        : $certDir\code-signing.cer   (public, safe to share)"
Write-Host ""
Write-Host "Next:  `$env:CSC_KEY_PASSWORD = '<password>' ; npm run dist"
Write-Host "Then, to trust it on a test machine:  .\scripts\trust-cert.ps1"
