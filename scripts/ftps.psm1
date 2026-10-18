#Requires -Version 7.0

function Get-FtpsDestination {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string] $FtpHost,

        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string] $RemotePath
    )

    if ([Uri]::CheckHostName($FtpHost) -notin @([UriHostNameType]::Dns, [UriHostNameType]::IPv4)) {
        throw 'FtpHost must be a hostname or IPv4 address, without a scheme, port, or path.'
    }

    $remoteSegments = $RemotePath.Trim().Trim('/').Split('/')
    if ($RemotePath -match '[\\\r\n]' -or $remoteSegments -contains '' -or
        $remoteSegments -contains '.' -or $remoteSegments -contains '..') {
        throw 'RemotePath must be a nonempty FTP directory path without backslashes or dot segments.'
    }
    $encodedRemotePath = ($remoteSegments | ForEach-Object { [Uri]::EscapeDataString($_) }) -join '/'
    return "ftp://$FtpHost/$encodedRemotePath/"
}

function Send-FtpsDirectory {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string] $SourcePath,

        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string] $FtpHost,

        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string] $RemotePath,

        [PSCredential] $Credential,

        [string] $PublishLast
    )

    $ErrorActionPreference = 'Stop'
    $PSNativeCommandUseErrorActionPreference = $false
    $OutputEncoding = [Text.UTF8Encoding]::new($false)
    $destination = Get-FtpsDestination -FtpHost $FtpHost -RemotePath $RemotePath

    if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) {
        throw "Upload source directory not found: $SourcePath."
    }
    $source = Get-Item -LiteralPath $SourcePath
    $buildItems = @($source) + @(Get-ChildItem -LiteralPath $SourcePath -Recurse -Force)
    if (@($buildItems | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) {
        throw 'The build contains symbolic links or junctions. Refusing to upload files outside the build.'
    }

    $lastPath = $null
    if (-not [string]::IsNullOrEmpty($PublishLast)) {
        if ($PublishLast -in @('.', '..') -or $PublishLast -match '[\\/\r\n]') {
            throw 'PublishLast must be a filename in the upload source directory.'
        }
        $lastPath = Join-Path $source.FullName $PublishLast
        if (-not (Test-Path -LiteralPath $lastPath -PathType Leaf)) {
            throw "PublishLast file not found: $lastPath."
        }
    }

    # Publish the entry point only after its dependencies have uploaded successfully.
    $files = @($buildItems | Where-Object { -not $_.PSIsContainer } |
        Sort-Object @{ Expression = { $_.FullName -eq $lastPath } }, FullName)
    if ($files.Count -eq 0) {
        throw 'The upload source contains no files. Nothing was uploaded.'
    }

    Write-Host "Source: $($source.FullName)"
    if (-not $PSCmdlet.ShouldProcess($destination,
        "Upload $($files.Count) files using explicit FTPS (overwrite matching files; never delete)")) {
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
        '--ssl-reqd', '--proto', '=ftp', '--globoff',
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
        $relativePath = [IO.Path]::GetRelativePath($source.FullName, $file.FullName)
        $encodedPath = ($relativePath.Split([IO.Path]::DirectorySeparatorChar) |
            ForEach-Object { [Uri]::EscapeDataString($_) }) -join '/'
        Write-Host "Uploading $relativePath"
        Invoke-Ftp -Operation "Upload of $relativePath" -CurlArguments @(
            '--ftp-create-dirs', '--upload-file', $file.FullName,
            '--url', "$destination$encodedPath"
        )
    }

    Write-Host "Upload complete: $($files.Count) files. No remote files were deleted."
}

Export-ModuleMember -Function Get-FtpsDestination, Send-FtpsDirectory
