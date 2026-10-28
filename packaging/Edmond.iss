; Independent per-user installation, without drivers or a native MIDI endpoint.
#ifndef AppVersion
  #error Pass AppVersion from the packaged executable using build-edmond.ps1
#endif
#ifndef AppIdentity
  #define AppIdentity "ProjectEdmond.Edmond"
#endif
#ifndef ShortcutName
  #define ShortcutName "Project Edmond"
#endif
#ifndef InstallFolder
  #define InstallFolder "Edmond"
#endif
#ifndef SetupName
  #define SetupName "Edmond-Setup"
#endif
[Setup]
AppId={#AppIdentity}
AppName=Project Edmond
AppVersion={#AppVersion}
AppVerName=Project Edmond {#AppVersion}
AppSupportURL=https://github.com/tamarin08/ProjectEdmond
VersionInfoDescription=Edmond MPC Beats Controller
VersionInfoProductName=Project Edmond
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\{#InstallFolder}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.26200
WizardStyle=modern
SetupIconFile=..\src\edmond\resources\edmond.ico
UninstallDisplayIcon={app}\Edmond.exe
OutputDir=..\dist\installer
OutputBaseFilename={#SetupName}
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
AppReadmeFile={app}\README.md

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Edmond\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#ShortcutName}"; Filename: "{app}\Edmond.exe"; AppUserModelID: "{#AppIdentity}"
Name: "{userdesktop}\{#ShortcutName}"; Filename: "{app}\Edmond.exe"; Tasks: desktopicon; AppUserModelID: "{#AppIdentity}"

[Run]
Filename: "{app}\Edmond.exe"; Description: "Launch Project Edmond"; Flags: nowait postinstall skipifsilent unchecked

[Code]
function GetFileAttributes(Filename: String): LongWord;
  external 'GetFileAttributesW@kernel32.dll stdcall';

function RedirectedPath(Path: String): Boolean;
var
  Attributes: LongWord;
  Parent: String;
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

function SafeTree(const Directory: String): Boolean;
var
  Entry: TFindRec;
begin
  Result := not RedirectedPath(Directory);
  if not Result then Exit;
  if FindFirst(AddBackslash(Directory) + '*', Entry) then
  begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') then
        begin
          if (Entry.Attributes and $400) <> 0 then Result := False
          else if (Entry.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            Result := SafeTree(AddBackslash(Directory) + Entry.Name);
          if not Result then Exit;
        end;
      until not FindNext(Entry);
    finally
      FindClose(Entry);
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Directory: String;
  Marker: AnsiString;
  Entry: TFindRec;
  NonEmpty: Boolean;
begin
  Result := '';
  if not FileExists(ExpandConstant('{sys}\Midi2.MidiSrvTransport.dll')) or
     not RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\midisrv') then
  begin
    Result := 'Updated Windows 11 25H2 or later with Windows MIDI Service is required. Install Windows updates, then run Setup again.';
    Exit;
  end;
  Directory := ExpandConstant('{app}');
  if not SafeTree(Directory) then
  begin
    Result := 'Choose an installation folder without redirected paths or linked contents.';
    Exit;
  end;
  NonEmpty := False;
  if FindFirst(AddBackslash(Directory) + '*', Entry) then
  begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') then NonEmpty := True;
      until not FindNext(Entry);
    finally
      FindClose(Entry);
    end;
  end;
  if NonEmpty then
  begin
    if not LoadStringFromFile(AddBackslash(Directory) + 'edmond-identity.txt', Marker) then Marker := '';
    if Trim(Marker) <> 'ProjectEdmond.Edmond' then
    begin
      Result := 'Choose an empty folder or an existing Project Edmond installation.';
    end;
  end;
end;
