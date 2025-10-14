(() => {
  // Simple telemetry logging
  const isMobile = window.innerWidth <= 768;
  console.log('[V2 Telemetry] v2_rendered', { ua_is_mobile: isMobile, viewport: `${window.innerWidth}x${window.innerHeight}` });

  const $ = (id) => document.getElementById(id);

  const VARIANT_META = {
    'comprehensive': { label: 'Comprehensive', icon: '📝', kind: 'text' },
    'bullet-points': { label: 'Key Points', icon: '🎯', kind: 'text' },
    'key-insights': { label: 'Insights', icon: '💡', kind: 'text' },
    'audio': { label: 'Audio (EN)', icon: '🎙️', kind: 'audio' },
    'audio-fr': { label: 'Audio (FR)', icon: '🎙️🇫🇷', kind: 'audio' },
    'audio-es': { label: 'Audio (ES)', icon: '🎙️🇪🇸', kind: 'audio' }
  };

  const normalizeVariantId = (value) => {
    if (!value) return '';
    return String(value).toLowerCase().replace(/_/g, '-');
  };

  const prettifyVariantId = (value) => {
    if (!value) return '';
    const normalized = normalizeVariantId(value);
    return normalized.replace(/[-_]+/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());
  };

  const formatSummaryText = (text) => {
    if (!text || typeof text !== 'string') return '';
    const trimmed = text.replace(/\r\n?/g, '\n').trim();
    if (!trimmed) return '';
    // basic bullet detection
    const lines = trimmed.split(/\n+/);
    const htmlLines = lines.map((line) => {
      if (/^\s*[-*•]/.test(line)) {
        return `<li>${line.replace(/^\s*[-*•]\s*/, '')}</li>`;
      }
      return `<p>${line}</p>`;
    });
    if (htmlLines.every((line) => line.startsWith('<li>'))) {
      return `<ul>${htmlLines.join('')}</ul>`;
    }
    return htmlLines.join('\n');
  };

  const initSummaryVariants = () => {
    const variantData = Array.isArray(window.SUMMARY_VARIANT_DATA) ? window.SUMMARY_VARIANT_DATA : [];
    const defaultVariant = normalizeVariantId(window.SUMMARY_DEFAULT_VARIANT || 'comprehensive');
    const controls = $("summaryVariantControls");
    const summaryBody = $("summaryBody");
    if (!controls || !summaryBody) return;

    const variants = new Map();
    const audioSource = (() => {
      if (!player) return '';
      const currentSrc = player.currentSrc || '';
      if (currentSrc) return currentSrc;
      const sourceEl = player.querySelector('source');
      return sourceEl ? sourceEl.src : '';
    })();

    const addVariant = (payload = {}) => {
      if (!payload) return;
      const normalized = normalizeVariantId(payload.id || payload.variant || payload.summary_type || payload.type);
      if (!normalized) return;
      if (variants.has(normalized)) return;

      const meta = VARIANT_META[normalized] || { label: prettifyVariantId(normalized), icon: '📝', kind: 'text' };
      const kind = meta.kind || 'text';

      const explicitHtml = payload.html ? String(payload.html) : (payload.content && payload.content.html ? String(payload.content.html) : '');
      const fallbackText = payload.text || payload.content?.text || '';
      const contentHtml = explicitHtml || (kind === 'text' ? formatSummaryText(fallbackText || '') : '');

      if (kind === 'text' && !contentHtml) return;

      variants.set(normalized, {
        id: normalized,
        label: payload.label || meta.label || prettifyVariantId(normalized),
        icon: meta.icon || '📝',
        kind,
        html: contentHtml,
        audioSrc: kind === 'audio' ? (payload.audio_src || payload.audioUrl || audioSource) : null
      });
    };

    variantData.forEach((item) => {
      if (!item || typeof item !== 'object') return;
      addVariant(item);
    });

    if (!variants.size) {
      addVariant({ id: defaultVariant || 'comprehensive', html: summaryBody.innerHTML });
    }

    if (!variants.has(defaultVariant)) {
      addVariant({ id: defaultVariant || 'comprehensive', html: summaryBody.innerHTML });
    }

    if (variants.size <= 1) {
      controls.style.display = 'none';
      return;
    }

    controls.style.display = '';
    controls.innerHTML = Array.from(variants.values()).map((variant) => {
      return `<button type="button" data-variant="${variant.id}"
                class="inline-flex items-center gap-2 rounded-full border border-white/50 bg-white/80 px-3.5 py-1.5 text-sm font-medium text-slate-600 shadow-sm transition hover:bg-white dark:border-slate-700/70 dark:bg-slate-900/60 dark:text-slate-200">
                <span class="text-base">${variant.icon}</span>
                <span>${variant.label}</span>
              </button>`;
    }).join('');

    const setActive = (variantId) => {
      const variant = variants.get(variantId);
      if (!variant) return;

      if (variant.kind === 'audio') {
        summaryBody.innerHTML = renderReportAudioVariant(variant);
        attachReportAudioHandlers(summaryBody, variant);
      } else {
        summaryBody.innerHTML = variant.html;
      }

      controls.querySelectorAll('[data-variant]').forEach((btn) => {
        const active = btn.dataset.variant === variantId;
        btn.classList.toggle('bg-gradient-to-r', active);
        btn.classList.toggle('from-audio-500', active);
        btn.classList.toggle('to-indigo-500', active);
        btn.classList.toggle('text-white', active);
        btn.classList.toggle('shadow-lg', active);
        btn.classList.toggle('border-transparent', active);
        btn.classList.toggle('bg-white/80', !active);
        btn.classList.toggle('dark:bg-slate-900/60', !active);
        btn.classList.toggle('text-slate-600', !active);
        btn.classList.toggle('dark:text-slate-200', !active);
      });

      controls.dataset.currentVariant = variantId;
      refreshAudioVariantState();
    };

    controls.querySelectorAll('[data-variant]').forEach((btn) => {
      btn.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        setActive(btn.dataset.variant);
      });
    });

    const initialVariant = variants.has(defaultVariant) ? defaultVariant : variants.keys().next().value;
    setActive(initialVariant);
  };

  const player = $("player");
  const playPause = $("playPause");
  const seek = $("seek");
  const timeMeta = $("timeMeta");
  const rateBtn = $("rateBtn");
  
  // Debug: Check if elements are found
  if (!player) console.error('Audio player element not found');
  if (!playPause) console.error('Play/pause button not found');
  if (!seek) console.error('Seek slider not found');

  const sticky = $("stickyBar");
  const mPlayPause = $("mPlayPause");
  const mTimeMeta = $("mTimeMeta");
  const mSeek = $("mSeek");
  const mRateBtn = $("mRateBtn");
  const closeSticky = $("closeSticky");

  const copyBtn = $("copyLinkBtn");

  let rates = [1, 1.25, 1.5, 1.75, 2];
  let rIdx = 0;

  // util
  const fmt = (sec) => {
    if (!isFinite(sec)) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  const updateButtons = () => {
    const icon = player.paused ? "▶" : "⏸";
    playPause.textContent = icon;
    mPlayPause.textContent = icon;
    refreshAudioVariantState();
  };

  const updateTime = () => {
    const cur = player.currentTime || 0;
    const dur = player.duration || 0;
    
    // If no duration from audio element, try to parse from template
    let displayDur = dur;
    if (!dur || dur === 0) {
      const templateDurText = document.querySelector('#timeMeta')?.textContent;
      if (templateDurText && templateDurText.includes('/')) {
        const parts = templateDurText.split('/');
        const durPart = parts[1]?.trim();
        if (durPart && durPart !== '—' && durPart !== '0:00') {
          // Parse template duration for display (don't set on audio element)
          const [min, sec] = durPart.split(':').map(n => parseInt(n) || 0);
          displayDur = min * 60 + sec;
        }
      }
    }
    
    timeMeta.textContent = `${fmt(cur)} / ${fmt(displayDur)}`;
    if (mTimeMeta) mTimeMeta.textContent = `${fmt(cur)} / ${fmt(displayDur)}`;
    
    if (displayDur > 0 && !seeking) {
      const progress = Math.round((cur / displayDur) * 100);
      seek.value = progress;
      if (mSeek) mSeek.value = progress;
    }

    // Debug logging
    if (dur === 0 && displayDur > 0) {
      console.log('[V2 Debug] Using template duration:', displayDur, 'audio duration:', dur);
    }

    refreshAudioVariantState();
  };

  // sticky visibility rules:
  //  - show once user scrolls > 240px OR playback has started
  //  - hide on explicit close
  let stickyClosed = false;
  const maybeShowSticky = () => {
    if (stickyClosed) return;
    const scrolled = window.scrollY > 240;
    const playing = !player.paused && !player.ended;
    const shouldShow = (scrolled || playing);
    const wasHidden = sticky.style.display === "none";
    sticky.style.display = shouldShow ? "block" : "none";
    
    if (shouldShow && wasHidden) {
      console.log('[V2 Telemetry] sticky_shown', { scrolled, playing });
    }
  };

  const resolveAudioSource = (fallback = '') => {
    if (player) {
      if (player.currentSrc) return player.currentSrc;
      const sourceEl = player.querySelector('source');
      if (sourceEl && sourceEl.src) return sourceEl.src;
    }
    return fallback;
  };

  const renderReportAudioVariant = (variant) => {
    const audioSrc = resolveAudioSource(variant.audioSrc || '');
    const available = Boolean(audioSrc);
    const playing = available && player && !player.paused && !player.ended;
    const status = !available
      ? 'Audio summary is not available for this report.'
      : playing
        ? 'Now playing via the audio controls above.'
        : 'Ready to play. Use the button below or the main controls to start playback.';
    const actionLabel = !available ? 'Unavailable' : (playing ? 'Pause audio' : 'Play audio');
    const buttonState = available ? '' : 'disabled aria-disabled="true"';
    const downloadMarkup = available
      ? `<a href="${audioSrc}" download
            class="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            data-report-audio-download>
            Download
         </a>`
      : '';

    return `
      <div class="rounded-xl border border-slate-200 bg-slate-50/80 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/60"
           data-report-audio-variant data-audio-available="${available ? '1' : ''}">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div class="space-y-1">
            <p class="font-semibold text-slate-800 dark:text-slate-100">${variant.label || 'Audio summary'}</p>
            <p class="text-slate-600 dark:text-slate-300" data-audio-status>${status}</p>
            <p class="text-xs text-slate-500 dark:text-slate-400">Use the primary player controls above to scrub or change speed.</p>
          </div>
          <div class="flex items-center gap-2 self-start md:self-auto">
            ${downloadMarkup}
            <button type="button" ${buttonState}
                    class="inline-flex items-center gap-2 rounded-full border border-white/40 bg-gradient-to-r from-audio-500 to-indigo-500 px-4 py-1.5 text-sm font-semibold text-white shadow-md disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-200 disabled:text-slate-500 dark:disabled:border-slate-700 dark:disabled:bg-slate-800 dark:disabled:text-slate-400"
                    data-report-audio-btn>
              ${actionLabel}
            </button>
          </div>
        </div>
      </div>
    `;
  };

  const attachReportAudioHandlers = (container, variant) => {
    const block = container.querySelector('[data-report-audio-variant]');
    if (!block) return;
    const playBtn = block.querySelector('[data-report-audio-btn]');
    if (playBtn) {
      playBtn.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!player) return;
        if (player.paused) {
          player.play().catch((err) => console.error('Audio play failed', err));
        } else {
          player.pause();
        }
      });
    }

    const downloadLink = block.querySelector('[data-report-audio-download]');
    if (downloadLink) {
      downloadLink.addEventListener('click', (event) => event.stopPropagation());
    }
  };

  const refreshAudioVariantState = () => {
    document.querySelectorAll('[data-report-audio-variant]').forEach((block) => {
      const available = block.getAttribute('data-audio-available') === '1';
      const statusEl = block.querySelector('[data-audio-status]');
      const btn = block.querySelector('[data-report-audio-btn]');
      const audioSrc = resolveAudioSource();

      if (!available || !audioSrc) {
        if (statusEl) statusEl.textContent = 'Audio summary is not available for this report.';
        if (btn) {
          btn.textContent = 'Unavailable';
          btn.disabled = true;
        }
        return;
      }

      const playing = player && !player.paused && !player.ended;
      if (statusEl) {
        statusEl.textContent = playing
          ? 'Now playing via the audio controls above.'
          : 'Ready to play. Use the button below or the main controls to start playback.';
      }
      if (btn) {
        btn.disabled = false;
        btn.textContent = playing ? 'Pause audio' : 'Play audio';
      }
      const downloadLink = block.querySelector('[data-report-audio-download]');
      if (downloadLink) downloadLink.href = audioSrc;
    });
  };

  // events
  if (playPause && player) {
    playPause.addEventListener("click", () => {
      console.log('[V2 Telemetry] play_clicked', { was_paused: player.paused });
      if (player.paused) player.play(); else player.pause();
    });
  }
  mPlayPause.addEventListener("click", () => {
    if (player.paused) player.play(); else player.pause();
  });

  // sticky player controls
  mRateBtn?.addEventListener("click", () => {
    rIdx = (rIdx + 1) % rates.length;
    player.playbackRate = rates[rIdx];
    rateBtn.textContent = `${rates[rIdx]}×`;
    mRateBtn.textContent = `${rates[rIdx]}×`;
  });

  mSeek?.addEventListener("mousedown", () => { seeking = true; });
  mSeek?.addEventListener("mouseup", () => { seeking = false; });
  mSeek?.addEventListener("touchstart", () => { seeking = true; });
  mSeek?.addEventListener("touchend", () => { seeking = false; });
  
  mSeek?.addEventListener("input", () => {
    if (seeking) {
      const dur = player.duration || 0;
      player.currentTime = (mSeek.value / 100) * dur;
    }
  });

  rateBtn?.addEventListener("click", () => {
    rIdx = (rIdx + 1) % rates.length;
    player.playbackRate = rates[rIdx];
    rateBtn.textContent = `${rates[rIdx]}×`;
  });

  let seeking = false;
  
  seek.addEventListener("mousedown", () => { seeking = true; });
  seek.addEventListener("mouseup", () => { seeking = false; });
  seek.addEventListener("touchstart", () => { seeking = true; });
  seek.addEventListener("touchend", () => { seeking = false; });
  
  seek.addEventListener("input", () => {
    if (seeking) {
      const dur = player.duration || 0;
      player.currentTime = (seek.value / 100) * dur;
    }
  });

  player.addEventListener("timeupdate", updateTime);
  player.addEventListener("loadedmetadata", updateTime);
  player.addEventListener("play", () => { updateButtons(); maybeShowSticky(); });
  player.addEventListener("pause", () => { updateButtons(); maybeShowSticky(); });
  player.addEventListener("ended", () => { updateButtons(); maybeShowSticky(); });

  window.addEventListener("scroll", maybeShowSticky);

  closeSticky.addEventListener("click", () => {
    stickyClosed = true;
    sticky.style.display = "none";
  });

  // copy link
  copyBtn?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      copyBtn.textContent = "Copied!";
      setTimeout(() => (copyBtn.textContent = "Copy link"), 1200);
    } catch {}
  });

  // Theme toggle functionality
  const themeToggle = $("themeToggle");
  const themeIcon = $("themeIcon");
  const themeText = $("themeText");
  
  const themes = {
    light: { 
      name: 'Light',
      icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>` 
    },
    dark: { 
      name: 'Dark',
      icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>` 
    },
    system: { 
      name: 'System',
      icon: `<rect x="3" y="4" width="18" height="14" rx="2"/><path d="M9 17v3h6v-3"/>` 
    }
  };
  
  let currentTheme = localStorage.getItem('ytv2.theme') || 'system';
  
  const applyTheme = (theme) => {
    const html = document.documentElement;
    
    if (theme === 'system') {
      const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (systemPrefersDark) {
        html.classList.add('dark');
      } else {
        html.classList.remove('dark');
      }
    } else if (theme === 'dark') {
      html.classList.add('dark');
    } else {
      html.classList.remove('dark');
    }
    
    // Update button appearance
    if (themeIcon && themeText) {
      themeIcon.innerHTML = themes[theme].icon;
      themeText.textContent = themes[theme].name;
    }
  };
  
  const nextTheme = (current) => {
    const order = ['system', 'light', 'dark'];
    const currentIndex = order.indexOf(current);
    return order[(currentIndex + 1) % order.length];
  };
  
  themeToggle?.addEventListener('click', () => {
    const newTheme = nextTheme(currentTheme);
    currentTheme = newTheme;
    localStorage.setItem('ytv2.theme', newTheme);
    applyTheme(newTheme);
  });
  
  // System theme change listener
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (currentTheme === 'system') {
      applyTheme('system');
    }
  });
  
  // Hide audio player if no audio file (but never hide metadata/thumbnail)
  const audioSource = player?.querySelector('source');
  const hasAudioSrc = audioSource && audioSource.src && audioSource.src.trim() !== '';
  
  console.log('[V2 Debug] Audio element check:', {
    hasPlayer: !!player,
    hasSource: !!audioSource,
    srcValue: audioSource?.src,
    hasValidSrc: hasAudioSrc
  });
  
  if (player && !hasAudioSrc) {
    // No audio source - find and hide only the specific audio player section
    const audioPlayerSection = player.closest('section');
    if (audioPlayerSection) {
      audioPlayerSection.style.display = 'none';
      console.log('[V2 Debug] No valid audio source found, hiding only audio player section');
    }
    // Also hide sticky player
    if (sticky) {
      sticky.style.display = 'none';
    }
  } else if (hasAudioSrc) {
    console.log('[V2 Debug] Valid audio source found:', audioSource.src);
  }
  
  // init
  applyTheme(currentTheme);
  updateButtons();
  updateTime();
  maybeShowSticky();
  initSummaryVariants();
})();
