// ==UserScript==
// @name         Linapse Browser Connector
// @namespace    https://github.com/sb-ocr/cad-mouse-mk2
// @version      2.6.14
// @description  Makes OnShape and SketchUp Web connect to the local spacenav-ws bridge on Linux
// @author       CAD Mouse MK2 contributors
// @match        https://cad.onshape.com/*
// @match        https://*.sketchup.com/*
// @match        https://sketchup.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

(function () {
    'use strict';

    // OnShape and SketchUp Web's 3Dconnexion integration only activates on Windows.
    // Spoofing the platform makes it try to connect to the local
    // spacenav-ws WebSocket server.
    Object.defineProperty(navigator, 'platform', {
        get: function () { return 'Win32'; },
        configurable: true,
    });
})();
