#Requires -Version 5.1
param(
    [switch]$UsePolicy,
    [switch]$OpenStorePages
)

$ErrorActionPreference = 'Stop'
$ExtDir = Split-Path -Parent $PSScriptRoot
$MetaPath = Join-Path $ExtDir 'extension-id.json'
$Meta = Get-Content -Raw -Path $MetaPath | ConvertFrom-Json

$ChromeId = $Meta.chrome_extension_id
$ChromeUrl = $Meta.chrome_web_store_url
$EdgeUrl = $Meta.edge_addons_url
$FirefoxUrl = $Meta.firefox_addons_url

function Write-Info($Message) { Write-Host "  $Message" }

function Install-ChromePolicy {
    param([string]$RootKey)
    $Path = Join-Path $RootKey 'Software\Policies\Google\Chrome\ExtensionInstallForcelist'
    New-Item -Path $Path -Force | Out-Null
    New-ItemProperty -Path $Path -Name '1' -PropertyType String `
        -Value "$ChromeId;https://clients2.google.com/service/update2/crx" -Force | Out-Null
    Write-Info "Wrote Chrome policy under $Path"
}

function Install-EdgePolicy {
    param([string]$RootKey)
    $Path = Join-Path $RootKey 'Software\Policies\Microsoft\Edge\ExtensionInstallForcelist'
    New-Item -Path $Path -Force | Out-Null
    New-ItemProperty -Path $Path -Name '1' -PropertyType String `
        -Value "$ChromeId;https://edge.microsoft.com/extensionwebstorebase/v1/crx" -Force | Out-Null
    Write-Info "Wrote Edge policy under $Path"
}

Write-Host ''
Write-Host '==> Linapse Browser Connector'

if (($UsePolicy -or $env:LINAPSE_INSTALL_BROWSER_POLICY -eq '1') -and $ChromeId) {
    Write-Host ''
    Write-Host '==> Installing managed browser policies'
    foreach ($Root in @('HKLM:\', 'HKCU:\')) {
        Install-ChromePolicy -RootKey $Root
        Install-EdgePolicy -RootKey $Root
    }
    Write-Info 'Restart Chrome and Edge to apply policies.'
} elseif ($UsePolicy -or $env:LINAPSE_INSTALL_BROWSER_POLICY -eq '1') {
    Write-Info 'chrome_extension_id is not set in extension-id.json — skipping managed policy install.'
} elseif ($OpenStorePages -or $env:LINAPSE_OPEN_STORE_PAGES -eq '1') {
    Write-Info 'Opening official store pages for manual install...'
    Start-Process $ChromeUrl
    Start-Process $EdgeUrl
    Start-Process $FirefoxUrl
} else {
    Write-Info 'Install the extension from your browser''s store (links below).'
    Write-Info "To open all store pages: `$env:LINAPSE_OPEN_STORE_PAGES=1; .\install-windows.ps1"
}

Write-Host ''
Write-Host '==> Browser connector setup'
Write-Host @"

Install the official Linapse Browser Connector from your browser's extension store:
  Chrome:  $ChromeUrl
  Edge:    $EdgeUrl
  Firefox: $FirefoxUrl

Then open https://cad.onshape.com or SketchUp Web and move the CAD Mouse.
"@
