(function () {
  const config = (typeof window !== 'undefined' && window.DASHBOARD_CONFIG) ? window.DASHBOARD_CONFIG : {};
  const parseBool = (value, fallback) => {
    if (typeof value === 'boolean') return value;
    if (typeof value === 'number') return value !== 0;
    if (typeof value === 'string') {
      const trimmed = value.trim().toLowerCase();
      if (!trimmed) return fallback;
      if (['false', '0', 'off', 'no'].includes(trimmed)) return false;
      if (['true', '1', 'on', 'yes'].includes(trimmed)) return true;
    }
    return fallback;
  };
  const haloFromConfig = (config && (config.wallSimilarityHalo ?? config.wall_similarity_halo ?? config.WALL_SIMILARITY_HALO));
  const haloEnabled = parseBool(haloFromConfig, false);

  // UI feature flags (branch-local; config overrides where provided)
  window.UI_FLAGS = Object.assign({}, window.UI_FLAGS || {}, {
    // Enable new Stream/Mosaic card rendering in List/Grid views
    cardV4: true,
    // Experimental Tailwind-first card/layout revamp (v5)
    twRevamp: true,
    // Allow inline expand/collapse for Read action
    cardExpandInline: true,
    // Wall view: use inline row-level reader (desktop). When false, always use modal.
    wallReadInline: true,
    // Wall view: similarity halo/resort behavior around inline reader (configurable via env)
    wallSimilarityHalo: haloEnabled,
  });
})();
