(() => {
  // Simple telemetry logging
  const isMobile = window.innerWidth <= 768;
  console.log('[V2 Telemetry] v2_rendered', { ua_is_mobile: isMobile, viewport: `${window.innerWidth}x${window.innerHeight}` });

  const $ = (id) => document.getElementById(id);

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
  if (player && (!player.querySelector('source') || !player.querySelector('source').src)) {
    // No audio source - find and hide only the specific audio player section
    const audioPlayerSection = player.closest('section');
    if (audioPlayerSection) {
      audioPlayerSection.style.display = 'none';
      console.log('[V2 Debug] No audio source found, hiding only audio player section');
    }
    // Also hide sticky player
    if (sticky) {
      sticky.style.display = 'none';
    }
  } else {
    console.log('[V2 Debug] Audio source found:', player?.querySelector('source')?.src);
  }
  
  // init
  applyTheme(currentTheme);
  updateButtons();
  updateTime();
  maybeShowSticky();
})();