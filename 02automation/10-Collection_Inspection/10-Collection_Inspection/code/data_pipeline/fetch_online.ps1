Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\common.ps1"

function Invoke-OnlineFetch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,
        [string]$SqlFile,
        [string]$Sql,
        [string]$Endpoint,
        [string]$AuthToken
    )

    $effectiveEndpoint = $Endpoint
    if (-not $effectiveEndpoint -or $effectiveEndpoint.Trim().Length -eq 0) {
        $effectiveEndpoint = $env:ONLINE_SQL_API_URL
    }
    if (-not $effectiveEndpoint -or $effectiveEndpoint.Trim().Length -eq 0) {
        throw "Online endpoint is missing. Pass -OnlineEndpoint or set ONLINE_SQL_API_URL."
    }

    $sqlText = Get-SqlText -SqlFile $SqlFile -SqlInline $Sql
    $sqlName = if ($SqlFile) { [System.IO.Path]::GetFileName($SqlFile) } else { "inline.sql" }
    $runPaths = New-RunPaths -ProjectRoot $ProjectRoot -Source "online"

    $token = $AuthToken
    if ((-not $token -or $token.Trim().Length -eq 0) -and $env:ONLINE_SQL_API_TOKEN) {
        $token = $env:ONLINE_SQL_API_TOKEN
    }

    $headers = @{}
    if ($token -and $token.Trim().Length -gt 0) {
        $headers["Authorization"] = "Bearer $token"
    }

    $resp = Invoke-SqlEndpoint -Endpoint $effectiveEndpoint -Sql $sqlText -Headers $headers
    return Save-RunArtifacts -Source "online" -Sql $sqlText -SqlName $sqlName -RunPaths $runPaths -Response $resp -Endpoint $effectiveEndpoint
}
