// UI feature flags for YTV2 Dashboard (runtime, no build step required)
// - Exported for ES module usage
// - Also attached to window for non-module access

export const UI_FLAGS = {
  compactCardActions: true,
  cardExpandInline: true,   // Enabled in Phase 2
  queueEnabled: true,        // ← enable for test
  showWaveformPreview: true  // ← enable for test
};

// Provide global access without import (keeps old scripts working)
try {
  if (typeof window !== 'undefined') {
    window.UI_FLAGS = UI_FLAGS;
  }
} catch (_) {}
