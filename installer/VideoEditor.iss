[Setup]
AppId={{7D46456F-93B5-4EBE-9855-BF0C08155F73}
AppName=Video Editor
AppVersion=1.0.0
AppPublisher=Gavrs
DefaultDirName={autopf}\Video Editor
DefaultGroupName=Video Editor
OutputDir=..\installer_output
OutputBaseFilename=VideoEditorSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\VideoEditor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Video Editor"; Filename: "{app}\VideoEditor.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Video Editor"; Filename: "{app}\VideoEditor.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\VideoEditor.exe"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,Video Editor}"; Flags: nowait postinstall skipifsilent
