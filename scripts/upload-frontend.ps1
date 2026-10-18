#Requires -Version 7.0

[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateNotNullOrEmpty()]
    [string] $FtpHost = 'ftp.c9ry3m6by.service.one',

    [ValidateNotNullOrEmpty()]
    [string] $RemotePath = 'webroots/r1058728',

    [PSCredential] $Credential,

    [switch] $SkipBuild
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
Import-Module (Join-Path $PSScriptRoot 'ftps.psm1') -Force
Get-FtpsDestination -FtpHost $FtpHost -RemotePath $RemotePath | Out-Null

$frontendPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'webroot' 'kk67-frontend'
if (-not (Test-Path -LiteralPath (Join-Path $frontendPath 'package.json') -PathType Leaf)) {
    throw "Frontend not found at $frontendPath. Initialize the frontend submodule first."
}

if (-not $SkipBuild) {
    $yarn = Get-Command yarn -ErrorAction Stop
    Push-Location -LiteralPath $frontendPath
    try {
        & $yarn build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend build failed (exit code $LASTEXITCODE). Nothing was uploaded."
        }
    }
    finally {
        Pop-Location
    }
}

$buildPath = Join-Path $frontendPath 'dist'
$indexPath = Join-Path $buildPath 'index.html'
if (-not (Test-Path -LiteralPath $indexPath -PathType Leaf)) {
    throw "No frontend build found at $indexPath. Run without -SkipBuild to build it first."
}

$uploadParameters = @{
    SourcePath = $buildPath
    FtpHost = $FtpHost
    RemotePath = $RemotePath
    Credential = $Credential
    PublishLast = 'index.html'
    WhatIf = $WhatIfPreference
}
if ($PSBoundParameters.ContainsKey('Confirm')) {
    $uploadParameters.Confirm = $PSBoundParameters.Confirm
}

Send-FtpsDirectory @uploadParameters
