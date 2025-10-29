// UI feature flags for YTV2 Dashboard (runtime, no build step required)
// Classic script (no module export) to guarantee early, in-order execution
// and avoid race with dashboard_v3.js. Also attached to window.

// Note: The template loads root `ui_flags.js` (not this file). This file is kept
// for reference only. Make changes in `/ui_flags.js` and bump the script query
// param in `dashboard_v3_template.html` if needed.
// Note: On this server, requests to "/ui_flags.js" resolve to this file
// (static/ui_flags.js). Merge onto any existing flags for safety.
try {
  if (typeof window !== 'undefined') {
    window.UI_FLAGS = Object.assign({}, window.UI_FLAGS || {}, {
      compactCardActions: true,
      cardExpandInline: true,
      queueEnabled: false,
      showWaveformPreview: true,
      cardV4: true,
      // Experimental Tailwind-first cards (V5)
      twRevamp: true,
    });
  }
} catch (_) {}
