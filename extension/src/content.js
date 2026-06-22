(function () {
    'use strict';

    // OnShape and SketchUp Web only enable 3Dconnexion integration on Windows.
    // Spoofing the platform makes them connect to the local Linapse browser bridge.
    Object.defineProperty(navigator, 'platform', {
        get: function () { return 'Win32'; },
        configurable: true,
    });
})();
