# One-shot CP9 offline verification. Does NOT run AWS CLI, terraform apply,
# create an approval, push a Docker image or connect to AWS.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Missing Project 12 Python venv' }

function Invoke-Checked([string]$program, [string[]]$arguments) {
    Write-Host "`n>> $program $($arguments -join ' ')"
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" }
}

Invoke-Checked -program $python -arguments @('-m', 'pytest', '-q', '--disable-warnings', '-p', 'no:cacheprovider')
Invoke-Checked -program $python -arguments @('Project12_CP9_stage_cloud_candidate.py')
Invoke-Checked -program $python -arguments @('Project12_CP9_prepare_cloud_image.py')
if (Test-Path 'Project12_CP9_cloud_runtime_dry_run.py') {
    Invoke-Checked -program $python -arguments @('Project12_CP9_cloud_runtime_dry_run.py')
}
Invoke-Checked -program 'terraform' -arguments @('-chdir=.\infrastructure\terraform', 'fmt', '-check')
Invoke-Checked -program 'terraform' -arguments @('-chdir=.\infrastructure\terraform', 'init', '-backend=false', '-input=false', '-lockfile=readonly')
Invoke-Checked -program 'terraform' -arguments @('-chdir=.\infrastructure\terraform', 'validate')

# Verify safety defaults without a cloud provider call.
$files = @(
    'infrastructure\terraform\variables.tf',
    'infrastructure\terraform\public_https_variables.tf',
    'infrastructure\terraform\public_https_ecs_variables.tf',
    'infrastructure\terraform\public_https_dns_variables.tf'
)
foreach ($file in $files) { if (-not (Test-Path $file)) { throw "Missing Terraform file: $file" } }
$content = ($files | ForEach-Object { Get-Content $_ -Raw }) -join "`n"
foreach ($flag in @('enable_aws_resources', 'enable_public_https', 'enable_ecs_deployment', 'cloud_runtime_verified', 'model_release_approved', 'manage_api_dns')) {
    if ($content -notmatch ('(?s)variable\s+"' + $flag + '"\s*\{.*?default\s*=\s*false')) {
        throw "Safety switch missing or not false by default: $flag"
    }
}
Write-Host "`nRESULT: CP9 OFFLINE VALIDATION PASSED - DEPLOYMENT DISABLED" -ForegroundColor Green
