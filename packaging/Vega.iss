; Classic per-user setup. No drivers, services, updater or settings deletion.
#ifndef AppVersion
  #error Pass AppVersion from the packaged executable using build-installer.ps1
#endif
#ifndef AppIdentity
  #define AppIdentity "ProjectVega.Vega"
#endif
#ifndef ShortcutName
  #define ShortcutName "Vega"
#endif
#ifndef InstallFolder
  #define InstallFolder "Vega"
#endif
#ifndef SetupName
  #define SetupName "Vega-Setup"
#endif

[Setup]
AppId={#AppIdentity}
AppName=Vega
AppVersion={#AppVersion}
AppVerName=Vega {#AppVersion}
AppSupportURL=https://github.com/tamarin08/ProjectVega
VersionInfoDescription=Vega Guitar Controller
VersionInfoProductName=Vega
VersionInfoVersion={#AppVersion}
VersionInfoCopyright=Unlicense
DefaultDirName={localappdata}\Programs\{#InstallFolder}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.26200
WizardStyle=classic
WizardSizePercent=100
WizardImageFile=..\build\installer-art\welcome.bmp
WizardSmallImageFile=..\build\installer-art\header.bmp
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=yes
DisableReadyPage=no
DisableFinishedPage=no
SetupIconFile=..\src\vega\app\resources\vega.ico
UninstallDisplayIcon={app}\Vega.exe
OutputDir=..\dist\installer
OutputBaseFilename={#SetupName}
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
Uninstallable=yes
AppReadmeFile={app}\README.md

[Messages]
WelcomeLabel1=Welcome to the Vega Setup Wizard
BeveledLabel=Vega

[LangOptions]
DialogFontName=Tahoma
DialogFontSize=8
WelcomeFontName=Tahoma
WelcomeFontSize=12

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Vega\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#ShortcutName}"; Filename: "{app}\Vega.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Vega.exe"; AppUserModelID: "ProjectVega.Vega"
Name: "{userdesktop}\{#ShortcutName}"; Filename: "{app}\Vega.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Vega.exe"; Tasks: desktopicon; AppUserModelID: "ProjectVega.Vega"
Name: "{userdesktop}\{#ShortcutName}"; Filename: "{app}\Vega.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Vega.exe"; Check: KeepLegacyDesktop; AppUserModelID: "ProjectVega.Vega"

[Run]
Filename: "{app}\Vega.exe"; Description: "Launch Vega"; Flags: nowait postinstall skipifsilent unchecked

[Code]
var
  Legacy: Boolean;
  LegacyDesktop: Boolean;

function SetWindowTheme(Window: HWND; SubAppName, SubIdList: String): Integer;
  external 'SetWindowTheme@uxtheme.dll stdcall';

function GetFileAttributes(Filename: String): LongWord;
  external 'GetFileAttributesW@kernel32.dll stdcall';

function RedirectedPath(Path: String): Boolean;
var
  Parent: String;
  Attributes: LongWord;
begin
  Result := False;
  repeat
    Attributes := GetFileAttributes(Path);
    if (Attributes <> $FFFFFFFF) and ((Attributes and $400) <> 0) then
    begin
      Result := True;
      Exit;
    end;
    Parent := ExtractFileDir(Path);
    if CompareText(Parent, Path) = 0 then Exit;
    Path := Parent;
  until Path = '';
end;

function RedirectedTree(const Directory: String): Boolean;
var
  Entry: TFindRec;
  Child: String;
begin
  Result := RedirectedPath(Directory);
  if Result then Exit;
  if FindFirst(AddBackslash(Directory) + '*', Entry) then
  begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') then
        begin
          Child := AddBackslash(Directory) + Entry.Name;
          Result := (Entry.Attributes and $400) <> 0;
          if not Result and ((Entry.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0) then
            Result := RedirectedTree(Child);
          if Result then Exit;
        end;
      until not FindNext(Entry);
    finally
      FindClose(Entry);
    end;
  end;
end;

function HasHashedLegacyExecutable: Boolean;
var
  Entry: TFindRec;
  Filename: String;
begin
  Result := False;
  if FindFirst(ExpandConstant('{app}\releases\*'), Entry) then
  begin
    try
      repeat
        if Length(Entry.Name) = 64 then
        begin
          Filename := ExpandConstant('{app}\releases\') + Entry.Name + '\Vega.exe';
          if FileExists(Filename) and not RedirectedPath(Filename) then
            if CompareText(GetSHA256OfFile(Filename), Entry.Name) = 0 then
            begin
              Result := True;
              Exit;
            end;
        end;
      until not FindNext(Entry);
    finally
      FindClose(Entry);
    end;
  end;
end;

procedure InitializeWizard;
var
  Index: Integer;
begin
  { Per-window visual styling only; never changes the user's Windows theme. }
  WizardForm.Color := $00C8D0D4;
  WizardForm.WelcomePage.Color := $00C8D0D4;
  WizardForm.FinishedPage.Color := $00C8D0D4;
  WizardForm.InnerPage.Color := $00C8D0D4;
  WizardForm.MainPanel.Color := $00C8D0D4;
  for Index := 0 to WizardForm.ComponentCount - 1 do
    if WizardForm.Components[Index] is TWinControl then
      SetWindowTheme(TWinControl(WizardForm.Components[Index]).Handle, ' ', ' ');
end;

function IsLegacyInstall: Boolean;
var
  Raw: AnsiString;
  Content: String;
begin
  Result := False;
  if LoadStringFromFile(ExpandConstant('{app}\install.json'), Raw) then
  begin
    Content := String(Raw);
    StringChangeEx(Content, ' ', '', True);
    StringChangeEx(Content, #9, '', True);
    StringChangeEx(Content, #13, '', True);
    StringChangeEx(Content, #10, '', True);
    Result := (Pos('"Owner":"ProjectVega.local.v1"', Content) > 0) and
              HasHashedLegacyExecutable;
  end;
end;

function LegacyShortcut(const Filename: String): Boolean;
var
  Shell, Link: Variant;
  Target, ReleaseDirectory, ReleaseHash: String;
begin
  Result := False;
  if Legacy and FileExists(Filename) then
  begin
    Shell := CreateOleObject('WScript.Shell');
    Link := Shell.CreateShortcut(Filename);
    Target := ExpandFileName(Link.TargetPath);
    ReleaseDirectory := ExtractFileDir(Target);
    ReleaseHash := ExtractFileName(ReleaseDirectory);
    if (CompareText(ExtractFileDir(ReleaseDirectory), ExpandConstant('{app}\releases')) = 0) and
       (Length(ReleaseHash) = 64) and
       (CompareText(ExtractFileName(Target), 'Vega.exe') = 0) and
       FileExists(Target) and not RedirectedPath(Target) then
      Result := CompareText(GetSHA256OfFile(Target), ReleaseHash) = 0;
  end;
end;

function KeepLegacyDesktop: Boolean;
begin
  Result := LegacyDesktop and not WizardIsTaskSelected('desktopicon');
end;

function HasFiles(const Directory: String): Boolean;
var
  Entry: TFindRec;
begin
  Result := False;
  if FindFirst(AddBackslash(Directory) + '*', Entry) then
  begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') then
          Result := True;
      until not FindNext(Entry);
    finally
      FindClose(Entry);
    end;
  end;
end;

function ConflictingShortcut(const Filename: String): Boolean;
var
  Shell, Link: Variant;
begin
  Result := False;
  if FileExists(Filename) then
  begin
    Shell := CreateOleObject('WScript.Shell');
    Link := Shell.CreateShortcut(Filename);
    Result := (CompareText(ExpandFileName(Link.TargetPath), ExpandConstant('{app}\Vega.exe')) <> 0)
              and not LegacyShortcut(Filename);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExistingDirectory: String;
  Managed: Boolean;
begin
  Result := '';
  if not FileExists(ExpandConstant('{sys}\Midi2.MidiSrvTransport.dll')) or
     not RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\midisrv') then
  begin
    Result := 'Updated Windows 11 25H2 or later with Windows MIDI Service is required. Install Windows updates, then run Setup again.';
    Exit;
  end;
  Managed := RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppIdentity}_is1',
                                 'InstallLocation', ExistingDirectory);
  Managed := Managed and (CompareText(AddBackslash(ExistingDirectory), AddBackslash(ExpandConstant('{app}'))) = 0);
  if RedirectedTree(ExpandConstant('{app}')) then
  begin
    Result := 'Choose a destination without symbolic links or directory junctions.';
    Exit;
  end;
  Legacy := IsLegacyInstall;
  LegacyDesktop := LegacyShortcut(ExpandConstant('{userdesktop}\{#ShortcutName}.lnk'));
  if Legacy and not Managed and
     (FileExists(ExpandConstant('{app}\Vega.exe')) or DirExists(ExpandConstant('{app}\_internal')) or
      DirExists(ExpandConstant('{app}\licenses')) or DirExists(ExpandConstant('{app}\docs')) or
      FileExists(ExpandConstant('{app}\LICENSE')) or FileExists(ExpandConstant('{app}\README.md')) or
      FileExists(ExpandConstant('{app}\ARCHITECTURE.md')) or FileExists(ExpandConstant('{app}\THIRD_PARTY_NOTICES.md')) or
      FileExists(ExpandConstant('{app}\distribution.json'))) then
    Result := 'Legacy destination contains files at the new application paths. Choose an empty folder to preserve them.'
  else if HasFiles(ExpandConstant('{app}')) and not (Managed or Legacy) then
    Result := 'The destination contains files not managed by Vega Setup. Choose an empty folder.'
  else if ConflictingShortcut(ExpandConstant('{userprograms}\{#ShortcutName}.lnk')) or
          (WizardIsTaskSelected('desktopicon') and ConflictingShortcut(ExpandConstant('{userdesktop}\{#ShortcutName}.lnk'))) then
    Result := 'A shortcut with this name belongs to a different location. Setup will not overwrite unrelated shortcuts.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ExitCode: Integer;
begin
  if (CurStep = ssPostInstall) and FileExists(ExpandConstant('{app}\install.json')) then
  begin
    { Only after successful copying/registration. Strict manifest/path/hash checks
      live in the small packaging helper, not in the musical application. }
    if not Exec(ExpandConstant('{app}\Vega.exe'), '--cleanup-legacy',
                ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ExitCode) then
      Log('Legacy cleanup could not start; old files preserved.')
    else if ExitCode <> 0 then
      Log('Legacy ownership could not be verified or cleanup failed; remaining files preserved.')
    else
      Log('Verified legacy files removed; unlisted files and user settings preserved.');
  end;
end;
