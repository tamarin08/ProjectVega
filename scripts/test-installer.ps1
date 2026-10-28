<## Compile a separately identified test installer; never target the real Vega install.
    It uses the production script/payload, changing only identity/names/destination.
    Generated setup, logs and reports remain in build/installer-validation for audit.
##>
[CmdletBinding()]
param([string]$Compiler = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Compiler) { $Compiler = Join-Path $projectRoot 'build\tools\inno\ISCC.exe' }
if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Supply -Compiler pointing to ISCC.exe.' }
$exe = Join-Path $projectRoot 'dist\Vega\Vega.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw 'Build Vega first.' }
$id = [guid]::NewGuid().ToString('N')
$name = "Vega-Validation-$id"
$testRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot "build\installer-validation\$id"))
$install = Join-Path $testRoot 'installed'
$expectedPrefix = [IO.Path]::GetFullPath((Join-Path $projectRoot 'build\installer-validation')) + '\'
if (-not $testRoot.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $testRoot)) {
    throw 'Unsafe or existing validation destination.'
}
$null = New-Item -ItemType Directory -Path $testRoot
$version = (Get-Item -LiteralPath $exe).VersionInfo.ProductVersion
& $Compiler "/DAppVersion=$version" "/DAppIdentity=ProjectVega.Validation.$id" "/DShortcutName=$name" "/DInstallFolder=$name" "/DSetupName=$name" "/O$testRoot" (Join-Path $projectRoot 'packaging\Vega.iss')
if ($LASTEXITCODE -ne 0) { throw 'Validation setup compile failed.' }
$setup = Join-Path $testRoot "$name.exe"
$desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) "$name.lnk"
$start = Join-Path ([Environment]::GetFolderPath('Programs')) "$name.lnk"
$userSettings = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'ProjectVega\settings.json'
$beforeSettings = if (Test-Path -LiteralPath $userSettings) { (Get-FileHash -LiteralPath $userSettings).Hash } else { '' }
$isolatedSettings = Join-Path $testRoot 'preferences\settings.json'

function Invoke-ValidationProcess([string]$File, [string[]]$Arguments, [switch]$ExpectFailure) {
    $oldPath, $oldPythonPath, $oldPythonHome = $env:PATH, $env:PYTHONPATH, $env:PYTHONHOME
    $oldAudio, $oldQt = $env:SDL_AUDIODRIVER, $env:QT_QPA_PLATFORM
    try {
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
        $env:PYTHONPATH = $null
        $env:PYTHONHOME = $null
        $env:QT_QPA_PLATFORM = $null
        $env:SDL_AUDIODRIVER = 'dummy'
        $process = Start-Process -FilePath $File -ArgumentList $Arguments -WorkingDirectory $testRoot -WindowStyle Hidden -PassThru
    } finally {
        $env:PATH, $env:PYTHONPATH, $env:PYTHONHOME = $oldPath, $oldPythonPath, $oldPythonHome
        $env:SDL_AUDIODRIVER, $env:QT_QPA_PLATFORM = $oldAudio, $oldQt
    }
    if (-not $process.WaitForExit(45000)) { throw "Validation process timed out: $File (PID $($process.Id))" }
    if ($ExpectFailure) {
        if ($process.ExitCode -eq 0) { throw 'Unsafe installation unexpectedly succeeded.' }
    } elseif ($process.ExitCode -ne 0) { throw "Validation process failed: $File, code $($process.ExitCode)" }
}

foreach ($tasks in @('', 'desktopicon')) {
    $log = Join-Path $testRoot $(if ($tasks) { 'upgrade.log' } else { 'install.log' })
    Invoke-ValidationProcess $setup @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
        ('/DIR="' + $install + '"'), ('/TASKS="' + $tasks + '"'), ('/LOG="' + $log + '"'))
    if (-not (Test-Path -LiteralPath (Join-Path $install 'Vega.exe'))) { throw 'Installed executable missing.' }
    if (-not (Test-Path -LiteralPath $start)) { throw 'Start Menu shortcut missing.' }
    if ([bool](Test-Path -LiteralPath $desktop) -ne [bool]$tasks) { throw 'Desktop task result incorrect.' }
    $shell = New-Object -ComObject WScript.Shell
    if ($shell.CreateShortcut($start).TargetPath -ne (Join-Path $install 'Vega.exe')) { throw 'Incorrect shortcut target.' }
    $uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ProjectVega.Validation.${id}_is1"
    if ((Get-ItemProperty -LiteralPath $uninstallKey).InstallLocation.TrimEnd('\') -ne $install) { throw 'Uninstall registration missing/wrong.' }
    $report = Join-Path $testRoot $(if ($tasks) { 'upgraded-smoke.json' } else { 'fresh-smoke.json' })
    $arguments = @('--smoke-test-report', ('"' + $report + '"'), '--smoke-test-settings', ('"' + $isolatedSettings + '"'), '--device-index', '9999')
    if (-not $tasks) { $arguments += '--smoke-test-edit-set' }
    Invoke-ValidationProcess (Join-Path $install 'Vega.exe') $arguments
    $smoke = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    $nativeReport = Join-Path $testRoot $(if ($tasks) { 'upgraded-native-midi.json' } else { 'fresh-native-midi.json' })
    Invoke-ValidationProcess (Join-Path $install 'Vega.exe') @('--native-midi-report', ('"' + $nativeReport + '"'))
    $native = Get-Content -LiteralPath $nativeReport -Raw | ConvertFrom-Json
    if (-not ($native.frozen -and $native.native_available -and $native.connected)) { throw 'Packaged native MIDI setup failed.' }
    if (-not ($smoke.frozen -and $smoke.gui_initialized -and $smoke.muted -and $smoke.icon_present) -or $smoke.connected -or $smoke.console_attached) {
        throw 'Installed native startup without a selected controller failed.'
    }
    if ($smoke.fret_sets[0].name -ne 'Release verification' -or $smoke.fret_sets[0].frets[0] -ne 24) {
        throw 'Custom Fret Set failed to save or survive upgrade.'
    }
}
$settingsHash = (Get-FileHash -LiteralPath $isolatedSettings).Hash
$unknownFile = Join-Path $install 'user-file.txt'
Set-Content -LiteralPath $unknownFile -Value 'unowned file: preserve'
# This uninstaller belongs to the GUID-scoped destination compiled above.
$uninstaller = [IO.Path]::GetFullPath((Join-Path $install 'unins000.exe'))
if (-not $uninstaller.StartsWith($testRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe uninstall target.' }
Invoke-ValidationProcess $uninstaller @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/LOG="' + (Join-Path $testRoot 'uninstall.log') + '"'))
if ((Test-Path -LiteralPath (Join-Path $install 'Vega.exe')) -or (Test-Path -LiteralPath $desktop) -or (Test-Path -LiteralPath $start)) {
    throw 'Uninstall left an application file or shortcut.'
}
if (Test-Path -LiteralPath $uninstallKey) { throw 'Uninstall registration was not removed.' }
if (-not (Test-Path -LiteralPath $unknownFile)) { throw 'Uninstall erased an unknown file.' }
if ((Get-FileHash -LiteralPath $isolatedSettings).Hash -ne $settingsHash) { throw 'Uninstall changed custom settings.' }
# Nonempty, unowned destination must be rejected, not silently overwritten.
Invoke-ValidationProcess $setup @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
    ('/DIR="' + $install + '"'), ('/LOG="' + (Join-Path $testRoot 'unowned-rejected.log') + '"')) -ExpectFailure
# Reproduce the pre-Setup developer install, including both existing shortcuts.
# These are disposable fixtures, not the user's actual legacy installation.
$legacyRelative = 'releases\' + (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
$legacyDirectory = Join-Path $install $legacyRelative
$null = New-Item -ItemType Directory -Path $legacyDirectory -Force
$legacyExe = Join-Path $legacyDirectory 'Vega.exe'
Copy-Item -LiteralPath $exe -Destination $legacyExe
$legacyUnknown = Join-Path $legacyDirectory 'keep.txt'
Set-Content -LiteralPath $legacyUnknown -Value 'unlisted legacy file: preserve'
@{ Owner = 'ProjectVega.local.v1'; Releases = @(@{ Directory = $legacyRelative; Files = @('Vega.exe') }) } |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $install 'install.json') -Encoding UTF8
foreach ($linkPath in @($start, $desktop)) {
    $link = $shell.CreateShortcut($linkPath)
    $link.TargetPath = $legacyExe
    $link.Save()
}
Invoke-ValidationProcess $setup @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
    ('/DIR="' + $install + '"'), '/TASKS=""', ('/LOG="' + (Join-Path $testRoot 'legacy-upgrade.log') + '"'))
foreach ($linkPath in @($start, $desktop)) {
    if ($shell.CreateShortcut($linkPath).TargetPath -ne (Join-Path $install 'Vega.exe')) {
        throw 'Legacy shortcut was not upgraded in place.'
    }
}
if ((Test-Path -LiteralPath $legacyExe) -or (Test-Path -LiteralPath (Join-Path $install 'install.json'))) {
    throw 'Verified legacy runtime/manifest was not removed.'
}
if (-not (Test-Path -LiteralPath $legacyUnknown)) { throw 'Legacy migration erased an unknown file.' }
Invoke-ValidationProcess $uninstaller @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
    ('/LOG="' + (Join-Path $testRoot 'legacy-uninstall.log') + '"'))
if ((Test-Path -LiteralPath (Join-Path $install 'Vega.exe')) -or (Test-Path -LiteralPath $desktop) -or (Test-Path -LiteralPath $start)) {
    throw 'Legacy-upgrade uninstall left a current app/shortcut.'
}
if (-not (Test-Path -LiteralPath $legacyUnknown) -or -not (Test-Path -LiteralPath $unknownFile)) { throw 'Uninstall erased an unknown file.' }
# A tampered manifest must never cause deletion outside its hashed release.
Copy-Item -LiteralPath $exe -Destination $legacyExe
@{ Owner = 'ProjectVega.local.v1'; Releases = @(@{ Directory = $legacyRelative; Files = @('Vega.exe', '..\..\user-file.txt') }) } |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $install 'install.json') -Encoding UTF8
Invoke-ValidationProcess $setup @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
    ('/DIR="' + $install + '"'), '/TASKS=""', ('/LOG="' + (Join-Path $testRoot 'unsafe-legacy.log') + '"'))
if (-not (Test-Path -LiteralPath $legacyExe) -or -not (Test-Path -LiteralPath $unknownFile)) { throw 'Unsafe legacy cleanup deleted a file.' }
Invoke-ValidationProcess $uninstaller @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
    ('/LOG="' + (Join-Path $testRoot 'unsafe-legacy-uninstall.log') + '"'))
$afterSettings = if (Test-Path -LiteralPath $userSettings) { (Get-FileHash -LiteralPath $userSettings).Hash } else { '' }
if ($beforeSettings -ne $afterSettings) { throw 'Personal settings changed during validation.' }
Write-Host "PASS: fresh install, upgrade, shortcuts/registration, standalone startup, editor/settings persistence, verified legacy cleanup, unsafe-manifest protection, unknown-file/settings preservation, uninstall. Evidence: $testRoot"
