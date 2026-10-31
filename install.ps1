# Windows: Right-click PowerShell -> Run, then: powershell -ExecutionPolicy Bypass -File .\install.ps1
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:LOCALAPPDATA 'MediaCraft'
$venv = Join-Path $root 'venv'
$bin = Join-Path $root 'bin'
$marker = Join-Path $root '.mediacraft-install'
if ((Test-Path $root) -and (!(Test-Path $marker) -or (Get-Content $marker -Raw).Trim() -ne 'mediacraft-managed-install-v1')) { throw "Unrecognized directory: $root" }
$python = $null
foreach ($candidate in @(@('py','-3.12'),@('py','-3.11'),@('py','-3.13'),@('python'))) {
  try { $v = & $candidate[0] @($candidate | Select-Object -Skip 1) -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,14)' 2>$null; if ($LASTEXITCODE -eq 0) { $python=$candidate; break } } catch {}
}
if (!$python) { throw 'Install Python 3.11-3.13 from python.org (enable Add Python to PATH), then retry.' }
New-Item -ItemType Directory -Force $root,$bin | Out-Null
Set-Content -Path $marker -Value 'mediacraft-managed-install-v1'
Write-Host '[1/3] Creating private environment...'
if (!(Test-Path (Join-Path $venv 'Scripts\python.exe'))) { & $python[0] @($python | Select-Object -Skip 1) -m venv $venv; if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' } }
$exe = Join-Path $venv 'Scripts\python.exe'
Write-Host '[2/3] Installing core tools (AI models install only when needed)...'
& $exe -m pip install --no-cache-dir --disable-pip-version-check $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed' }
$cmd = Join-Path $bin 'mediacraft.cmd'
@'
@echo off
set "MEDIACRAFT_HOME=%LOCALAPPDATA%\MediaCraft"
set "REMBG_HOME=%MEDIACRAFT_HOME%\models\rembg"
set "U2NET_HOME=%REMBG_HOME%"
set "TORCH_HOME=%MEDIACRAFT_HOME%\models\torch"
set "HF_HOME=%MEDIACRAFT_HOME%\models\huggingface"
set "XDG_CACHE_HOME=%MEDIACRAFT_HOME%\cache"
set "PIP_NO_CACHE_DIR=1"
"%MEDIACRAFT_HOME%\venv\Scripts\python.exe" -m mediacraft %*
'@ | Set-Content -Path $cmd -Encoding ascii
Copy-Item (Join-Path $PSScriptRoot 'uninstall.ps1') (Join-Path $root 'uninstall.ps1') -Force
Write-Host '[3/3] Adding MediaCraft to user PATH...'
$userPath=[Environment]::GetEnvironmentVariable('Path','User')
if (($userPath -split ';') -notcontains $bin) { [Environment]::SetEnvironmentVariable('Path', (($userPath.TrimEnd(';') + ';' + $bin).TrimStart(';')), 'User') }
$env:Path += ";$bin"
& $cmd --version
Write-Host 'Done. Open a NEW terminal and run: mediacraft splitvideo clip.mp4'
