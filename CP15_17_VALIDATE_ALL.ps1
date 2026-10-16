# Project 12 CP15-CP17 OFFLINE validation. Windows PowerShell 5.1 compatible.
# Read-only with respect to AWS, MLflow registry, models and GitHub.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project 12 .venv Python missing' }

Write-Host '=== CP15-CP17 Full regression suite ==='
& $python -m pytest -q --disable-warnings -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw 'Full pytest suite failed' }

Write-Host '=== CP15 CI and release safeguards ==='
& $python .\CP15_RELEASE_GATE.py
if ($LASTEXITCODE -ne 0) { throw 'CP15 safety checks failed' }

Write-Host '=== CP16 offline reliability, security and recovery ==='
& $python .\CP16_RELIABILITY_AUDIT.py
if ($LASTEXITCODE -ne 0) { throw 'CP16 audit failed' }

Write-Host '=== CP16 repository secret and reproducibility audit ==='
& $python .\CP16_REPOSITORY_AUDIT.py
if ($LASTEXITCODE -ne 0) { throw 'CP16 repository audit failed' }

Write-Host '=== CP17 documentation and screenshot readiness ==='
& $python .\CP17_EVIDENCE_AUDIT.py
if ($LASTEXITCODE -ne 0) { throw 'CP17 documentation audit failed' }

Write-Host '=== Terraform format / validation ==='
$terraform = Get-Command terraform -ErrorAction SilentlyContinue
if ($null -eq $terraform) { throw 'Terraform executable not found in PATH' }
& terraform '-chdir=.\infrastructure\terraform' fmt -check -recursive
if ($LASTEXITCODE -ne 0) { throw 'Terraform formatting invalid' }
& terraform '-chdir=.\infrastructure\terraform' init -backend=false -input=false -lockfile=readonly
if ($LASTEXITCODE -ne 0) { throw 'Terraform offline initialization failed' }
& terraform '-chdir=.\infrastructure\terraform' validate
if ($LASTEXITCODE -ne 0) { throw 'Terraform configuration invalid' }

Write-Host 'RESULT: CP15-CP17 OFFLINE VALIDATION PASSED - LIVE AWS RELEASE AND GITHUB PUBLICATION BLOCKED' -ForegroundColor Green
