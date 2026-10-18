[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
param(
    [PSCredential] $Credential,
    [string] $AppPath = (Join-Path $PSScriptRoot '..\webroot\kk67-backend-php')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'ftps.psm1') -Force -ErrorAction Stop

function Get-OrdinaryItem {
    param(
        [string] $Path,
        [switch] $Directory
    )

    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ([bool] $Directory -ne ($item -is [IO.DirectoryInfo])) {
        throw "Unexpected file type: '$Path'."
    }

    $ancestor = $item
    while ($null -ne $ancestor) {
        if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Symbolic links and junctions are not allowed: '$($ancestor.FullName)'."
        }
        $ancestor = if ($ancestor -is [IO.DirectoryInfo]) { $ancestor.Parent } else { $ancestor.Directory }
    }

    return $item
}

$appRoot = (Get-OrdinaryItem -Path $AppPath -Directory).FullName
$sourceRoot = (Get-OrdinaryItem -Path (Join-Path $appRoot 'src') -Directory).FullName

foreach ($manifest in @('composer.json', 'composer.lock')) {
    if (Test-Path -LiteralPath (Join-Path $appRoot $manifest)) {
        throw 'This PHP package has no Composer dependencies. Update the explicit production package and its tests before adding Composer.'
    }
}

$runtimeFiles = @(
    @{ Source = (Join-Path $sourceRoot 'index.php'); Destination = 'index.php' },
    @{ Source = (Join-Path $sourceRoot 'loader.php'); Destination = 'loader.php' }
)
foreach ($file in $runtimeFiles) {
    $null = Get-OrdinaryItem -Path $file.Source
}
$null = Get-OrdinaryItem -Path (Join-Path $appRoot 'tests') -Directory
$smokeTest = (Get-OrdinaryItem -Path (Join-Path $appRoot 'tests\smoke.php')).FullName

& php -r 'exit(PHP_VERSION_ID >= 80300 ? 0 : 1);'
if ($LASTEXITCODE -ne 0) {
    throw 'PHP 8.3 or newer is required, matching the application Docker baseline.'
}

$buildRoot = Join-Path $appRoot 'build'
if (Test-Path -LiteralPath $buildRoot) {
    $null = Get-OrdinaryItem -Path $buildRoot -Directory
}
else {
    $null = New-Item -ItemType Directory -Path $buildRoot -WhatIf:$false -Confirm:$false
}
$packageRoot = Join-Path $buildRoot ("ftps-package-" + [guid]::NewGuid().ToString('N'))

try {
    $null = New-Item -ItemType Directory -Path $packageRoot -WhatIf:$false -Confirm:$false
    foreach ($file in $runtimeFiles) {
        $destination = Join-Path $packageRoot $file.Destination
        Copy-Item -LiteralPath $file.Source -Destination $destination -WhatIf:$false -Confirm:$false
        & php -l $destination
        if ($LASTEXITCODE -ne 0) {
            throw "PHP syntax check failed for '$($file.Destination)'."
        }
    }

    & php $smokeTest (Join-Path $packageRoot 'index.php')
    if ($LASTEXITCODE -ne 0) {
        throw 'PHP smoke check failed; nothing has been uploaded.'
    }

    Write-Host 'Packaged 2 PHP runtime files: index.php and loader.php.'
    $upload = @{
        SourcePath = $packageRoot
        FtpHost = 'ftp.c9ry3m6by.service.one'
        RemotePath = 'webroots/r1058768'
        PublishLast = 'index.php'
        WhatIf = [bool] $WhatIfPreference
    }
    if ($PSBoundParameters.ContainsKey('Credential')) {
        $upload.Credential = $Credential
    }
    if ($PSBoundParameters.ContainsKey('Confirm')) {
        $upload.Confirm = $PSBoundParameters.Confirm
    }
    Send-FtpsDirectory @upload
}
finally {
    if (Test-Path -LiteralPath $packageRoot) {
        Remove-Item -LiteralPath $packageRoot -Recurse -Force -WhatIf:$false -Confirm:$false
    }
}
