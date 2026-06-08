<#
.SYNOPSIS
Invoice Validator CLI - Acceptance Test Runner (GBK-safe)

.DESCRIPTION
Run all acceptance tests in default Windows PowerShell/GBK environment.
This script is in plain English to avoid GBK parsing issues.
All Chinese output is handled by Python scripts with encoding protection.

No manual encoding setup required - everything is handled internally.
#>

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Invoice Validator - Acceptance Tests" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Console encoding: $([Console]::OutputEncoding.BodyName)" -ForegroundColor Gray
Write-Host "Working dir: $(Get-Location)" -ForegroundColor Gray
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TestDir = Join-Path $ScriptDir "_acceptance_test"
$ExitCode = 0

try {
    if (Test-Path $TestDir) {
        Remove-Item -Recurse -Force $TestDir | Out-Null
    }
    New-Item -ItemType Directory -Path $TestDir | Out-Null
    Set-Location $TestDir

    Write-Host "[1/4] Preparing test environment..." -ForegroundColor Yellow
    $SampleDir = Join-Path $ScriptDir "samples"
    if (Test-Path $SampleDir) {
        Copy-Item -Recurse $SampleDir ($TestDir + "\samples")
        Write-Host "      Sample data copied" -ForegroundColor Gray
    }

    Write-Host ""
    Write-Host "[2/4] CLI smoke test: invoice-validator init --force" -ForegroundColor Yellow
    $InitOutput = & invoice-validator init --force 2>&1
    $InitExit = $LASTEXITCODE
    $InitOutput | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
    if ($InitExit -ne 0) {
        Write-Host "      FAIL: exit code $InitExit" -ForegroundColor Red
        $ExitCode = 1
    } else {
        Write-Host "      PASS: exit code 0" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "[3/4] Running regression tests (test_regression.py)" -ForegroundColor Yellow
    $RegScript = Join-Path $ScriptDir "test_regression.py"
    $RegOutput = & python $RegScript 2>&1
    $RegExit = $LASTEXITCODE
    $RegOutput | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
    if ($RegExit -ne 0) {
        Write-Host "      FAIL: exit code $RegExit" -ForegroundColor Red
        $ExitCode = 1
    } else {
        Write-Host "      PASS: exit code 0" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "[4/4] Running end-to-end tests (e2e_verify.py)" -ForegroundColor Yellow
    $E2EScript = Join-Path $ScriptDir "e2e_verify.py"
    $E2EOutput = & python $E2EScript 2>&1
    $E2EExit = $LASTEXITCODE
    $E2EOutput | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
    if ($E2EExit -ne 0) {
        Write-Host "      FAIL: exit code $E2EExit" -ForegroundColor Red
        $ExitCode = 1
    } else {
        Write-Host "      PASS: exit code 0" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  TEST SUMMARY" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""

    $CliStatus = if ($InitExit -eq 0) { "PASS" } else { "FAIL" }
    $CliColor = if ($InitExit -eq 0) { "Green" } else { "Red" }
    $RegStatus = if ($RegExit -eq 0) { "PASS" } else { "FAIL" }
    $RegColor = if ($RegExit -eq 0) { "Green" } else { "Red" }
    $E2EStatus = if ($E2EExit -eq 0) { "PASS" } else { "FAIL" }
    $E2EColor = if ($E2EExit -eq 0) { "Green" } else { "Red" }

    Write-Host "  CLI smoke test:  $CliStatus" -ForegroundColor $CliColor
    Write-Host "  Regression:      $RegStatus" -ForegroundColor $RegColor
    Write-Host "  End-to-end:      $E2EStatus" -ForegroundColor $E2EColor
    Write-Host ""

    if ($ExitCode -eq 0) {
        Write-Host "  ALL TESTS PASSED!" -ForegroundColor Green
    } else {
        Write-Host "  SOME TESTS FAILED - see output above" -ForegroundColor Red
    }

} finally {
    Set-Location $ScriptDir
    if (Test-Path $TestDir) {
        Remove-Item -Recurse -Force $TestDir -ErrorAction SilentlyContinue | Out-Null
    }
}

exit $ExitCode
