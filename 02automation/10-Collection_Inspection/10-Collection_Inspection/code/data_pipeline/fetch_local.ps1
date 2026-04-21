Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\common.ps1"

function Invoke-LocalFetch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,
        [string]$SqlFile,
        [string]$Sql,
        [string]$Endpoint = "https://fc-maxcte-query-azbabkaceu.ap-southeast-1.fcapp.run",
        [string]$AuthToken
    )

    $sqlText = Get-SqlText -SqlFile $SqlFile -SqlInline $Sql
    $sqlName = if ($SqlFile) { [System.IO.Path]::GetFileName($SqlFile) } else { "inline.sql" }
    $runPaths = New-RunPaths -ProjectRoot $ProjectRoot -Source "local"

    $headers = @{}
    if ($AuthToken -and $AuthToken.Trim().Length -gt 0) {
        $headers["Authorization"] = "Bearer $AuthToken"
    }

    $resp = Invoke-SqlEndpoint -Endpoint $Endpoint -Sql $sqlText -Headers $headers
    return Save-RunArtifacts -Source "local" -Sql $sqlText -SqlName $sqlName -RunPaths $runPaths -Response $resp -Endpoint $Endpoint
}
