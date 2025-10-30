// UI feature flags (branch-local)
window.UI_FLAGS = Object.assign({}, window.UI_FLAGS || {}, {
  // Enable new Stream/Mosaic card rendering in List/Grid views
  cardV4: true,
  // Experimental Tailwind-first card/layout revamp (v5)
  twRevamp: true,
  // Allow inline expand/collapse for Read action
  cardExpandInline: true,
});
