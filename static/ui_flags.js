// UI feature flags for YTV2 Dashboard (runtime, no build step required)
// Classic script (no module export) to guarantee early, in-order execution
// and avoid race with dashboard_v3.js. Also attached to window.

// Note: The template loads root `ui_flags.js` (not this file). This file is kept
// for reference only. Make changes in `/ui_flags.js` and bump the script query
// param in `dashboard_v3_template.html` if needed.
const UI_FLAGS = {
  compactCardActions: true,
  cardExpandInline: true,
  queueEnabled: false,
  showWaveformPreview: true,
  cardV4: true,
};

// Provide global access without import (keeps old scripts working)
try {
  if (typeof window !== 'undefined') {
    window.UI_FLAGS = UI_FLAGS;
  }
} catch (_) {}
