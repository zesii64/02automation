param(
    [ValidateSet("local", "online")]
    [string]$Source = "local",
    [ValidateSet("notebook", "single")]
    [string]$Mode = "notebook",
    [string]$SqlFile = "",
    [string]$Sql = "",
    [string]$LocalEndpoint = "https://fc-maxcte-query-azbabkaceu.ap-southeast-1.fcapp.run",
    [string]$OnlineEndpoint = "",
    [string]$LocalAuthToken = "",
    [string]$OnlineAuthToken = "",
    [string]$NotebookPath = "",
    [string]$OutputXlsx = "",
    [string]$DtStart = "",
    [string]$DtEnd = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\fetch_local.ps1"
. "$PSScriptRoot\fetch_online.ps1"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Test-Ascii {
    param([string]$Text)
    if (-not $Text) { return $true }
    foreach ($ch in $Text.ToCharArray()) {
        if ([int][char]$ch -gt 127) { return $false }
    }
    return $true
}

if ($Mode -eq "notebook") {
    if (-not $NotebookPath -or $NotebookPath.Trim().Length -eq 0) {
        $NotebookPath = Join-Path $projectRoot "material\collection_report\01_Data_Extraction_v3.ipynb"
    }
    if (-not $OutputXlsx -or $OutputXlsx.Trim().Length -eq 0) {
        $OutputXlsx = Join-Path $projectRoot "data\260318_output_automation_v3.xlsx"
    }

    $endpoint = if ($Source -eq "local") { $LocalEndpoint } else { $OnlineEndpoint }
    $token = if ($Source -eq "local") { $LocalAuthToken } else { $OnlineAuthToken }

    if ($Source -eq "online" -and (-not $endpoint -or $endpoint.Trim().Length -eq 0)) {
        $endpoint = $env:ONLINE_SQL_API_URL
    }
    if ($Source -eq "online" -and (-not $token -or $token.Trim().Length -eq 0) -and $env:ONLINE_SQL_API_TOKEN) {
        $token = $env:ONLINE_SQL_API_TOKEN
    }
    if ($token -and -not (Test-Ascii $token)) {
        Write-Warning "OnlineAuthToken contains non-ASCII characters; skip Authorization header to avoid HTTP latin-1 encoding failure."
        $token = ""
    }
    if (-not (Test-Ascii $endpoint)) {
        throw "Online endpoint contains non-ASCII characters. Please use a valid ASCII URL."
    }
    if (-not $endpoint -or $endpoint.Trim().Length -eq 0) {
        throw "Endpoint is required for notebook mode."
    }

    $args = @(
        (Join-Path $PSScriptRoot "execute_notebook_sql.py"),
        "--notebook", $NotebookPath,
        "--endpoint", $endpoint,
        "--output-xlsx", $OutputXlsx
    )
    if ($token -and $token.Trim().Length -gt 0) {
        $args += @("--auth-token", $token)
    }
    if ($DtStart -and $DtStart.Trim().Length -gt 0) {
        $args += @("--dt-start", $DtStart)
    }
    if ($DtEnd -and $DtEnd.Trim().Length -gt 0) {
        $args += @("--dt-end", $DtEnd)
    }

    & python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Notebook pipeline failed with exit code: $LASTEXITCODE"
    }

    Write-Host "Data pipeline completed." -ForegroundColor Green
    Write-Host ("Mode     : {0}" -f $Mode)
    Write-Host ("Source   : {0}" -f $Source)
    Write-Host ("Notebook : {0}" -f $NotebookPath)
    Write-Host ("Output   : {0}" -f $OutputXlsx)
} else {
    if ((-not $SqlFile -or $SqlFile.Trim().Length -eq 0) -and (-not $Sql -or $Sql.Trim().Length -eq 0)) {
        $SqlFile = Join-Path $PSScriptRoot "sql\default.sql"
    }

    if ($Source -eq "local") {
        $result = Invoke-LocalFetch -ProjectRoot $projectRoot -SqlFile $SqlFile -Sql $Sql -Endpoint $LocalEndpoint -AuthToken $LocalAuthToken
    } else {
        $result = Invoke-OnlineFetch -ProjectRoot $projectRoot -SqlFile $SqlFile -Sql $Sql -Endpoint $OnlineEndpoint -AuthToken $OnlineAuthToken
    }

    Write-Host "Data pipeline completed." -ForegroundColor Green
    Write-Host ("Mode     : {0}" -f $Mode)
    Write-Host ("Source   : {0}" -f $Source)
    Write-Host ("Run Dir  : {0}" -f $result.RunDir)
    Write-Host ("Raw JSON : {0}" -f $result.RawPath)
    if ($result.CsvPath) {
        Write-Host ("CSV      : {0}" -f $result.CsvPath)
        Write-Host ("Row Count: {0}" -f $result.RowCount)
    }
    Write-Host ("Meta     : {0}" -f $result.MetaPath)
}
