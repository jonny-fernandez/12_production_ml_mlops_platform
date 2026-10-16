# Project 12 CP10 - Offline Kubernetes and regression validation.
# Read-only: no kubectl apply, no AWS, no Docker build, no model promotion.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Project 12 .venv Python not found' }
Write-Host 'CP10 - Running all Project 12 regression tests'
& $python -m pytest -p no:cacheprovider -q --disable-warnings
if ($LASTEXITCODE -ne 0) { throw 'Regression suite failed' }
Write-Host 'CP10 - Verifying Kubernetes manifests offline'
& $python '.\CP10_validate_kubernetes.py'
if ($LASTEXITCODE -ne 0) { throw 'Kubernetes offline validation failed' }
$kubectl = Get-Command kubectl -ErrorAction SilentlyContinue
if ($kubectl) {
  Write-Host 'CP10 - kubectl kustomize: checking rendered manifests (offline)'
  $output = & kubectl kustomize '.\infrastructure\kubernetes' 2>&1
  if ($LASTEXITCODE -ne 0) { $output | Out-Host; throw 'kubectl kustomize failed' }
  if (-not ($output | Select-String 'kind: Deployment')) { throw 'No Deployment in rendered manifests' }
  Write-Host 'CP10 - kubectl Kustomize rendering: PASS'
} else {
  Write-Host 'CP10 - kubectl is not installed: optional Kustomize check skipped'
}
Write-Host 'RESULT: CP10 OFFLINE VALIDATION PASSED - KUBERNETES DEPLOYMENT DISABLED' -ForegroundColor Green
