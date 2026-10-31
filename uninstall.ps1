$ErrorActionPreference = 'Stop'
$root=Join-Path $env:LOCALAPPDATA 'MediaCraft'
$marker=Join-Path $root '.mediacraft-install'
if (!(Test-Path $marker) -or (Get-Content $marker -Raw).Trim() -ne 'mediacraft-managed-install-v1') { throw 'Refusing to remove an unrecognized installation.' }
$bin=Join-Path $root 'bin'
$userPath=[Environment]::GetEnvironmentVariable('Path','User')
$remaining=(($userPath -split ';') | Where-Object { $_ -and $_ -ne $bin }) -join ';'
[Environment]::SetEnvironmentVariable('Path',$remaining,'User')
Remove-Item -LiteralPath $root -Recurse -Force
Write-Host 'MediaCraft removed. Your original and generated media files were not touched.'
