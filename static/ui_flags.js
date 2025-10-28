// UI feature flags for YTV2 Dashboard (runtime, no build step required)
// Classic script (no module export) to guarantee early, in-order execution
// and avoid race with dashboard_v3.js. Also attached to window.

const UI_FLAGS = {
  compactCardActions: true,
  cardExpandInline: true,   // Enabled in Phase 2
  queueEnabled: false,      // drop queue UI per feedback
  showWaveformPreview: true, // ← enable for test
  // New card system (List: Stream, Grid: Mosaic)
  cardV4: true
};

// Provide global access without import (keeps old scripts working)
try {
  if (typeof window !== 'undefined') {
    window.UI_FLAGS = UI_FLAGS;
  }
} catch (_) {}
