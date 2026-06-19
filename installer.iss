[Setup]
AppName=Linapse CAD Mouse Service
AppVersion=2.6.8
DefaultDirName={autopf}\LinapseCADMouse
DefaultGroupName=Linapse CAD Mouse
OutputDir=.
OutputBaseFilename=LinapseServiceSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\linapse-service.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Linapse CAD Mouse Service"; Filename: "{app}\linapse-service.exe"
Name: "{group}\Uninstall Linapse"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\linapse-service.exe"; Flags: nowait postinstall skipifsilent
