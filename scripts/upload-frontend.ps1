#Requires -Version 7.0

[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateNotNullOrEmpty()]
    [string] $FtpHost = 'ftp.c9ry3m6by.service.one',

    [ValidateNotNullOrEmpty()]
    [string] $RemotePath = 'c9ry3m6by_kk67ctcg/webroots/r1058728',

    [PSCredential] $Credential,

    [switch] $SkipBuild
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$OutputEncoding = [Text.UTF8Encoding]::new($false)

if ([Uri]::CheckHostName($FtpHost) -notin @([UriHostNameType]::Dns, [UriHostNameType]::IPv4)) {
    throw 'FtpHost must be a hostname or IPv4 address, without a scheme, port, or path.'
}

$remoteSegments = $RemotePath.Trim().Trim('/').Split('/')
if ($RemotePath -match '[\\\r\n]' -or $remoteSegments -contains '' -or
    $remoteSegments -contains '.' -or $remoteSegments -contains '..') {
    throw 'RemotePath must be a nonempty FTP directory path without backslashes or dot segments.'
}
$encodedRemotePath = ($remoteSegments | ForEach-Object { [Uri]::EscapeDataString($_) }) -join '/'
$destination = "ftp://$FtpHost/$encodedRemotePath/"

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

$buildItems = @(Get-Item -LiteralPath $buildPath) +
    @(Get-ChildItem -LiteralPath $buildPath -Recurse -Force)
if (@($buildItems | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) {
    throw 'The build contains symbolic links or junctions. Refusing to upload files outside the build.'
}

# Publish the entry point only after its assets have uploaded successfully.
$files = @($buildItems | Where-Object { -not $_.PSIsContainer } |
    Sort-Object @{ Expression = { $_.FullName -eq $indexPath } }, FullName)

Write-Host "Source: $buildPath"
if (-not $PSCmdlet.ShouldProcess($destination,
    "Upload $($files.Count) frontend files using explicit FTPS (overwrite matching files; never delete)")) {
    return
}

$curl = Get-Command curl.exe -ErrorAction Stop
$envFile = Join-Path (Split-Path -Parent $PSScriptRoot) '.env'
if ($null -eq $Credential -and (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    $node = Get-Command node -ErrorAction Stop
    $readEnv = @'
const { readFileSync } = require('node:fs');
const { parseEnv } = require('node:util');
if (typeof parseEnv !== 'function') {
    console.error('Reading saved FTP credentials requires Node.js 20.12 or newer.');
    process.exit(1);
}
const values = parseEnv(readFileSync(process.argv[1], 'utf8'));
process.stdout.write(JSON.stringify({
    username: values.FTP_USERNAME ?? '',
    password: values.FTP_PASSWORD ?? ''
}));
'@
    $savedCredentialJson = & $node --input-type=commonjs -e $readEnv $envFile
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not read FTP credentials from the root .env. Nothing was uploaded.'
    }
    $savedCredential = ConvertFrom-Json -InputObject $savedCredentialJson
    $hasUsername = -not [string]::IsNullOrEmpty($savedCredential.username)
    $hasPassword = -not [string]::IsNullOrEmpty($savedCredential.password)
    if ($hasUsername -ne $hasPassword) {
        throw 'Set both FTP_USERNAME and FTP_PASSWORD in the root .env, or leave both empty to use the credential prompt.'
    }
    if ($hasUsername) {
        $securePassword = ConvertTo-SecureString $savedCredential.password -AsPlainText -Force
        $Credential = [PSCredential]::new($savedCredential.username, $securePassword)
    }
}
if ($null -eq $Credential) {
    $Credential = Get-Credential -Message "FTP credentials for $FtpHost"
}
if ($null -eq $Credential -or [string]::IsNullOrWhiteSpace($Credential.UserName) -or
    $Credential.UserName -match '[:\r\n]') {
    throw 'An FTP credential with a nonempty username without colons or newlines is required.'
}

# Feed credentials through stdin, not process arguments or a temporary file.
$userPassword = '{0}:{1}' -f $Credential.UserName, $Credential.GetNetworkCredential().Password
$escapedCredential = $userPassword.Replace('\', '\\').Replace('"', '\"')
$escapedCredential = $escapedCredential.Replace("`r", '\r').Replace("`n", '\n')
$escapedCredential = $escapedCredential.Replace("`t", '\t').Replace("`v", '\v')
$curlConfig = 'user = "' + $escapedCredential + '"'
$curlOptions = @(
    '--disable', '--config', '-', '--silent', '--show-error',
    '--ssl-reqd', '--ftp-ssl-auth', 'TLS', '--proto', '=ftp', '--globoff',
    '--connect-timeout', '15', '--max-time', '1800'
)

function Invoke-Ftp {
    param(
        [string] $Operation,
        [string[]] $CurlArguments
    )

    $curlConfig | & $curl @curlOptions @CurlArguments | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed (curl exit code $LASTEXITCODE). Deployment stopped; uploaded files are not rolled back."
    }
}

# Check the existing destination before allowing creation of asset subdirectories.
Invoke-Ftp -Operation 'FTP login or destination check' -CurlArguments @(
    '--list-only', '--url', $destination
)

foreach ($file in $files) {
    $relativePath = [IO.Path]::GetRelativePath($buildPath, $file.FullName)
    $encodedPath = ($relativePath.Split([IO.Path]::DirectorySeparatorChar) |
        ForEach-Object { [Uri]::EscapeDataString($_) }) -join '/'
    Write-Host "Uploading $relativePath"
    Invoke-Ftp -Operation "Upload of $relativePath" -CurlArguments @(
        '--ftp-create-dirs', '--upload-file', $file.FullName,
        '--url', "$destination$encodedPath"
    )
}

Write-Host "Upload complete: $($files.Count) frontend files. No remote files were deleted."
