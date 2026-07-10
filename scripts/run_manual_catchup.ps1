param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$StartDate,

    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$EndDate = $StartDate,

    [ValidateSet(
        'all',
        'incremental-daily',
        'incremental-hourly',
        'incremental-aqi-hourly'
    )]
    [string]$RunType = 'all',

    [switch]$SkipPrepare,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

if ($StartDate -gt $EndDate) {
    throw "StartDate must be before or equal to EndDate."
}

$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$alembic = Join-Path $repoRoot '.venv\Scripts\alembic.exe'
$poetry = Get-Command poetry -ErrorAction SilentlyContinue

if ((Test-Path $python) -and (Test-Path $alembic)) {
    $runner = @{
        Python = $python
        Alembic = $alembic
        UsePoetry = $false
    }
} elseif ($poetry) {
    $runner = @{
        Python = 'poetry'
        Alembic = 'poetry'
        UsePoetry = $true
    }
} else {
    throw "Could not find .venv executables or poetry on PATH. Run 'poetry install' first."
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [string]$Exe,

        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    $display = "$Exe $($Args -join ' ')"
    Write-Host "==> $Label"
    Write-Host "    $display"

    if ($DryRun) {
        return
    }

    & $Exe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

if (-not $SkipPrepare) {
    if ($runner.UsePoetry) {
        Invoke-Step 'Run migrations' $runner.Alembic @('run', 'alembic', 'upgrade', 'head')
        Invoke-Step 'Seed districts' $runner.Python @('run', 'python', 'scripts/seed_provinces.py')
        Invoke-Step 'Seed date dimension' $runner.Python @('run', 'python', 'scripts/seed_dim_date.py')
    } else {
        Invoke-Step 'Run migrations' $runner.Alembic @('upgrade', 'head')
        Invoke-Step 'Seed districts' $runner.Python @('scripts/seed_provinces.py')
        Invoke-Step 'Seed date dimension' $runner.Python @('scripts/seed_dim_date.py')
    }
}

$runTypes = if ($RunType -eq 'all') {
    @('incremental-daily', 'incremental-hourly', 'incremental-aqi-hourly')
} else {
    @($RunType)
}

foreach ($type in $runTypes) {
    if ($runner.UsePoetry) {
        Invoke-Step "Run ETL $type" $runner.Python @(
            'run',
            'vwdp-etl',
            '--run-type',
            $type,
            '--start-date',
            $StartDate,
            '--end-date',
            $EndDate
        )
    } else {
        Invoke-Step "Run ETL $type" $runner.Python @(
            '-c',
            'from src.etl.cli import main; raise SystemExit(main())',
            '--run-type',
            $type,
            '--start-date',
            $StartDate,
            '--end-date',
            $EndDate
        )
    }
}

Write-Host "Manual catch-up completed for $StartDate to $EndDate."
