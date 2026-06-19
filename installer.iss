[Setup]
AppName=Linapse CAD Mouse Service
AppVersion=2.5.2
DefaultDirName={autopf}\LinapseCADMouse
DefaultGroupName=Linapse CAD Mouse
OutputDir=.
OutputBaseFilename=LinapseServiceSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\linapse-service.exe"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{app}\linapse-service.exe"; Flags: nowait postinstall skipifsilent
