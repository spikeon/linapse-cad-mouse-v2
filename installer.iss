[Setup]
AppName=Linapse CAD Mouse Service
AppVersion=2.10.7
DefaultDirName={autopf}\LinapseCADMouse
DefaultGroupName=Linapse CAD Mouse
OutputDir=.
OutputBaseFilename=LinapseServiceSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\linapse-service.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "configurator\dist\win-unpacked\*"; DestDir: "{app}\configurator"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Linapse Configurator"; Filename: "{app}\configurator\Linapse Configurator.exe"
Name: "{group}\Linapse CAD Mouse Service"; Filename: "{app}\linapse-service.exe"
Name: "{group}\Uninstall Linapse"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\linapse-service.exe"; Flags: nowait postinstall skipifsilent
