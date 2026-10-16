# Project 12: repair cross-platform Terraform lock and validate local CI prerequisites.
# Safe: no AWS credentials, terraform plan/apply, model promotion, git add/commit/push.
# Run from any PowerShell directory: powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\CP15_REPAIR_AND_VALIDATE.ps1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = $PSScriptRoot
$tf = Join-Path $root 'infrastructure\terraform'
$lock = Join-Path $tf '.terraform.lock.hcl'
$ci = Join-Path $root '.github\workflows\ci.yml'
$python = Join-Path $root '.venv\Scripts\python.exe'

function Check-Exit([string]$label) {
    if ($LASTEXITCODE -ne 0) { throw "$label failed (exit code $LASTEXITCODE)." }
}

if (-not (Test-Path $tf -PathType Container)) { throw 'Terraform project directory not found.' }
if (-not (Test-Path $lock -PathType Leaf)) { throw 'Terraform dependency lockfile not found.' }
if (-not (Test-Path $ci -PathType Leaf)) { throw 'CI workflow missing.' }
if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) { throw 'terraform command not in PATH.' }
if (-not (Test-Path $python -PathType Leaf)) { throw 'Project Python virtual environment not found.' }

$ciText = Get-Content -LiteralPath $ci -Raw
if ($ciText -notmatch 'httpx2==2\.13\.1' -or $ciText -notmatch 'python-docx==1\.2\.0') {
    throw 'CI workflow was not replaced with the new file.'
}

Write-Host 'CP15 CI FIX - Terraform official multi-platform provider hashes' -ForegroundColor Cyan
# Query the origin registry (not a mirror). Terraform verifies package/signature metadata.
# This adds a linux_amd64 h1 hash alongside the existing Windows hash.
& terraform "-chdir=$tf" providers lock '-platform=windows_amd64' '-platform=linux_amd64' 'registry.terraform.io/hashicorp/aws'
Check-Exit 'terraform providers lock'

# The published lock already includes the signed official ZIP hashes. Do not remove them.
$lockText = Get-Content -LiteralPath $lock -Raw
if (($lockText -split "`n" | Where-Object { $_ -match '^\s*"h1:' }).Count -lt 2) {
    throw 'Lockfile does not contain at least two platform h1 hashes; do not commit.'
}
# Official AWS provider 5.100.0 linux amd64 / windows amd64 package checksums.
if ($lockText -notmatch 'zh:1589a2266af699cbd5d80737a0fe02e54ec9cf2ca54e7e00ac51c7359056f274') {
    throw 'Linux AWS 5.100.0 official checksum missing; do not commit.'
}
if ($lockText -notmatch 'zh:9f8b909d3ec50ade83c8062290378b1ec553edef6a447c56dadc01a99f4eaa93') {
    throw 'Windows AWS 5.100.0 official checksum missing; do not commit.'
}

Write-Host 'CP15 CI FIX - Read-only Terraform initialization and validation' -ForegroundColor Cyan
& terraform "-chdir=$tf" fmt -check -recursive
Check-Exit 'terraform fmt -check'
& terraform "-chdir=$tf" init '-backend=false' '-input=false' '-lockfile=readonly'
Check-Exit 'terraform init -lockfile=readonly'
& terraform "-chdir=$tf" validate
Check-Exit 'terraform validate'

Write-Host 'CP15 CI FIX - Full local Python regression suite' -ForegroundColor Cyan
& $python -m pytest -o 'addopts=' -q --disable-warnings -p 'no:cacheprovider'
Check-Exit 'pytest'

Write-Host 'RESULT: CP15 CI FIX LOCAL VALIDATION PASSED - REVIEW AND COMMIT LOCKFILE' -ForegroundColor Green
Write-Host 'No files staged, committed, pushed, deployed, or approved.'
