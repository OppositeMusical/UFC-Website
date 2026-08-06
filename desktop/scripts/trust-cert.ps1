<#
.SYNOPSIS
    Installs the self-signed code-signing certificate into Trusted Root.

.DESCRIPTION
    Run this on a test machine to make Windows accept the signature, which
    turns the UAC prompt's "Unknown Publisher" into the certificate's
    publisher name.

    READ THIS BEFORE RUNNING IT ELSEWHERE
    -------------------------------------
    A root certificate can vouch for ANY software, not just this app. Adding
    one means that machine will trust anything signed with the matching
    private key (desktop/certs/code-signing.pfx). If that file leaks, whoever
    holds it can sign malware that these machines run without a warning.

    That is why Windows normally shows a confirmation dialog here. Only
    install this on machines you control, and treat the .pfx like a password.

    It also does NOT clear SmartScreen for the public - see
    new-signing-cert.ps1 for why.

.PARAMETER Scope
    CurrentUser (default, no admin needed) or LocalMachine (all users,
    requires an elevated session).

.EXAMPLE
    .\scripts\trust-cert.ps1
    .\scripts\trust-cert.ps1 -Scope LocalMachine   # from an admin shell

.EXAMPLE
    # Undo:
    .\scripts\trust-cert.ps1 -Remove
#>
[CmdletBinding()]
param(
    [ValidateSet("CurrentUser", "LocalMachine")][string]$Scope = "CurrentUser",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$cerPath = Join-Path $PSScriptRoot "..\certs\code-signing.cer"
if (-not (Test-Path $cerPath)) { throw "No certificate at $cerPath - run new-signing-cert.ps1 first." }

$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2((Resolve-Path $cerPath).Path)

if ($Scope -eq "LocalMachine") {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "LocalMachine scope needs an elevated PowerShell session."
    }
}

$store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", $Scope)
$store.Open("ReadWrite")
try {
    if ($Remove) {
        $existing = $store.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
        if ($existing) {
            $store.Remove($cert)
            Write-Host "Removed $($cert.Subject) from ${Scope}\Root"
        } else {
            Write-Host "Not present in ${Scope}\Root - nothing to do."
        }
    } else {
        $store.Add($cert)
        Write-Host "Trusted $($cert.Subject)"
        Write-Host "  Thumbprint : $($cert.Thumbprint)"
        Write-Host "  Store      : ${Scope}\Root"
        Write-Host ""
        Write-Host "Undo with:  .\scripts\trust-cert.ps1 -Scope $Scope -Remove"
    }
} finally {
    $store.Close()
}
