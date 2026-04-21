Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-SqlText {
    param(
        [string]$SqlFile,
        [string]$SqlInline
    )

    if ($SqlInline -and $SqlInline.Trim().Length -gt 0) {
        return $SqlInline.Trim()
    }

    if (-not $SqlFile -or -not (Test-Path -LiteralPath $SqlFile)) {
        throw "SQL source is missing. Provide -Sql or a valid -SqlFile."
    }

    $sql = (Get-Content -LiteralPath $SqlFile -Raw).Trim()
    if (-not $sql) {
        throw "SQL file is empty: $SqlFile"
    }
    return $sql
}

function New-RunPaths {
    param(
        [string]$ProjectRoot,
        [string]$Source
    )

    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $base = Join-Path $ProjectRoot "result\data_pipeline"
    $runDir = Join-Path $base "$ts`_$Source"
    $rawDir = Join-Path $runDir "raw"
    $normDir = Join-Path $runDir "normalized"

    New-Item -ItemType Directory -Force -Path $rawDir | Out-Null
    New-Item -ItemType Directory -Force -Path $normDir | Out-Null

    return @{
        Timestamp = $ts
        RunDir = $runDir
        RawDir = $rawDir
        NormalizedDir = $normDir
    }
}

function Invoke-SqlEndpoint {
    param(
        [string]$Endpoint,
        [string]$Sql,
        [hashtable]$Headers
    )

    if (-not $Endpoint -or $Endpoint.Trim().Length -eq 0) {
        throw "Endpoint is required."
    }

    $body = @{ sql = $Sql } | ConvertTo-Json -Compress
    if ($Headers -and $Headers.Count -gt 0) {
        return Invoke-RestMethod -Uri $Endpoint -Method Post -ContentType "application/json" -Headers $Headers -Body $body
    }
    return Invoke-RestMethod -Uri $Endpoint -Method Post -ContentType "application/json" -Body $body
}

function Save-RunArtifacts {
    param(
        [string]$Source,
        [string]$Sql,
        [string]$SqlName,
        [hashtable]$RunPaths,
        [object]$Response,
        [string]$Endpoint
    )

    $rawPath = Join-Path $RunPaths.RawDir "response.json"
    $metaPath = Join-Path $RunPaths.RunDir "meta.json"
    $csvPath = Join-Path $RunPaths.NormalizedDir "rows.csv"

    $json = $Response | ConvertTo-Json -Depth 100
    Set-Content -LiteralPath $rawPath -Value $json -Encoding UTF8

    $rows = $null
    if ($Response -is [System.Collections.IEnumerable] -and -not ($Response -is [string])) {
        $rows = $Response
    } elseif ($Response.PSObject.Properties.Name -contains "data" -and $Response.data -is [System.Collections.IEnumerable]) {
        $rows = $Response.data
    } elseif ($Response.PSObject.Properties.Name -contains "result" -and $Response.result -is [System.Collections.IEnumerable]) {
        $rows = $Response.result
    }

    $rowCount = 0
    if ($rows) {
        $rows | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8
        try {
            $rowCount = @($rows).Count
        } catch {
            $rowCount = 0
        }
    }

    $meta = [ordered]@{
        timestamp = $RunPaths.Timestamp
        source = $Source
        endpoint = $Endpoint
        sql_name = $SqlName
        sql = $Sql
        raw_response_path = $rawPath
        normalized_csv_path = if (Test-Path -LiteralPath $csvPath) { $csvPath } else { $null }
        row_count = $rowCount
    }
    $meta | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $metaPath -Encoding UTF8

    return [ordered]@{
        RawPath = $rawPath
        MetaPath = $metaPath
        CsvPath = if (Test-Path -LiteralPath $csvPath) { $csvPath } else { $null }
        RowCount = $rowCount
        RunDir = $RunPaths.RunDir
    }
}
