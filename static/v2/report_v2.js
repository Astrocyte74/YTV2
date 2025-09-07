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

  const sticky = $("stickyBar");
  const mPlayPause = $("mPlayPause");
  const mTimeMeta = $("mTimeMeta");
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
    timeMeta.textContent = `${fmt(cur)} / ${fmt(dur)}`;
    mTimeMeta.textContent = `${fmt(cur)} / ${fmt(dur)}`;
    if (dur > 0) seek.value = Math.round((cur / dur) * 100);
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
  playPause.addEventListener("click", () => {
    console.log('[V2 Telemetry] play_clicked', { was_paused: player.paused });
    if (player.paused) player.play(); else player.pause();
  });
  mPlayPause.addEventListener("click", () => {
    if (player.paused) player.play(); else player.pause();
  });

  rateBtn?.addEventListener("click", () => {
    rIdx = (rIdx + 1) % rates.length;
    player.playbackRate = rates[rIdx];
    rateBtn.textContent = `${rates[rIdx]}×`;
  });

  seek.addEventListener("input", () => {
    const dur = player.duration || 0;
    player.currentTime = (seek.value / 100) * dur;
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

  // init
  updateButtons();
  updateTime();
  maybeShowSticky();
})();