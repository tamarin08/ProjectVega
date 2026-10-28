<# Compile a GUID-isolated installer; never use the personal Edmond identity. #>
[CmdletBinding()]
param([string]$Compiler = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Compiler) { $Compiler = Join-Path $projectRoot 'build\tools\inno\ISCC.exe' }
$id = [guid]::NewGuid().ToString('N')
$name = "Edmond-Validation-$id"
$testRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot "build\edmond-validation\$id"))
$prefix = [IO.Path]::GetFullPath((Join-Path $projectRoot 'build\edmond-validation')) + '\'
if (-not $testRoot.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $testRoot)) {
    throw 'Unsafe or existing validation destination.'
}
$null = New-Item -ItemType Directory -Path $testRoot
$install = Join-Path $testRoot 'installed'
$preferences = @('ProjectEdmond','ProjectVega') | ForEach-Object { Join-Path $env:LOCALAPPDATA "$_\settings.json" }
function PreferencesSnapshot {
    return (@($preferences | ForEach-Object { if (Test-Path -LiteralPath $_) { (Get-FileHash -LiteralPath $_).Hash } else { 'absent' } }) -join ',')
}
$before = PreferencesSnapshot
$version = (Get-Item -LiteralPath (Join-Path $projectRoot 'dist\Edmond\Edmond.exe')).VersionInfo.ProductVersion
& $Compiler "/DAppVersion=$version" "/DAppIdentity=ProjectEdmond.Validation.$id" "/DShortcutName=$name" "/DInstallFolder=$name" "/DSetupName=$name" "/O$testRoot" (Join-Path $projectRoot 'packaging\Edmond.iss') *> (Join-Path $testRoot 'compile.log')
if ($LASTEXITCODE -ne 0) { throw "Test installer compilation failed. See $testRoot\compile.log" }
$setup = Join-Path $testRoot "$name.exe"
function Run([string]$file,[string[]]$arguments,[switch]$ExpectFailure) {
    $oldPath,$oldPythonPath,$oldPythonHome,$oldQt = $env:PATH,$env:PYTHONPATH,$env:PYTHONHOME,$env:QT_QPA_PLATFORM
    try {
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
        $env:PYTHONPATH = $null
        $env:PYTHONHOME = $null
        $env:QT_QPA_PLATFORM = $null
        $process = Start-Process -FilePath $file -ArgumentList $arguments -WorkingDirectory $testRoot -WindowStyle Hidden -PassThru
    } finally {
        $env:PATH,$env:PYTHONPATH,$env:PYTHONHOME,$env:QT_QPA_PLATFORM = $oldPath,$oldPythonPath,$oldPythonHome,$oldQt
    }
    if (-not $process.WaitForExit(45000)) { throw "Process timed out: $file" }
    if ($ExpectFailure) {
        if ($process.ExitCode -eq 0) { throw 'Unsafe installation unexpectedly succeeded.' }
    } elseif ($process.ExitCode -ne 0) { throw "Process failed: $file (exit $($process.ExitCode))" }
}
$start = Join-Path ([Environment]::GetFolderPath('Programs')) "$name.lnk"
$registry = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ProjectEdmond.Validation.${id}_is1"
foreach ($stage in @('fresh','upgrade')) {
    Run $setup @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',('/DIR="'+$install+'"'),'/TASKS=""',('/LOG="'+(Join-Path $testRoot "$stage-install.log")+'"'))
    if (-not (Test-Path -LiteralPath (Join-Path $install 'Edmond.exe'))) { throw 'Installed executable missing.' }
    if (-not (Test-Path -LiteralPath $start)) { throw 'Start Menu shortcut missing.' }
    if (-not (Test-Path -LiteralPath $registry)) { throw 'Isolated uninstall registration missing.' }
    $report = Join-Path $testRoot "$stage-smoke.json"
    Run (Join-Path $install 'Edmond.exe') @('--smoke-report',('"'+$report+'"'),'--screenshot',('"'+(Join-Path $testRoot "$stage.png")+'"'))
    $smoke = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if ($smoke.app -ne 'Project Edmond' -or $smoke.pads -ne 16 -or $smoke.channel -ne 10 -or $smoke.repeat -or -not $smoke.settings_isolated -or -not $smoke.frozen -or -not $smoke.icon_present -or -not $smoke.gui_initialized) {
        throw 'Installed application smoke test failed.'
    }
    $nativeReport = Join-Path $testRoot "$stage-native-midi.json"
    Run (Join-Path $install 'Edmond.exe') @('--native-midi-report',('"'+$nativeReport+'"'))
    $native = Get-Content -LiteralPath $nativeReport -Raw | ConvertFrom-Json
    if (-not ($native.frozen -and $native.native_available -and $native.connected)) { throw 'Packaged native MIDI setup failed.' }
}
$foreign = Join-Path $testRoot 'foreign'
$null = New-Item -ItemType Directory -Path $foreign
Set-Content -LiteralPath (Join-Path $foreign 'keep.txt') -Value 'unrelated'
Run $setup @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',('/DIR="'+$foreign+'"'),'/TASKS=""',('/LOG="'+(Join-Path $testRoot 'refused-install.log')+'"')) -ExpectFailure
if ((Get-Content -LiteralPath (Join-Path $foreign 'keep.txt') -Raw).Trim() -ne 'unrelated') { throw 'Foreign file changed.' }
$uninstaller = [IO.Path]::GetFullPath((Join-Path $install 'unins000.exe'))
if (-not $uninstaller.StartsWith($testRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe uninstall target.' }
Set-Content -LiteralPath (Join-Path $install 'user-file.txt') -Value 'preserve'
Run $uninstaller @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="'+(Join-Path $testRoot 'uninstall.log')+'"'))
if ((Test-Path -LiteralPath (Join-Path $install 'Edmond.exe')) -or (Test-Path -LiteralPath $start) -or (Test-Path -LiteralPath $registry)) {
    throw 'Uninstall left app files, shortcut or registration.'
}
if (-not (Test-Path -LiteralPath (Join-Path $install 'user-file.txt'))) { throw 'Uninstall removed an unowned file.' }
if ((PreferencesSnapshot) -ne $before) { throw 'Personal Vega or Edmond settings changed.' }
@{ install=$true; upgrade=$true; native_startup=$true; uninstall=$true; foreign_folder_refused=$true;
   personal_preferences_untouched=$true; test_root=$testRoot } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $testRoot 'results.json')
Write-Host "Edmond installer verified: $testRoot"
