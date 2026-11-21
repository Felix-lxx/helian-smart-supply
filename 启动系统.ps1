param([switch]$SeedDemo)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$backendDir = Join-Path $projectRoot 'code\system'
$frontendDir = Join-Path $projectRoot 'code\Agricultural-product-system'
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$viteEntry = Join-Path $frontendDir 'node_modules\vite\bin\vite.js'
$logDir = Join-Path $projectRoot '.run'
if (!(Test-Path -LiteralPath $pythonExe) -or !(Test-Path -LiteralPath $viteEntry)) {
    throw '缺少本地运行环境，请先安装后端依赖和前端 npm 依赖。'
}
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$env:YOLOv5_AUTOINSTALL = 'false'
$env:YOLO_AUTOINSTALL = 'false'
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $backendDir
try {
    & $pythonExe manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw '数据库迁移失败，请检查本地 MySQL 服务与数据库配置。' }
    if ($SeedDemo) {
        & $pythonExe manage.py seed_workspace
        if ($LASTEXITCODE -ne 0) { throw '演示数据初始化失败。' }
        & $pythonExe manage.py seed_collaboration
        if ($LASTEXITCODE -ne 0) { throw '协同场景初始化失败。' }
    }
} finally { Pop-Location }
if (!(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $pythonExe -ArgumentList '-u','manage.py','runserver','127.0.0.1:8000','--noreload' -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'backend.log') -RedirectStandardError (Join-Path $logDir 'backend.err.log') | Out-Null
} else { Write-Host '8000 已有服务监听，保留该进程。' }
if (!(Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) {
    $nodeExe = (Get-Command node -ErrorAction Stop).Source
    $viteArgs = '"{0}" --host 127.0.0.1 --port 5173 --strictPort' -f $viteEntry
    Start-Process -FilePath $nodeExe -ArgumentList $viteArgs -WorkingDirectory $frontendDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'frontend.log') -RedirectStandardError (Join-Path $logDir 'frontend.err.log') | Out-Null
} else { Write-Host '5173 已有服务监听，保留该进程。' }
Write-Host '禾链智配：http://127.0.0.1:5173'
$runningJobs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($projectRoot) -and $_.CommandLine -match 'manage.py workspace_jobs' }
if (!$runningJobs) {
    Start-Process -FilePath $pythonExe -ArgumentList '-u','manage.py','workspace_jobs','--interval','45' -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'jobs.log') -RedirectStandardError (Join-Path $logDir 'jobs.err.log') | Out-Null
    Write-Host '预留、报价与到货提醒服务已启动。'
}
Write-Host '如端口为其他项目占用，请先核对；启动日志位于 .run。'
