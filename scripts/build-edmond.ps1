[CmdletBinding()]
param([string]$Compiler = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'generate-edmond-assets.py')
if ($LASTEXITCODE -ne 0) { throw 'Edmond asset generation failed.' }
$dist = Join-Path $projectRoot 'dist'
$work = Join-Path $projectRoot 'build\edmond-pyinstaller'
foreach ($target in @($dist,$work,(Join-Path $dist 'Edmond'))) {
    if ((Test-Path -LiteralPath $target) -and ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Refusing a redirected build directory: $target"
    }
}
$originalPath = $env:PATH
$originalPythonPath = $env:PYTHONPATH
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$(Split-Path -Parent $python)"
    $env:PYTHONPATH = $null
    & $python -m PyInstaller --noconfirm --distpath $dist --workpath $work (Join-Path $projectRoot 'packaging\Edmond.spec')
    if ($LASTEXITCODE -ne 0) { throw 'Edmond build failed.' }
} finally {
    $env:PATH = $originalPath
    $env:PYTHONPATH = $originalPythonPath
}
& $python -c 'import runpy; from pathlib import Path; m=runpy.run_path("scripts/collect-licenses.py"); m["collect"](Path("dist/Edmond"),app="Edmond")'
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
Copy-Item -LiteralPath (Join-Path $projectRoot 'docs\EDMOND.md') -Destination (Join-Path $dist 'Edmond\README.md')
$noticePath = Join-Path $dist 'Edmond\THIRD_PARTY_NOTICES.md'
$notice = (Get-Content -LiteralPath $noticePath -Raw).Replace('Project Vega','Project Edmond').Replace('Vega','Edmond').Replace('build-windows.ps1','build-edmond.ps1')
Set-Content -LiteralPath $noticePath -Value $notice -Encoding utf8
Copy-Item -LiteralPath (Join-Path $projectRoot 'src\edmond\resources\Project Edmond.xmm') -Destination (Join-Path $dist 'Edmond\Project Edmond.xmm')
Set-Content -LiteralPath (Join-Path $dist 'Edmond\edmond-identity.txt') -Value 'ProjectEdmond.Edmond' -Encoding ascii
& $python (Join-Path $PSScriptRoot 'verify-distribution.py') --app Edmond --write
if ($LASTEXITCODE -ne 0) { throw 'Edmond distribution validation failed.' }
if (-not $Compiler) { $Compiler = Join-Path $projectRoot 'build\tools\inno\ISCC.exe' }
if (-not (Test-Path -LiteralPath $Compiler -PathType Leaf)) { throw 'Supply -Compiler with the path to Inno Setup 6 ISCC.exe.' }
$version = (Get-Item -LiteralPath (Join-Path $dist 'Edmond\Edmond.exe')).VersionInfo.ProductVersion
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw 'Packaged Edmond has invalid version metadata.' }
& $Compiler "/DAppVersion=$version" (Join-Path $projectRoot 'packaging\Edmond.iss')
if ($LASTEXITCODE -ne 0) { throw 'Edmond installer compilation failed.' }
Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $dist 'installer\Edmond-Setup.exe')
