# Project 12 CP11-CP14 offline validation (Windows PowerShell 5.1 compatible).
# NEVER calls AWS, terraform apply or model promotion.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project 12 .venv is missing' }

Write-Host '=== Full Project 12 pytest suite ==='
& $python -m pytest -q --disable-warnings -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw 'pytest failed' }

Write-Host '=== CP11 AWS prerequisites ==='
& $python .\CP11_PREFLIGHT.py
if ($LASTEXITCODE -ne 0) { throw 'CP11 preflight failed' }

Write-Host '=== CP12 observability ==='
& $python .\CP12_OBSERVABILITY_REPORT.py
if ($LASTEXITCODE -ne 0) { throw 'CP12 observability failed' }

Write-Host '=== CP13 synthetic drift ==='
& $python .\CP13_DRIFT_REPORT.py
if ($LASTEXITCODE -ne 0) { throw 'CP13 drift failed' }

Write-Host '=== CP14 model release screening ==='
& $python .\CP14_RELEASE_REVIEW.py
if ($LASTEXITCODE -ne 0) { throw 'CP14 release screening failed' }

Write-Host '=== CP14 rollback planning ==='
& $python .\CP14_ROLLBACK_PLAN.py
if ($LASTEXITCODE -ne 0) { throw 'CP14 rollback planning failed' }

Write-Host '=== Terraform format check ==='
& terraform '-chdir=.\infrastructure\terraform' fmt -check
if ($LASTEXITCODE -ne 0) { throw 'Terraform format failed' }

Write-Host '=== Terraform validation ==='
& terraform '-chdir=.\infrastructure\terraform' validate
if ($LASTEXITCODE -ne 0) { throw 'Terraform validation failed' }

Write-Host 'RESULT: CP11-CP14 OFFLINE CHECKS PASSED - NO AWS DEPLOYMENT OR MODEL PROMOTION'
