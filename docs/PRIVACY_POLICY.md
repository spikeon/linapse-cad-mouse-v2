# Linapse Browser Connector — Privacy Policy

Last Updated: June 23, 2026

Your privacy is important to us. This Privacy Policy explains how the Linapse Browser Connector extension (the "Extension") handles your data.

## 1. No Data Collection

The Extension **does not collect, store, track, or upload** any personal data, browsing history, user credentials, or CAD model data. 

## 2. Local Communication Only

The Extension operates strictly as a bridge between your browser and your local computer. 
- It communicates solely with the local CAD Mouse driver service running on your machine at `wss://127.51.68.120:8181` or `wss://localhost:13000`.
- All communication remains entirely local to your device. 
- No data is ever transmitted to external servers, cloud services, or third parties.

## 3. Permissions Justification

The Extension requests specific browser permissions to function:
- **Host Permissions (`*://*.onshape.com/*`, `*://*.sketchup.com/*`)**: Used strictly to inject the local navigation bridge script into supported CAD web pages so that your CAD Mouse MK2 can navigate the 3D viewport.
- **Storage**: Used solely to save local extension preferences (such as enabling/disabling the bridge).

## 4. Updates to This Policy

We may update this Privacy Policy from time to time. Any changes will be posted in this repository.

## 5. Contact

If you have questions about this policy, please open an issue in the official repository:
[linapse-cad-mouse-v2 GitHub Repository](https://github.com/spikeon/linapse-cad-mouse-v2)
