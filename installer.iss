[Setup]
AppName=Linapse CAD Mouse Service
AppVersion=2.19.0
DefaultDirName={autopf}\LinapseCADMouse
DefaultGroupName=Linapse CAD Mouse
OutputDir=.
OutputBaseFilename=LinapseServiceSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\linapse-service.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "configurator\dist\win-unpacked\*"; DestDir: "{app}\configurator"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "extension\dist\chrome\*"; DestDir: "{app}\extension"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "extension\scripts\install-windows.ps1"; DestDir: "{app}\extension\scripts"; Flags: ignoreversion
Source: "extension\extension-id.json"; DestDir: "{app}\extension"; Flags: ignoreversion

[Icons]
Name: "{group}\Linapse Configurator"; Filename: "{app}\configurator\Linapse Configurator.exe"
Name: "{group}\Linapse CAD Mouse Service"; Filename: "{app}\linapse-service.exe"
Name: "{group}\Uninstall Linapse"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\linapse-service.exe"; Flags: nowait postinstall skipifsilent
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\extension\scripts\install-windows.ps1"""; Description: "Show browser extension install links"; Flags: postinstall nowait skipifsilent unchecked

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "LinapseCADMouseService"; ValueData: """{app}\linapse-service.exe"""; Flags: uninsdeletevalue
