/**
 * YTV2 Dashboard V3 - Audio-Centric Interface
 * Phase 3 implementation with integrated audio player and modern UX
 */

class AudioDashboard {
    constructor() {
        this.currentAudio = null;
        this.playlist = [];
        this.currentTrackIndex = -1;
        this.isPlaying = false;
        // Read UI feature flags (non-breaking if missing)
        this.flags = (typeof window !== 'undefined' && window.UI_FLAGS) ? window.UI_FLAGS : {};
        this.currentFilters = {};
        this.currentPage = 1;
        this.currentSort = 'newest';
        this.searchQuery = '';
        this.viewMode = (localStorage.getItem('ytv2.viewMode') || 'list');
        // Inline expand state
        this.currentExpandedId = null;
        // Queue persistence key (Phase 3)
        this.queueKey = 'ytv2.queue';
        // Telemetry buffer
        this.telemetryBuf = [];
        this.telemetryFlushTimer = null;
        
        this.initializeElements();
        this.bindEvents();
        this.loadInitialData();
    }

    initializeElements() {
        // Audio elements
        this.audioElement = document.getElementById('audioElement');
        // Bottom container removed; mini player is always visible in sidebar
        this.audioPlayerContainer = null;
        
        // Player controls
        this.playPauseBtn = document.getElementById('playPauseBtn');
        this.playIcon = document.getElementById('playIcon');
        this.pauseIcon = document.getElementById('pauseIcon');
        this.prevBtn = document.getElementById('prevBtn');
        this.nextBtn = document.getElementById('nextBtn');
        this.progressContainer = document.getElementById('progressContainer');
        this.progressBar = document.getElementById('progressBar');
        this.currentTimeEl = document.getElementById('currentTime');
        this.totalTimeEl = document.getElementById('totalTime');
        this.volumeBtn = document.getElementById('volumeBtn');
        this.volumeOnIcon = document.getElementById('volumeOnIcon');
        this.volumeOffIcon = document.getElementById('volumeOffIcon');
        
        // Player info
        // Legacy bottom-player ids not present anymore; keep null-safe
        this.playerTitle = document.getElementById('playerTitle');
        this.playerMeta = document.getElementById('playerMeta');
        
        // Search and filters
        this.searchInput = document.getElementById('searchInput');
        this.sortToolbar = document.getElementById('sortToolbar');
        this.categoryFilters = document.getElementById('categoryFilters');
        this.contentTypeFilters = document.getElementById('contentTypeFilters');
        this.complexityFilters = document.getElementById('complexityFilters');
        
        // Content area
        this.contentGrid = document.getElementById('contentGrid');
        this.resultsTitle = document.getElementById('resultsTitle');
        this.resultsCount = document.getElementById('resultsCount');
        this.pagination = document.getElementById('pagination');
        this.listViewBtn = document.getElementById('listViewBtn');
        this.gridViewBtn = document.getElementById('gridViewBtn');
        
        // Queue
        this.queueSidebar = document.getElementById('queueSidebar');
        this.queueToggle = document.getElementById('queueToggle');
        this.audioQueue = document.getElementById('audioQueue');
        this.queueClearBtn = document.getElementById('queueClearBtn');
        this.nowPlayingPreview = document.getElementById('nowPlayingPreview');
        this.nowPlayingThumb = document.getElementById('nowPlayingThumb');
        this.nowPlayingTitle = document.getElementById('nowPlayingTitle');
        this.nowPlayingMeta = document.getElementById('nowPlayingMeta');
        this.nowPlayingProgress = document.getElementById('nowPlayingProgress');

        // Delete modal
        this.confirmModal = document.getElementById('confirmModal');
        this.confirmText = document.getElementById('confirmText');
        this.cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
        this.confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
        this.pendingDelete = null; // {stem, title}
        // Settings / theme
        this.settingsToggle = document.getElementById('settingsToggle');
        this.settingsMenu = document.getElementById('settingsMenu');
        this.themeButtons = this.settingsMenu ? this.settingsMenu.querySelectorAll('[data-theme]') : [];
        this.themeMode = localStorage.getItem('ytv2.theme') || 'system';
    }

    bindEvents() {
        // Audio events
        this.audioElement.addEventListener('loadedmetadata', () => this.updateDuration());
        this.audioElement.addEventListener('timeupdate', () => this.updateProgress());
        this.audioElement.addEventListener('ended', () => this.playNext('auto'));
        this.audioElement.addEventListener('canplay', () => this.handleCanPlay());
        this.audioElement.addEventListener('error', () => this.handleAudioError());
        
        // Player controls
        this.playPauseBtn.addEventListener('click', () => this.togglePlayPause());
        this.prevBtn.addEventListener('click', () => this.playPrevious());
        this.nextBtn.addEventListener('click', () => this.playNext());
        this.progressContainer.addEventListener('click', (e) => this.seekTo(e));
        if (this.volumeBtn) this.volumeBtn.addEventListener('click', () => this.toggleMute());
        if (this.settingsToggle) this.settingsToggle.addEventListener('click', (e) => { e.stopPropagation(); this.toggleSettings(); });
        if (this.settingsMenu) document.addEventListener('click', (e) => { if (!e.target.closest('#settingsMenu') && !e.target.closest('#settingsToggle')) this.closeSettings(); });
        if (this.themeButtons) this.themeButtons.forEach(btn => btn.addEventListener('click', () => this.setTheme(btn.dataset.theme)));
        if (this.cancelDeleteBtn) this.cancelDeleteBtn.addEventListener('click', () => this.closeConfirm());
        if (this.confirmDeleteBtn) this.confirmDeleteBtn.addEventListener('click', () => this.confirmDelete());
        
        // Search and filters
        this.searchInput.addEventListener('input', 
            this.debounce(() => this.handleSearch(), 500));
        if (this.sortToolbar) {
            this.sortToolbar.querySelectorAll('[data-sort]').forEach(btn => {
                btn.addEventListener('click', () => this.setSortMode(btn.dataset.sort));
            });
        }
        
        // UI controls
        this.queueToggle.addEventListener('click', () => this.toggleQueue());
        if (this.queueClearBtn) this.queueClearBtn.addEventListener('click', () => this.clearQueue());
        // Play All button removed - auto-playlist handles this
        if (this.listViewBtn) this.listViewBtn.addEventListener('click', () => this.setViewMode('list'));
        if (this.gridViewBtn) this.gridViewBtn.addEventListener('click', () => this.setViewMode('grid'));
        this.updateViewToggle();
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
        this.audioElement.addEventListener('volumechange', () => this.updateMuteIcon());

        // Delegated card actions
        if (this.contentGrid) {
            this.contentGrid.addEventListener('click', (e) => this.onClickCardAction(e));
        }
        // URL hash handling for deep links
        window.addEventListener('hashchange', () => this.onHashChange());
        // Telemetry flush on unload/hidden
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden' && this.telemetryBuf && this.telemetryBuf.length) {
                try {
                    const payload = { batch: this.telemetryBuf, ts: Date.now() };
                    const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
                    if (navigator.sendBeacon) navigator.sendBeacon('/api/telemetry', blob);
                } catch (_) {
                    // ignore
                } finally {
                    this.telemetryBuf = [];
                }
            }
        });
    }

    async loadInitialData() {
        try {
            // Apply theme at startup
            this.applyTheme(this.themeMode);
            this.updateThemeChecks();
            await Promise.all([
                this.loadFilters(),
                this.loadContent()
            ]);
            // Queue UI visibility based on flag
            if (this.queueSidebar) {
                if (this.flags.queueEnabled) this.queueSidebar.classList.remove('hidden');
                else this.queueSidebar.classList.add('hidden');
            }
            if (this.queueToggle) {
                if (!this.flags.queueEnabled) this.queueToggle.classList.add('hidden');
                else this.queueToggle.classList.remove('hidden');
            }
            // Restore queue if enabled
            if (this.flags.queueEnabled) {
                this.restoreQueue();
            }
            // Default select first item (do not autoplay)
            if (!this.currentAudio && this.currentItems && this.currentItems.length > 0) {
                const first = this.currentItems[0];
                this.setCurrentFromItem(first);
            }
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showError('Failed to load dashboard data');
        }
    }

    // Settings / Theme
    toggleSettings() { if (!this.settingsMenu) return; this.settingsMenu.classList.toggle('hidden'); }
    closeSettings() { if (!this.settingsMenu) return; this.settingsMenu.classList.add('hidden'); }
    setTheme(mode) { 
        this.themeMode = mode || 'system'; 
        localStorage.setItem('ytv2.theme', this.themeMode); 
        this.applyTheme(this.themeMode); 
        this.updateThemeChecks(); 
    }
    
    applyTheme(mode) {
        const root = document.documentElement;
        const mq = window.matchMedia('(prefers-color-scheme: dark)');
        const wantsDark = mode === 'dark' || (mode === 'system' && mq.matches);
        
        // Apply dark class to root element
        root.classList.toggle('dark', wantsDark);
        
        // Bind media query listener for system mode
        if (!this._mqBound) { 
            mq.addEventListener('change', () => { 
                if ((localStorage.getItem('ytv2.theme') || 'system') === 'system') {
                    this.applyTheme('system'); 
                }
            }); 
            this._mqBound = true; 
        }
    }
    updateThemeChecks() {
        ['system', 'light', 'dark'].forEach(k => {
            const el = document.getElementById(`themeCheck-${k}`);
            if (el) {
                el.textContent = (k === this.themeMode) ? '✓' : '';
            }
        });
    }

    async loadFilters() {
        try {
            const response = await fetch('/api/filters');
            const filters = await response.json();
            
            this.renderFilterSection(filters.category, this.categoryFilters, 'category');
            this.renderFilterSection(filters.content_type, this.contentTypeFilters, 'content_type');
            this.renderFilterSection(filters.complexity_level, this.complexityFilters, 'complexity');
        } catch (error) {
            console.error('Failed to load filters:', error);
        }
    }

    renderFilterSection(items, container, filterType) {
        container.innerHTML = items.slice(0, 8).map(item => `
            <label class="flex items-center space-x-2 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700 rounded px-2 py-1 transition-colors">
                <input type="checkbox" 
                       value="${this.escapeHtml(item.value)}" 
                       data-filter="${filterType}"
                       class="rounded border-slate-300 dark:border-slate-600 text-audio-500 focus:ring-audio-500 focus:ring-offset-0">
                <span class="text-sm text-slate-700 dark:text-slate-200 flex-1">${this.escapeHtml(item.value)}</span>
                <span class="text-xs text-slate-400 dark:text-slate-500">${item.count}</span>
            </label>
        `).join('');

        // Bind filter change events
        container.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', () => this.handleFilterChange());
        });
    }

    async loadContent() {
        const params = new URLSearchParams();
        
        // Add search query
        if (this.searchQuery) params.append('q', this.searchQuery);
        
        // Add filters
        Object.entries(this.currentFilters).forEach(([key, values]) => {
            values.forEach(value => params.append(key, value));
        });
        
        // Add pagination and sorting
        params.append('page', this.currentPage.toString());
        params.append('size', '12'); // Show 12 items per page
        params.append('sort', this.currentSort);

        try {
            const response = await fetch(`/api/reports?${params}`);
            const data = await response.json();
            this.currentItems = data.data;
            this.renderContent(this.currentItems);
            this.renderPagination(data.pagination);
            this.updateResultsInfo(data.pagination);
            // Default playlist and current item (no autoplay)
            if (this.currentItems && this.currentItems.length > 0) {
                this.playlist = this.currentItems.map(i => i.file_stem);
                this.currentTrackIndex = 0;
                this.setCurrentFromItem(this.currentItems[0]);
            }
        } catch (error) {
            console.error('Failed to load content:', error);
            this.showError('Failed to load content');
        }
    }

    renderContent(items) {
        const html = this.viewMode === 'grid'
            ? `<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">${items.map(i => this.createGridCard(i)).join('')}</div>`
            : items.map(i => this.createContentCard(i)).join('');
        this.contentGrid.innerHTML = html;

        // Make whole card clickable (except controls)
        this.contentGrid.querySelectorAll('[data-card]').forEach(card => {
            card.addEventListener('click', (e) => {
                // Ignore if click on a control
                if (e.target.closest('[data-control]') || e.target.closest('[data-action]')) return;
                const href = card.dataset.href;
                if (href) window.location.href = href;
            });
            card.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    const href = card.dataset.href;
                    if (href) window.location.href = href;
                }
            });
        });

        // Highlight currently playing
        this.updatePlayingCard();

        // Apply deep-link expansion if present
        this.applyHashDeepLink();

        // After render, ensure currentAudio still exists; if not, advance or clear
        if (this.currentAudio) {
            const exists = (this.currentItems || []).some(x => x.file_stem === this.currentAudio.id && x.media?.has_audio);
            if (!exists) {
                if (this.playlist && this.playlist.length > 1) this.playNext('auto');
                else { this.audioElement.pause(); this.isPlaying = false; this.currentAudio = null; this.updatePlayButton(); this.updateNowPlayingPreview(); }
            }
        }
    }

    onClickCardAction(e) {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const card = btn.closest('[data-report-id]');
        if (!card) return;
        e.stopPropagation();
        if (btn.dataset.busy) return;
        btn.dataset.busy = '1';
        setTimeout(() => { try { delete btn.dataset.busy; } catch(_){} }, 400);
        const action = btn.dataset.action;
        const id = card.dataset.reportId;
        if (action === 'listen') {
            const hasAudio = card.getAttribute('data-has-audio') === 'true';
            if (!hasAudio) { this.showToast('No audio for this item', 'warn'); return; }
            this.playAudio(id);
            this.sendTelemetry('cta_listen', { id });
        }
        if (action === 'read') { this.handleRead(id); this.sendTelemetry('cta_read', { id }); }
        if (action === 'watch') { this.openYoutube(card.dataset.videoId); this.sendTelemetry('cta_watch', { id, video_id: card.dataset.videoId }); }
        if (action === 'delete') { this._lastDeleteTrigger = btn; this.toggleDeletePopover(card, true); }
        if (action === 'menu') { this.toggleKebabMenu(card, true, btn); }
        if (action === 'menu-close') { this.toggleKebabMenu(card, false); }
        if (action === 'copy-link') { this.copyLink(card, id); this.toggleKebabMenu(card, false); }
        if (action === 'confirm-delete') { this.handleDelete(id, card); this.sendTelemetry('cta_delete', { id }); }
        if (action === 'cancel-delete') this.toggleDeletePopover(card, false);
        if (action === 'collapse') this.collapseCardInline(id);
    }

    handleRead(id) {
        if (this.flags.cardExpandInline) {
            if (this.currentExpandedId === id) {
                return this.collapseCardInline(id);
            }
            return this.expandCardInline(id);
        }
        const href = `/${id}.json?v=2`;
        window.location.href = href;
    }

    openYoutube(videoId) {
        if (!videoId) {
            this.showToast('No YouTube link available', 'warn');
            return;
        }
        const url = `https://www.youtube.com/watch?v=${videoId}`;
        window.open(url, '_blank');
    }

    async expandCardInline(id) {
        const card = this.contentGrid.querySelector(`[data-report-id="${id}"]`);
        if (!card) return;
        // Collapse any other expanded
        if (this.currentExpandedId && this.currentExpandedId !== id) {
            this.collapseCardInline(this.currentExpandedId);
        }
        const region = this.ensureExpandRegion(card);
        if (!region) return;

        // If already visible, do nothing
        if (!region.hasAttribute('hidden')) return;

        // Load content
        region.innerHTML = this.renderExpandedSkeleton();
        // Set id and control linkage
        if (!region.id) region.id = `expand-${id}`;
        const readBtn = card.querySelector('[data-action="read"]');
        if (readBtn) { readBtn.setAttribute('aria-controls', region.id); readBtn.setAttribute('aria-expanded', 'true'); }
        this.showRegion(region, true);
        // Update URL hash
        this.updateHash(id);
        this.currentExpandedId = id;
        // Fetch details
        try {
            // Try API endpoints first (both plural and singular), tolerant of non-JSON responses.
            const apiUrls = [`/api/reports/${id}`, `/api/report/${id}`];
            let data = null, ok = false;
            for (const url of apiUrls) {
                try {
                    const res = await fetch(url, { credentials: 'same-origin' });
                    if (!res.ok) continue;
                    const text = await res.text();
                    const t = text.trim();
                    if (t.startsWith('<')) continue; // clearly not JSON (HTML error page)
                    try { data = JSON.parse(text); ok = true; break; } catch { /* not JSON; try next */ }
                } catch { /* network; try next */ }
            }
            // Fallback to static JSON report (already supported by the app)
            if (!ok) {
                try {
                    const res = await fetch(`/${encodeURIComponent(id)}.json?v=2`, { credentials: 'same-origin' });
                    if (res.ok) { data = await res.json(); ok = true; }
                } catch { /* ignore */ }
            }
            if (!ok || !data) throw new Error('No detail available');
            region.innerHTML = this.renderExpandedContent(data);
            // Focus expanded wrapper for a11y (title is sr-only)
            const wrapper = region.querySelector('[data-expanded]');
            if (wrapper) {
                wrapper.setAttribute('tabindex', '-1');
                try { wrapper.focus({ preventScroll: true }); } catch(_) { wrapper.focus(); }
            }
        } catch (err) {
            console.error('Failed to load report', err);
            region.innerHTML = `<div class="mt-3 rounded-xl bg-red-50 border border-red-200 text-red-700 p-4">Failed to load summary.</div>`;
        }
        // Scroll into view (less jumpy)
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    collapseCardInline(id) {
        const card = this.contentGrid.querySelector(`[data-report-id="${id}"]`);
        if (!card) return;
        const region = card.querySelector('[data-expand-region]');
        if (!region) { this.currentExpandedId = null; this.updateHash(''); return; }
        this.showRegion(region, false);
        const readBtn = card.querySelector('[data-action="read"]');
        if (readBtn) readBtn.setAttribute('aria-expanded', 'false');
        if (this.currentExpandedId === id) this.currentExpandedId = null;
        // If current hash targets this id, go back to clear hash so Back button collapses naturally
        const target = this.parseHash();
        if (target === id) {
            try { history.back(); } catch (_) { this.updateHash(''); }
        }
    }

    ensureExpandRegion(card) {
        let region = card.querySelector('[data-expand-region]');
        if (!region) {
            region = document.createElement('section');
            region.setAttribute('role', 'region');
            region.setAttribute('aria-live', 'polite');
            region.setAttribute('hidden', '');
            region.dataset.expandRegion = '';
            // Insert near bottom inside card content
            const container = card.querySelector('.flex-1.min-w-0') || card;
            container.appendChild(region);
        }
        return region;
    }

    showRegion(region, show) {
        if (show) {
            region.hidden = false;
            region.style.overflow = 'hidden';
            region.style.maxHeight = '0px';
            region.style.opacity = '0';
            region.offsetHeight; // reflow
            region.style.transition = 'max-height 250ms ease, opacity 200ms ease';
            region.style.maxHeight = region.scrollHeight + 'px';
            region.style.opacity = '1';
            setTimeout(() => {
                region.style.maxHeight = '';
                region.style.overflow = '';
            }, 260);
        } else {
            region.style.overflow = 'hidden';
            region.style.maxHeight = region.scrollHeight + 'px';
            region.offsetHeight;
            region.style.transition = 'max-height 220ms ease, opacity 200ms ease';
            region.style.maxHeight = '0px';
            region.style.opacity = '0';
            setTimeout(() => {
                region.hidden = true;
                region.style.maxHeight = '';
                region.style.opacity = '';
                region.style.overflow = '';
            }, 230);
        }
    }

    renderExpandedSkeleton() {
        return `
          <div class="mt-3 rounded-xl bg-white/70 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 p-4 w-full md:mx-0">
            <div class="h-4 bg-slate-200 dark:bg-slate-700 rounded w-1/2 mb-3"></div>
            <div class="space-y-2">
              <div class="h-3 bg-slate-200 dark:bg-slate-700 rounded"></div>
              <div class="h-3 bg-slate-200 dark:bg-slate-700 rounded w-5/6"></div>
              <div class="h-3 bg-slate-200 dark:bg-slate-700 rounded w-2/3"></div>
            </div>
          </div>`;
    }

    renderExpandedContent(data) {
        // Badges (omit duration here)
        const badges = [];
        if (data.channel) badges.push(`<span class="px-2 py-0.5 rounded bg-slate-700/50 text-slate-200 text-xs">${this.escapeHtml(data.channel)}</span>`);
        if (data.language) badges.push(`<span class="px-2 py-0.5 rounded bg-slate-700/50 text-slate-200 text-xs">${this.escapeHtml(data.language)}</span>`);

        // Tolerant summary extraction across shapes - handle NEW and OLD formats
        let summaryRaw = '';
        if (typeof data.summary === 'string') {
            summaryRaw = data.summary;
        } else if (data.summary && typeof data.summary === 'object') {
            // Try NEW format first (summary.summary)
            if (typeof data.summary.summary === 'string') {
                summaryRaw = data.summary.summary;
            }
            // Then try OLD format (summary.content.*)
            else if (typeof data.summary.content === 'string') {
                summaryRaw = data.summary.content;
            }
            else if (data.summary.content && typeof data.summary.content.summary === 'string') {
                summaryRaw = data.summary.content.summary;
            }
            else if (data.summary.content && typeof data.summary.content.audio === 'string') {
                summaryRaw = data.summary.content.audio;
            }
            else if (data.summary.content && typeof data.summary.content.comprehensive === 'string') {
                summaryRaw = data.summary.content.comprehensive;
            }
            else if (Array.isArray(data.summary.content)) {
                summaryRaw = data.summary.content.join('\n');
            }
        }
        if (!summaryRaw) summaryRaw = data.analysis?.summary || data.analysis?.summary_text || data.summary_preview || '';
        // Additional fallbacks: bullets / key points arrays
        if (!summaryRaw && Array.isArray(data.summary?.bullets)) {
            summaryRaw = data.summary.bullets
                .map(b => (typeof b === 'string' ? `• ${b}` : ''))
                .filter(Boolean)
                .join('\n');
        }
        if (!summaryRaw && Array.isArray(data.analysis?.key_points)) {
            summaryRaw = data.analysis.key_points.map(b => typeof b === 'string' ? `• ${b}` : '').filter(Boolean).join('\n');
        }
        if (typeof summaryRaw !== 'string') {
            try { summaryRaw = String(summaryRaw.summary || ''); } catch (_) {}
        }
        if (typeof summaryRaw !== 'string') {
            try { summaryRaw = JSON.stringify(summaryRaw); } catch (_) { summaryRaw = ''; }
        }
        // Normalize and trim, collapse blank lines
        summaryRaw = String(summaryRaw).replace(/\r\n?/g, '\n').trim();
        const summary = summaryRaw
            .split('\n')
            .map(s => s.trim())
            .filter(Boolean)
            .map(p => `<p>${this.escapeHtml(p)}</p>`)
            .join('') || '<p>No summary available.</p>';

        return `
          <div class="mt-3 rounded-xl bg-white/80 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 p-4 space-y-4 w-full md:mx-0" data-expanded>
            ${badges.length ? `<div class="flex items-center gap-2 text-slate-600 dark:text-slate-300 text-sm flex-wrap">${badges.join('')}</div>` : ''}
            <h4 class="sr-only" data-expanded-title>Summary</h4>
            <div class="prose prose-sm prose-slate dark:prose-invert max-w-none leading-6 w-full break-words">${summary}</div>
            <div class="flex items-center justify-end">
              <button class="ybtn ybtn-ghost px-3 py-1.5 rounded-md" data-action="collapse">Collapse</button>
            </div>
          </div>`;
    }

    updateHash(id) {
        if (!id) {
            history.pushState('', document.title, window.location.pathname + window.location.search);
            return;
        }
        const newHash = `#report=${encodeURIComponent(id)}`;
        if (window.location.hash !== newHash) {
            window.location.hash = newHash;
        }
    }

    parseHash() {
        const h = window.location.hash || '';
        const m = h.match(/^#report=([^&]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    onHashChange() {
        const id = this.parseHash();
        if (id) {
            this.expandCardInline(id);
        } else if (this.currentExpandedId) {
            const prev = this.currentExpandedId;
            this.collapseCardInline(prev);
        }
    }

    applyHashDeepLink() {
        const id = this.parseHash();
        if (!id) return;
        if (this.flags.cardExpandInline) {
            const card = this.contentGrid.querySelector(`[data-report-id="${id}"]`);
            if (card) this.expandCardInline(id);
        }
    }

    toggleDeletePopover(card, show) {
        const pop = card.querySelector('[data-delete-popover]');
        if (!pop) return;
        if (show) {
            pop.setAttribute('role', 'dialog');
            pop.setAttribute('aria-modal', 'true');
            pop.classList.remove('hidden');
            // focus first button
            const firstBtn = pop.querySelector('button');
            if (firstBtn) firstBtn.focus();
        } else {
            pop.classList.add('hidden');
            // restore focus
            if (this._lastDeleteTrigger && this._lastDeleteTrigger.focus) {
                this._lastDeleteTrigger.focus();
            }
        }
    }

    toggleKebabMenu(card, show, trigger) {
        const menu = card.querySelector('[data-kebab-menu]');
        const btn  = trigger || card.querySelector('[data-action="menu"]');
        if (!menu || !btn) return;
        const setExpanded = (val) => btn.setAttribute('aria-expanded', val ? 'true' : 'false');
        if (show) {
            // Close any other open menus globally
            try { document.querySelectorAll('[data-kebab-menu]:not(.hidden)').forEach(m => m.classList.add('hidden')); } catch(_) {}
            setExpanded(true);
            menu.classList.remove('hidden');
            menu.setAttribute('role', 'menu');
            this._lastMenuTrigger = btn;
            const first = menu.querySelector('[role="menuitem"],button');
            if (first) first.focus();
            const close = () => {
                menu.classList.add('hidden');
                setExpanded(false);
                document.removeEventListener('keydown', onKey, true);
                document.removeEventListener('click', onClickAway, true);
                btn.focus();
            };
            const onKey = (e) => { if (e.key === 'Escape') close(); };
            const onClickAway = (e) => {
                if (!e.target.closest('[data-kebab-menu]') && !e.target.closest('[data-action="menu"]')) close();
            };
            this._menuCleanup = () => close();
            setTimeout(() => {
                document.addEventListener('keydown', onKey, true);
                document.addEventListener('click', onClickAway, true);
            }, 0);
        } else {
            menu.classList.add('hidden');
            setExpanded(false);
            if (this._menuCleanup) this._menuCleanup();
        }
    }

    async copyLink(card, id) {
        try {
            const url = `${location.origin}/${encodeURIComponent(id)}.json?v=2`;
            await navigator.clipboard.writeText(url);
            this.showToast('Link copied');
        } catch (e) {
            this.showToast('Copy failed', 'warn');
        }
    }

    async handleDelete(id, cardEl) {
        try {
            // Optimistic UI: show busy state
            const pop = cardEl.querySelector('[data-delete-popover]');
            if (pop) pop.classList.add('pointer-events-none', 'opacity-60');
            const res = await fetch('/api/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: [id] })
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            await res.json();
            // Smooth remove
            cardEl.classList.add('transition', 'duration-200', 'ease-out', 'opacity-0', 'scale-95');
            setTimeout(() => {
                cardEl.remove();
                this.showToast('Deleted successfully', 'success');
            }, 200);
            // Ask server to refresh
            fetch('/api/refresh').catch(() => {});
        } catch (err) {
            console.error('Delete failed', err);
            this.showToast('Delete failed', 'error');
        } finally {
            this.toggleDeletePopover(cardEl, false);
        }
    }

    openConfirm(stem, title) {
        this.pendingDelete = { stem, title };
        if (this.confirmText) this.confirmText.textContent = `Delete "${title}" and its audio?`;
        if (this.confirmModal) {
            this.confirmModal.classList.remove('hidden');
            this.confirmModal.classList.add('flex');
        }
    }

    closeConfirm() {
        if (this.confirmModal) {
            this.confirmModal.classList.add('hidden');
            this.confirmModal.classList.remove('flex');
        }
        this.pendingDelete = null;
    }

    async confirmDelete() {
        if (!this.pendingDelete) return;
        const stem = this.pendingDelete.stem;
        try {
            // Optional admin secret (if set manually in localStorage)
            const adminSecret = localStorage.getItem('ytv2.adminSecret') || '';
            const res = await fetch('/delete-reports', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(adminSecret ? { 'X-Sync-Secret': adminSecret } : {})
                },
                body: JSON.stringify({ files: [stem], delete_audio: true })
            });
            // If 401 and we were using a stored key, clear it silently
            if (res.status === 401) {
                if (adminSecret) localStorage.removeItem('ytv2.adminSecret');
                alert('Unauthorized (delete key invalid). Set localStorage ytv2.adminSecret if needed.');
                return;
            }
            await res.json();
            await fetch('/api/refresh');
            this.closeConfirm();
            this.loadContent();
        } catch (e) {
            console.error('Delete failed', e);
            alert('Delete failed: ' + (e?.message || e));
        }
    }

    createContentCard(item) {
        const duration = this.formatDuration(item.duration_seconds || 0);
        const categories = item.analysis?.category?.slice(0, 2) || ['General'];
        const hasAudio = item.media?.has_audio;
        const href = `/${item.file_stem}.json?v=2`;
        
        const isPlaying = this.currentAudio && this.currentAudio.id === item.file_stem && this.isPlaying;
        const channelInitial = (item.channel || '?').trim().charAt(0).toUpperCase();
        return `
            <div data-card data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-has-audio="${hasAudio ? 'true' : 'false'}" data-href="${href}" title="Open summary" tabindex="0" class="group relative list-layout cursor-pointer bg-white/80 dark:bg-slate-800/60 backdrop-blur-sm rounded-xl border border-slate-200/60 dark:border-slate-700 p-4 hover:bg-white dark:hover:bg-slate-800 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200" style="--thumbW: 240px;">
                <div class="flex gap-4 items-start">
                    <div class="relative w-56 aspect-video overflow-hidden rounded-lg bg-slate-100 flex-shrink-0">
                        ${item.thumbnail_url ? `<img src="${item.thumbnail_url}" alt="thumbnail" loading="lazy" class="absolute inset-0 w-full h-full object-cover">` : ''}
                        <div class="absolute inset-x-0 bottom-0 h-1 bg-black/20">
                            <div class="h-1 bg-audio-500" style="width:0%" data-card-progress role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
                        </div>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-start justify-between gap-3">
                            <div class="flex-1 min-w-0">
                                <h3 class="text-lg font-semibold text-slate-800 dark:text-slate-100 group-hover:text-audio-700 transition-colors line-clamp-2">
                                    ${this.escapeHtml(item.title)}
                                </h3>
                                <div class="text-sm text-slate-500 dark:text-slate-300 mt-0.5 line-clamp-1 flex items-center gap-2">
                                    <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 text-slate-700 text-[10px]">${channelInitial}</span>
                                    ${this.escapeHtml(item.channel || '')}
                                    ${isPlaying ? '<span class="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-audio-100 text-audio-700">Now Playing</span>' : ''}
                                </div>
                                <div class="mt-1 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                                    <span>🎬 ${duration}</span>
                                    ${item.media?.audio_duration_seconds ? `<span>•</span><span>🎵 ${this.formatDuration(item.media.audio_duration_seconds)}</span>` : ''}
                                    <span>•</span>
                                    <span>${item.analysis?.complexity_level || 'Intermediate'}</span>
                                    <span>•</span>
                                    <span>${item.analysis?.language || 'en'}</span>
                                </div>
                            </div>
                            <div class="absolute top-3 right-3">
                              <button class="p-2 rounded-md hover:bg-slate-200/60 dark:hover:bg-slate-700/60" data-action="menu" aria-label="More options" aria-haspopup="menu" aria-expanded="false">
                                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>
                              </button>
                              <div class="absolute right-0 mt-2 w-44 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg hidden z-10" data-kebab-menu role="menu">
                                <button class="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors" role="menuitem" data-action="copy-link">Copy link</button>
                                <button class="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors" role="menuitem" data-action="delete">Delete…</button>
                              </div>
                            </div>
                            <div class="absolute top-12 right-3 hidden z-10" data-delete-popover>
                              <div class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-3 text-sm">
                                <div class="mb-2 text-slate-700 dark:text-slate-200">Delete this summary?</div>
                                <div class="flex items-center gap-2 justify-end">
                                  <button class="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700" data-action="cancel-delete">Cancel</button>
                                  <button class="px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700" data-action="confirm-delete">Delete</button>
                                </div>
                              </div>
                            </div>
                        </div>

                        <div class="mt-3 flex flex-wrap gap-2">
                            ${categories.map(cat => `
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-audio-100 dark:bg-slate-700 text-audio-800 dark:text-slate-300">${this.escapeHtml(cat)}</span>
                            `).join('')}
                        </div>
                        <!-- CTA row under meta -->
                        <div class="mt-3 flex items-center gap-2 text-sm">
                          <button class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-slate-300/60 dark:border-slate-600/60 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-slate-700 dark:text-slate-200 font-medium" data-action="read"><span>Read</span><span aria-hidden="true">›</span></button>
                          ${hasAudio ? `<button class=\"inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-slate-300/60 dark:border-slate-600/60 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-slate-700 dark:text-slate-200 font-medium\" data-action=\"listen\"><span>Listen</span><span aria-hidden=\"true\">›</span></button>` : ''}
                          <button class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-slate-300/60 dark:border-slate-600/60 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-slate-700 dark:text-slate-200 font-medium" data-action="watch"><span>Watch</span><span aria-hidden="true">›</span></button>
                        </div>

                        <section role="region" aria-live="polite" hidden data-expand-region></section>
                    </div>
                </div>
            </div>
        `;
    }

    createGridCard(item) {
        const duration = this.formatDuration(item.duration_seconds || 0);
        const href = `/${item.file_stem}.json?v=2`;
        const isPlaying = this.currentAudio && this.currentAudio.id === item.file_stem && this.isPlaying;
        const channelInitial = (item.channel || '?').trim().charAt(0).toUpperCase();
        return `
        <div data-card data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-has-audio="${(item.media && item.media.has_audio) ? 'true' : 'false'}" data-href="${href}" title="Open summary" tabindex="0" class="group relative cursor-pointer bg-white/80 dark:bg-slate-800/60 rounded-xl border border-slate-200/60 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-800 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200 overflow-hidden">
            <div class="relative aspect-video bg-slate-100">
                ${item.thumbnail_url ? `<img src="${item.thumbnail_url}" alt="thumbnail" loading="lazy" class="absolute inset-0 w-full h-full object-cover">` : ''}
                <div class="absolute inset-x-0 bottom-0 h-1 bg-black/20">
                    <div class="h-1 bg-audio-500" style="width:0%" data-card-progress role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
                </div>
                <div class="absolute top-2 right-2">
                  <button class="p-1.5 min-w-[36px] min-h-[36px] rounded-md bg-white/70 dark:bg-slate-900/60 hover:bg-white/90" data-action="menu" aria-label="More options" aria-haspopup="menu" aria-expanded="false">
                    <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>
                  </button>
                  <div class="absolute right-0 mt-2 w-40 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg hidden z-10" data-kebab-menu role="menu">
                    <button class="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors" role="menuitem" data-action="copy-link">Copy link</button>
                    <button class="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors" role="menuitem" data-action="delete">Delete…</button>
                  </div>
                </div>
                <div class="absolute top-10 right-2 hidden z-10" data-delete-popover>
                  <div class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-2 text-xs">
                    <div class="mb-2 text-slate-700 dark:text-slate-200">Delete this summary?</div>
                    <div class="flex items-center gap-2 justify-end">
                      <button class="px-2 py-1 rounded border border-slate-200 dark:border-slate-700" data-action="cancel-delete">Cancel</button>
                      <button class="px-2 py-1 rounded bg-red-600 text-white" data-action="confirm-delete">Delete</button>
                    </div>
                  </div>
                </div>
            </div>
            <div class="p-3">
                <h3 class="text-sm font-semibold text-slate-800 dark:text-slate-100 group-hover:text-audio-700 line-clamp-2">${this.escapeHtml(item.title)}</h3>
                <div class="text-xs text-slate-500 dark:text-slate-300 mt-1 line-clamp-1 flex items-center gap-2">
                    <span class="inline-flex items-center justify-center w-4 h-4 rounded-full bg-slate-200 text-slate-700 text-[9px]">${channelInitial}</span>
                    ${this.escapeHtml(item.channel || '')}
                    ${isPlaying ? '<span class="ml-2 text-[10px] px-1 py-0.5 rounded bg-audio-100 text-audio-700">Now Playing</span>' : ''}
                </div>
                <div class="mt-1 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <span>${duration}</span>
                    <span>•</span>
                    <span>${item.analysis?.language || 'en'}</span>
                </div>
                <div class="mt-2 flex items-center gap-2 text-xs px-3 pb-2">
                    <button class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-slate-300/60 dark:border-slate-600/60 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-slate-700 dark:text-slate-200 font-medium" data-action="read"><span>Read</span><span aria-hidden=\"true\">›</span></button>
                    ${(item.media && item.media.has_audio) ? `<button class=\"inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-slate-300/60 dark:border-slate-600/60 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-slate-700 dark:text-slate-200 font-medium\" data-action=\"listen\"><span>Listen</span><span aria-hidden=\"true\">›</span></button>` : ''}
                    <button class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-slate-300/60 dark:border-slate-600/60 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-slate-700 dark:text-slate-200 font-medium" data-action="watch"><span>Watch</span><span aria-hidden=\"true\">›</span></button>
                </div>
                <section role="region" aria-live="polite" hidden data-expand-region></section>
            </div>
        </div>`;
    }

    renderPagination(pagination) {
        if (pagination.pages <= 1) {
            this.pagination.innerHTML = '';
            return;
        }

        const currentPage = pagination.page;
        const totalPages = pagination.pages;
        const showPages = 5;
        
        let startPage = Math.max(1, currentPage - Math.floor(showPages / 2));
        let endPage = Math.min(totalPages, startPage + showPages - 1);
        
        if (endPage - startPage < showPages - 1) {
            startPage = Math.max(1, endPage - showPages + 1);
        }

        let paginationHTML = '';
        
        // Previous button
        if (currentPage > 1) {
            paginationHTML += `
                <button data-page="${currentPage - 1}" class="px-3 py-2 text-sm text-slate-600 hover:text-audio-600 transition-colors">
                    Previous
                </button>
            `;
        }

        // Page numbers
        for (let i = startPage; i <= endPage; i++) {
            paginationHTML += `
                <button data-page="${i}" 
                        class="px-3 py-2 text-sm ${i === currentPage 
                            ? 'bg-audio-500 text-white' 
                            : 'text-slate-600 hover:text-audio-600'} 
                               rounded-lg transition-colors">
                    ${i}
                </button>
            `;
        }

        // Next button
        if (currentPage < totalPages) {
            paginationHTML += `
                <button data-page="${currentPage + 1}" class="px-3 py-2 text-sm text-slate-600 hover:text-audio-600 transition-colors">
                    Next
                </button>
            `;
        }

        this.pagination.innerHTML = paginationHTML;

        // Bind pagination events
        this.pagination.querySelectorAll('[data-page]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.currentPage = parseInt(e.target.dataset.page);
                this.loadContent();
            });
        });
    }

    updateResultsInfo(pagination) {
        this.resultsTitle.textContent = this.searchQuery 
            ? `Search Results for "${this.searchQuery}"` 
            : 'Discover Audio Content';
        
        this.resultsCount.textContent = 
            `${pagination.total} summaries found • Page ${pagination.page} of ${pagination.pages}`;
    }

    async playAudio(reportId) {
        try {
            // Find the report data
            const reportCard = document.querySelector(`[data-report-id="${reportId}"]`);
            if (!reportCard) return;

            // Extract report info from the card
            const title = reportCard.querySelector('h3').textContent.trim();
            const videoId = reportCard.dataset.videoId;
            // Use server-side resolver to map videoId to latest audio file
            const audioSrc = videoId ? `/exports/by_video/${videoId}.mp3` : `/exports/${reportId}.mp3`;
            
            // Reset per-card progress bars
            try { document.querySelectorAll('[data-card-progress]').forEach(el => { el.style.width = '0%'; el.setAttribute('aria-valuenow', '0'); }); } catch(_) {}
            // Update current track info
            this.currentAudio = {
                id: reportId,
                title: title,
                src: audioSrc
            };

            // Queue management (Phase 3)
            if (this.flags.queueEnabled && Array.isArray(this.currentItems)) {
                this.playlist = this.currentItems.map(i => i.file_stem);
                this.currentTrackIndex = this.playlist.indexOf(reportId);
                if (this.currentTrackIndex < 0) this.currentTrackIndex = 0;
                this.renderQueue();
                this.saveQueue();
            }

            // Update player info
            if (this.nowPlayingTitle) this.nowPlayingTitle.textContent = title;
            if (this.nowPlayingMeta) this.nowPlayingMeta.textContent = 'Loading...';
            const cardImg = reportCard.querySelector('img');
            if (this.nowPlayingThumb && cardImg && cardImg.src) {
                this.nowPlayingThumb.src = cardImg.src;
                this.nowPlayingThumb.classList.remove('hidden');
            }
            
            // Load and play audio (user initiated)
            this.audioElement.src = audioSrc;
            this.audioElement.load();
            this.userInitiatedPlay = true;
            
            // Update now playing preview
            this.updateNowPlayingPreview();
            this.updatePlayingCard();
            
        } catch (error) {
            console.error('Failed to play audio:', error);
            this.showError('Failed to play audio');
        }
    }

    handleAudioError() {
        // Try fallback path if by_video failed
        if (!this.currentAudio) return;
        const src = this.audioElement.currentSrc || this.audioElement.src;
        if (src.includes('/exports/by_video/') && this.currentAudio.id) {
            const fallback = `/exports/${this.currentAudio.id}.mp3`;
            this.audioElement.src = fallback;
            this.audioElement.load();
        }
    }

    togglePlayPause() {
        if (!this.currentAudio) return;

        if (this.isPlaying) {
            this.audioElement.pause();
        } else {
            this.audioElement.play().catch(error => {
                console.error('Playback failed:', error);
                this.showError('Playback failed');
            });
        }
    }

    handleCanPlay() {
        if (this.currentAudio && !this.isPlaying && this.userInitiatedPlay) {
            this.audioElement.play().then(() => {
                this.isPlaying = true;
                this.updatePlayButton();
                this.updatePlayingCard();
            }).catch(error => {
                console.error('Auto-play failed:', error);
            }).finally(() => {
                this.userInitiatedPlay = false;
            });
        }
    }

    updatePlayButton() {
        if (this.isPlaying) {
            this.playIcon.classList.add('hidden');
            this.pauseIcon.classList.remove('hidden');
        } else {
            this.playIcon.classList.remove('hidden');
            this.pauseIcon.classList.add('hidden');
        }
    }

    setViewMode(mode) {
        this.viewMode = mode;
        localStorage.setItem('ytv2.viewMode', mode);
        // Re-render current items
        this.updateViewToggle();
        if (this.currentItems) this.renderContent(this.currentItems);
    }

    updateViewToggle() {
        const active = 'bg-audio-500 text-white';
        const inactive = 'bg-white text-slate-700';
        if (this.listViewBtn && this.gridViewBtn) {
            this.listViewBtn.className = this.listViewBtn.className
                .replace(active, '').replace(inactive, '').trim() + ' ' + (this.viewMode === 'list' ? active : inactive);
            this.gridViewBtn.className = this.gridViewBtn.className
                .replace(active, '').replace(inactive, '').trim() + ' ' + (this.viewMode === 'grid' ? active : inactive);
        }
    }

    setCurrentFromItem(item) {
        const reportId = item.file_stem;
        const title = item.title;
        const videoId = item.video_id;
        const audioSrc = videoId ? `/exports/by_video/${videoId}.mp3` : `/exports/${reportId}.mp3`;
        this.currentAudio = { id: reportId, title, src: audioSrc };
        if (this.nowPlayingTitle) this.nowPlayingTitle.textContent = title;
        if (this.nowPlayingMeta) this.nowPlayingMeta.textContent = 'Ready';
        if (this.nowPlayingThumb && item.thumbnail_url) {
            this.nowPlayingThumb.src = item.thumbnail_url;
            this.nowPlayingThumb.classList.remove('hidden');
        }
        // Do not autoplay here; will load when user hits play
        this.audioElement.src = audioSrc;
        this.audioElement.load();
        this.updateNowPlayingPreview();
        this.updatePlayingCard();
    }

    updatePlayingCard() {
        this.contentGrid.querySelectorAll('[data-card]').forEach(card => {
            card.classList.remove('ring-2', 'ring-audio-400');
        });
        if (this.currentAudio) {
            const active = this.contentGrid.querySelector(`[data-report-id="${this.currentAudio.id}"]`);
            if (active) {
                active.classList.add('ring-2', 'ring-audio-400');
            }
        }
    }

    updateDuration() {
        const duration = this.audioElement.duration;
        if (duration && !isNaN(duration)) {
            if (this.totalTimeEl) this.totalTimeEl.textContent = this.formatDuration(duration);
            if (this.nowPlayingMeta) {
                this.nowPlayingMeta.textContent = `0:00 / ${this.formatDuration(duration)}`;
            }
        }
    }

    updateProgress() {
        const currentTime = this.audioElement.currentTime;
        const duration = this.audioElement.duration;
        
        if (duration && !isNaN(duration) && !isNaN(currentTime)) {
            const progress = (currentTime / duration) * 100;
            this.progressBar.style.width = `${progress}%`;
            this.currentTimeEl.textContent = this.formatDuration(currentTime);
            
            // Update now playing preview
            if (this.nowPlayingProgress) {
                this.nowPlayingProgress.style.width = `${progress}%`;
            }
            if (this.nowPlayingMeta) {
                this.nowPlayingMeta.textContent = `${this.formatDuration(currentTime)} / ${this.formatDuration(duration)}`;
            }
            // Micro progress bar on current card (flagged)
            if (this.currentAudio) {
                const card = document.querySelector(`[data-report-id="${this.currentAudio.id}"]`);
                const bar = card && card.querySelector('[data-card-progress]');
                if (bar) {
                    if (this.flags.showWaveformPreview) {
                        bar.style.width = `${progress}%`;
                        bar.setAttribute('aria-valuenow', String(Math.round(progress)));
                    } else {
                        bar.style.width = '0%';
                        bar.setAttribute('aria-valuenow', '0');
                    }
                }
            }
        } else {
            // If no valid duration, ensure progress bar is reset
            if (this.flags.showWaveformPreview && this.currentAudio) {
                const card = document.querySelector(`[data-report-id="${this.currentAudio.id}"]`);
                const bar = card && card.querySelector('[data-card-progress]');
                if (bar) { bar.style.width = '0%'; bar.setAttribute('aria-valuenow', '0'); }
            }
        }
        
        // Update playing state
        const wasPlaying = this.isPlaying;
        this.isPlaying = !this.audioElement.paused;
        
        if (wasPlaying !== this.isPlaying) {
            this.updatePlayButton();
        }
    }

    updateNowPlayingPreview() {
        if (this.currentAudio) {
            this.nowPlayingPreview.classList.remove('hidden');
            this.nowPlayingTitle.textContent = this.currentAudio.title;
        } else {
            this.nowPlayingPreview.classList.add('hidden');
        }
    }

    seekTo(event) {
        const rect = this.progressContainer.getBoundingClientRect();
        const percentage = (event.clientX - rect.left) / rect.width;
        const duration = this.audioElement.duration;
        
        if (duration && !isNaN(duration)) {
            this.audioElement.currentTime = percentage * duration;
        }
    }

    handleSearch() {
        this.searchQuery = this.searchInput.value.trim();
        this.currentPage = 1;
        this.loadContent();
    }

    setSortMode(mode) {
        this.currentSort = mode;
        this.currentPage = 1;
        this.updateSortToggle();
        this.loadContent();
    }

    updateSortToggle() {
        if (!this.sortToolbar) return;
        this.sortToolbar.querySelectorAll('[data-sort]').forEach(btn => {
            const active = btn.dataset.sort === this.currentSort;
            btn.classList.toggle('bg-audio-500', active);
            btn.classList.toggle('text-white', active);
            btn.classList.toggle('dark:bg-audio-600', active);
        });
    }

    handleFilterChange() {
        this.currentFilters = {};
        
        // Collect all checked filters
        document.querySelectorAll('input[type="checkbox"][data-filter]:checked').forEach(checkbox => {
            const filterType = checkbox.dataset.filter;
            if (!this.currentFilters[filterType]) {
                this.currentFilters[filterType] = [];
            }
            this.currentFilters[filterType].push(checkbox.value);
        });
        
        this.currentPage = 1;
        this.loadContent();
    }

    toggleQueue() {
        this.queueSidebar.classList.toggle('hidden');
    }

    addToQueue(reportId) {
        if (!this.flags.queueEnabled) return;
        if (!this.playlist) this.playlist = [];
        const item = (this.currentItems || []).find(x => x.file_stem === reportId);
        if (!item || !item.media?.has_audio) { this.showToast('No audio for this item', 'warn'); return; }
        if (!this.playlist.includes(reportId)) {
            this.playlist.push(reportId);
            this.saveQueue();
            this.renderQueue();
            this.showToast('Added to queue', 'success');
        }
    }

    playAllResults() {
        if (!this.currentItems || this.currentItems.length === 0) return;
        this.playlist = this.currentItems.map(i => i.file_stem);
        this.currentTrackIndex = 0;
        this.playAudio(this.playlist[0]);
    }

    playNext(source = 'user') {
        if (!this.playlist || this.playlist.length <= 1) return;
        this.currentTrackIndex = (this.currentTrackIndex + 1) % this.playlist.length;
        let safety = 0;
        while (safety < this.playlist.length) {
            const id = this.playlist[this.currentTrackIndex];
            const item = (this.currentItems || []).find(x => x.file_stem === id);
            if (item && item.media?.has_audio) break;
            this.currentTrackIndex = (this.currentTrackIndex + 1) % this.playlist.length;
            safety++;
        }
        if (safety >= this.playlist.length) return this.showToast('No playable items in queue', 'warn');
        this.saveQueue();
        this.playAudio(this.playlist[this.currentTrackIndex]);
        this.sendTelemetry(source === 'auto' ? 'auto_advance' : 'next', { index: this.currentTrackIndex });
    }

    playPrevious() {
        if (!this.playlist || this.playlist.length <= 1) return;
        this.currentTrackIndex = (this.currentTrackIndex - 1 + this.playlist.length) % this.playlist.length;
        let safety = 0;
        while (safety < this.playlist.length) {
            const id = this.playlist[this.currentTrackIndex];
            const item = (this.currentItems || []).find(x => x.file_stem === id);
            if (item && item.media?.has_audio) break;
            this.currentTrackIndex = (this.currentTrackIndex - 1 + this.playlist.length) % this.playlist.length;
            safety++;
        }
        if (safety >= this.playlist.length) return this.showToast('No playable items in queue', 'warn');
        this.saveQueue();
        this.playAudio(this.playlist[this.currentTrackIndex]);
        this.sendTelemetry('prev', { index: this.currentTrackIndex });
    }

    toggleMute() {
        if (!this.audioElement) return;
        
        this.audioElement.muted = !this.audioElement.muted;
        this.updateMuteIcon();
    }

    updateMuteIcon() {
        if (this.audioElement.muted) {
            this.volumeOnIcon.classList.add('hidden');
            this.volumeOffIcon.classList.remove('hidden');
        } else {
            this.volumeOnIcon.classList.remove('hidden');
            this.volumeOffIcon.classList.add('hidden');
        }
    }

    handleKeyboard(event) {
        // Ignore if typing in an input
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') return;
        
        switch(event.code) {
            case 'Space':
                if (this.currentAudio) {
                    event.preventDefault();
                    this.togglePlayPause();
                }
                break;
            case 'KeyJ':
                if (this.currentAudio) {
                    event.preventDefault();
                    this.playPrevious();
                }
                break;
            case 'KeyK':
                if (this.currentAudio) {
                    event.preventDefault();
                    this.playNext();
                }
                break;
            case 'KeyN':
                if (this.currentAudio) {
                    event.preventDefault();
                    this.playNext();
                }
                break;
            case 'KeyP':
                if (this.currentAudio) {
                    event.preventDefault();
                    this.playPrevious();
                }
                break;
            case 'KeyM':
                if (this.currentAudio) {
                    event.preventDefault();
                    this.toggleMute();
                }
                break;
            case 'KeyD': {
                const active = document.activeElement;
                const card = active && active.closest && active.closest('[data-card]');
                if (!card) break;
                event.preventDefault();
                this.toggleDeletePopover(card, true);
                break;
            }
            case 'Escape':
                if (this.currentExpandedId) {
                    event.preventDefault();
                    this.collapseCardInline(this.currentExpandedId);
                }
                break;
            // Card shortcuts while a card has focus
            case 'KeyL':
            case 'KeyR':
            case 'KeyW': {
                const active = document.activeElement;
                const card = active && active.closest && active.closest('[data-card]');
                if (!card) return;
                event.preventDefault();
                const id = card.dataset.reportId;
                if (event.code === 'KeyL') this.playAudio(id);
                if (event.code === 'KeyR') this.handleRead(id);
                if (event.code === 'KeyW') this.openYoutube(card.dataset.videoId);
                break;
            }
        }
    }

    // Utility methods
    formatDuration(seconds) {
        if (!seconds || isNaN(seconds)) return '0:00';
        
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    showError(message) {
        // Simple error display - could be enhanced with toast notifications
        console.error(message);
        // In a real implementation, show a user-friendly error message
    }

    showToast(message, type = 'info') {
        const el = document.createElement('div');
        const colors = {
            success: 'bg-emerald-600',
            error: 'bg-red-600',
            warn: 'bg-amber-600',
            info: 'bg-slate-800'
        };
        el.className = `fixed top-4 left-1/2 -translate-x-1/2 z-50 px-3 py-2 rounded-lg text-white shadow ${colors[type] || colors.info}`;
        el.textContent = message;
        document.body.appendChild(el);
        // SR live update
        const sr = document.getElementById('srLive');
        if (sr) sr.textContent = message;
        setTimeout(() => {
            el.classList.add('opacity-0', 'transition', 'duration-200');
            setTimeout(() => el.remove(), 220);
        }, 1600);
    }

    // Queue rendering/persistence (Phase 3)
    renderQueue() {
        if (!this.audioQueue) return;
        const items = this.playlist || [];
        const html = items.map((id, idx) => {
            const item = (this.currentItems || []).find(x => x.file_stem === id);
            const title = item ? this.escapeHtml(item.title) : id;
            const isCurrent = idx === this.currentTrackIndex;
            const aria = isCurrent ? ' aria-current="true"' : '';
            return `
              <button data-queue-index="${idx}"${aria} class="w-full text-left px-3 py-2 rounded-lg border ${isCurrent ? 'border-audio-400 bg-audio-50' : 'border-slate-200 hover:bg-slate-50'} text-sm truncate">
                <span class="text-slate-600">${(idx+1).toString().padStart(2,'0')}.</span>
                <span class="ml-2 ${isCurrent ? 'text-audio-700 font-medium' : 'text-slate-700'}">${title}</span>
              </button>`;
        }).join('');
        this.audioQueue.innerHTML = html;
        this.audioQueue.querySelectorAll('[data-queue-index]').forEach(btn => {
            btn.addEventListener('click', () => {
                const i = parseInt(btn.dataset.queueIndex);
                if (isNaN(i)) return;
                this.currentTrackIndex = i;
                this.saveQueue();
                this.playAudio(this.playlist[this.currentTrackIndex]);
                this.sendTelemetry('queue_jump', { index: i });
            });
        });
    }

    clearQueue() {
        this.playlist = [];
        this.currentTrackIndex = -1;
        this.saveQueue();
        this.renderQueue();
        this.sendTelemetry('queue_clear', {});
    }

    saveQueue() {
        try {
            const data = { playlist: this.playlist || [], index: this.currentTrackIndex };
            sessionStorage.setItem(this.queueKey, JSON.stringify(data));
        } catch (_) {}
    }

    restoreQueue() {
        try {
            const raw = sessionStorage.getItem(this.queueKey);
            if (!raw) return;
            const data = JSON.parse(raw);
            if (Array.isArray(data.playlist) && typeof data.index === 'number') {
                this.playlist = data.playlist;
                this.currentTrackIndex = Math.min(Math.max(0, data.index), this.playlist.length - 1);
                const id = this.playlist[this.currentTrackIndex];
                const item = (this.currentItems || []).find(x => x.file_stem === id) || this.currentItems[0];
                if (item) this.setCurrentFromItem(item);
                this.renderQueue();
            }
        } catch (_) {}
    }

    // Telemetry batching + sampling
    queueTelemetry(evt) {
        if (!this.telemetryBuf) this.telemetryBuf = [];
        this.telemetryBuf.push(evt);
        if (!this.telemetryFlushTimer) {
            this.telemetryFlushTimer = setTimeout(() => this.flushTelemetry(), 5000);
        }
    }

    async flushTelemetry() {
        const buf = this.telemetryBuf.splice(0, this.telemetryBuf.length);
        this.telemetryFlushTimer = null;
        if (!buf.length) return;
        try {
            await fetch('/api/telemetry', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ batch: buf, ts: Date.now() })
            });
        } catch (e) {
            console.log('[telemetry:batch]', buf);
        }
    }

    sendTelemetry(eventName, payload = {}) {
        const sampled = ['cta_listen','cta_watch'].includes(eventName) ? (Math.random() < 0.25) : true;
        if (!sampled) return;
        this.queueTelemetry({ event: eventName, ...payload, t: Date.now() });
    }
}

// Initialize the dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.audioDashboard = new AudioDashboard();
});
