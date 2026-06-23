%{!?_userunitdir: %global _userunitdir %{_prefix}/lib/systemd/user}
%{!?_environmentdir: %global _environmentdir %{_prefix}/lib/environment.d}
%{!?_udevrulesdir: %global _udevrulesdir %{_prefix}/lib/udev/rules.d}

Name:           linapse-cad-mouse
Version:        2.21.30
Release:        1%{?dist}
Summary:        CAD Mouse MK2 Linapse driver service and configurator

License:        GPLv3
URL:            https://github.com/spikeon/linapse-cad-mouse-v2
Source0:        https://github.com/spikeon/linapse-cad-mouse-v2/archive/refs/tags/v%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
Requires:       python3
Requires:       python3-websockets
Requires:       python3-pyserial
Requires:       python3-pyyaml
Requires:       python3-fastapi
Requires:       python3-uvicorn
Requires:       python3-numpy
Requires:       python3-scipy
Requires:       ydotool

%description
Driver service and WebSocket bridge for Seeed XIAO RP2040 based
CAD Mouse MK2, including a local web-based configuration utility.

%prep
%autosetup -n linapse-cad-mouse-v2-%{version}

%build
# Nothing to compile

%install
# Install Python modules
install -d %{buildroot}%{python3_sitelib}
cp -r service/linapse %{buildroot}%{python3_sitelib}/
cp -r service/spacenav_ws %{buildroot}%{python3_sitelib}/

# Install service scripts
install -Dm755 service/linapse-service %{buildroot}%{_bindir}/linapse-service
install -Dm755 service/linapse-ws-proxy %{buildroot}%{_bindir}/linapse-ws-proxy

# Install systemd user services
install -d %{buildroot}%{_userunitdir}
sed 's|%h/.local/bin/linapse-service|%{_bindir}/linapse-service|g' service/systemd/linapse-service.service \
  > %{buildroot}%{_userunitdir}/linapse-service.service

install -m644 service/systemd/ydotoold.service %{buildroot}%{_userunitdir}/ydotoold.service

sed -e 's|__CONFIGURATOR_DIR__|%{_datadir}/linapse/configurator|g' \
    -e 's|__PORT__|7890|g' \
    service/systemd/linapse-configurator.service \
    > %{buildroot}%{_userunitdir}/linapse-configurator.service

# Install configurator files
install -d %{buildroot}%{_datadir}/linapse/configurator
cp -r configurator/* %{buildroot}%{_datadir}/linapse/configurator/
rm -rf %{buildroot}%{_datadir}/linapse/configurator/node_modules
rm -rf %{buildroot}%{_datadir}/linapse/configurator/dist

# Install patched Electron main.js without updater
cat << 'EOF' > %{buildroot}%{_datadir}/linapse/configurator/main.js
const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 1020,
    height: 820,
    title: "Linapse Configurator",
    icon: path.join(__dirname, 'linapse-square-logo.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  win.loadFile(path.join(__dirname, 'index.html'));
  win.setMenuBarVisibility(false);
}

app.whenReady().then(() => {
  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
EOF

# Install configurator wrapper script
install -d %{buildroot}%{_bindir}
cat << 'EOF' > %{buildroot}%{_bindir}/linapse-configurator
#!/bin/sh
if command -v electron >/dev/null; then
  exec electron %{_datadir}/linapse/configurator "$@"
else
  exec xdg-open http://localhost:7890
fi
EOF
chmod +x %{buildroot}%{_bindir}/linapse-configurator

# Install desktop entry
install -Dm644 /dev/null %{buildroot}%{_datadir}/applications/linapse-configurator.desktop
cat << 'EOF' > %{buildroot}%{_datadir}/applications/linapse-configurator.desktop
[Desktop Entry]
Name=Linapse Configurator
Comment=CAD Mouse MK2 Electron Configurator
Exec=linapse-configurator
Icon=/usr/share/linapse/configurator/linapse-square-logo.png
Terminal=false
Type=Application
Categories=Utility;Settings;
StartupNotify=true
EOF

# Install system-wide environment.d file
install -d %{buildroot}%{_environmentdir}
cat << 'EOF' > %{buildroot}%{_environmentdir}/99-spnav.conf
SPNAV_SOCKET="${XDG_RUNTIME_DIR}/spnav.sock"
EOF

# Install udev rules
install -Dm644 service/udev/99-spacemouse.rules %{buildroot}%{_udevrulesdir}/99-spacemouse.rules

%files
%{_bindir}/linapse-service
%{_bindir}/linapse-ws-proxy
%{_bindir}/linapse-configurator
%{python3_sitelib}/linapse/
%{python3_sitelib}/spacenav_ws/
%{_userunitdir}/linapse-service.service
%{_userunitdir}/linapse-configurator.service
%{_userunitdir}/ydotoold.service
%{_datadir}/linapse/configurator/
%{_datadir}/applications/linapse-configurator.desktop
%{_environmentdir}/99-spnav.conf
%{_udevrulesdir}/99-spacemouse.rules

%changelog
* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.30-1
- Add -u flag to dput to bypass local GPG verification issues in CI and bump version to 2.21.30

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.29-1
- Add support for skipping test/build steps in CI using commit message and bump version to 2.21.29

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.28-1
- Correct Launchpad PPA dput directory path format to username/ppa-name/ubuntu/ and bump version to 2.21.28

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.27-1
- Fix dput incoming path trailing slash and set passive_ftp, and bump version to 2.21.27

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.26-1
- Fix Ubuntu PPA signing using loopback GPG wrapper script and devscripts config, and bump version to 2.21.26

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.25-1
- Expand absolute path in GPG wrapper script and add passphrase diagnostics and bump version to 2.21.25

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.24-1
- Fix gpg-agent.conf newline bug and use DEBSIGN_PROGRAM environment variable and bump version to 2.21.24

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.23-1
- Configure passphrase-file in GPG wrapper script and add Git pull retry to PPA failure log step and bump version to 2.21.23

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.22-1
- Increase Playwright reload timeout to stabilize Windows build and bump version to 2.21.22

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.21-1
- Integrate GPG_PASSPHRASE into workflow steps and wrapper script and bump version to 2.21.21

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.20-1
- Add diagnostics and use gpgconf kill all in PPA release workflow and bump version to 2.21.20

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.19-1
- Add failure error logging and automatic log push in PPA release workflow step and bump version to 2.21.19

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.18-1
- Fix Ubuntu PPA signing path in GNUPGHOME isolation and bump version to 2.21.18

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.17-1
- Fix Ubuntu PPA signing by enabling GPG agent loopback mode in config and bump version to 2.21.17

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.16-1
- Fix Ubuntu PPA signing using loopback GPG wrapper script and bump version to 2.21.16

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.15-1
- Fix Ubuntu PPA signing using loopback mode in debsign parameter and bump version to 2.21.15

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.14-1
- Fix Ubuntu PPA signing using loopback mode in gpg.conf and bump version to 2.21.14

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.13-1
- Fix Ubuntu PPA signing using ghaction-import-gpg and bump version to 2.21.13

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.12-1
- Fix Ubuntu PPA signing using stdin GPG wrapper script and bump version to 2.21.12

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.11-1
- Fix Ubuntu PPA signing using GPG wrapper script and bump version to 2.21.11

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.10-1
- Fix PPA GPG passphrase passing with loopback fd 0 and bump version to 2.21.10

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.9-1
- Limit COPR builds to Python 3.8+ compatible chroots and bump version to 2.21.9

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.8-1
- Fix Ubuntu PPA signing command and bump version to 2.21.8

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.7-1
- Fix missing systemd/udev macros and bump version to 2.21.7

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.6-1
- Update version to 2.21.6

* Tue Jun 23 2026 spikeon <spikeon@example.com> - 2.21.5-1
- Initial Fedora packaging release
