/**
 * YTV2 Dashboard V3 - Audio-Centric Interface
 * Phase 3 implementation with integrated audio player and modern UX
 */

// Subcategory to parent category mapping (authoritative source from youtube_summarizer.py)
const SUBCATEGORY_PARENTS = {
    // Education subcategories
    "Academic Subjects": "Education",
    "Online Learning": "Education", 
    "Tutorials & Courses": "Education",
    "Teaching Methods": "Education",
    "Educational Technology": "Education",
    "Student Life": "Education",
    
    // Technology subcategories  
    "Programming & Software Development": "Technology",
    "Web Development": "Technology",
    "Mobile Development": "Technology", 
    "DevOps & Infrastructure": "Technology",
    "Databases & Data Science": "Technology",
    "Cybersecurity": "Technology",
    "Tech Reviews & Comparisons": "Technology",
    "Software Tutorials": "Technology",
    "Tech News & Trends": "Technology",
    
    // AI Software Development subcategories
    "Model Selection & Evaluation": "AI Software Development",
    "Prompt Engineering & RAG": "AI Software Development",
    "Training & Fine-Tuning": "AI Software Development", 
    "Deployment & Serving": "AI Software Development",
    "Agents & MCP/Orchestration": "AI Software Development",
    "APIs & SDKs": "AI Software Development",
    "Data Engineering & ETL": "AI Software Development",
    "Testing & Observability": "AI Software Development", 
    "Security & Safety": "AI Software Development",
    "Cost Optimisation": "AI Software Development",
    
    // History subcategories
    "Ancient Civilizations": "History",
    "Medieval History": "History",
    "Modern History": "History",
    "Cultural Heritage": "History", 
    "Historical Analysis": "History",
    "Biographies": "History",
    
    // WWII subcategories  
    "Causes & Prelude": "World War II (WWII)",
    "European Theatre": "World War II (WWII)",
    "Pacific Theatre": "World War II (WWII)",
    "Home Front & Society": "World War II (WWII)",
    "Technology & Weapons": "World War II (WWII)",
    "Intelligence & Codebreaking": "World War II (WWII)",
    "Holocaust & War Crimes": "World War II (WWII)",
    "Diplomacy & Conferences (Yalta, Potsdam)": "World War II (WWII)",
    "Biographies & Commanders": "World War II (WWII)",
    "Aftermath & Reconstruction": "World War II (WWII)",
    
    // Business subcategories
    "Industry Analysis": "Business",
    "Career Development": "Business",
    
    // General subcategories
    "Miscellaneous": "General",
    "Other": "General"
};

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
        this.currentSort = 'added_desc';
        this.searchQuery = '';
        this.viewMode = (localStorage.getItem('ytv2.viewMode') || 'list');
        // Inline expand state
        this.currentExpandedId = null;
        // Queue persistence key (Phase 3)
        this.queueKey = 'ytv2.queue';
        // Telemetry buffer
        this.telemetryBuf = [];
        this.telemetryFlushTimer = null;
        // Realtime ingest state
        this.eventSource = null;
        this.realtimeBackoff = 1000;
        this.realtimeReconnectTimer = null;
        this.realtimeEventBuffer = [];
        this.realtimeFlushTimer = null;
        this.realtimePendingCount = 0;
        this.latestIndexedAt = null;
        this.lastRealtimeRefresh = 0;
        this.pollTimer = null;
        this.initialLoadComplete = false;
        this.disableRealtimeSSE = this.shouldDisableRealtimeSSE();
        this.metricsTimer = null;
        this.metricsData = null;
        this.metricsRefreshTimer = null;
        this.reprocessToken = (typeof window !== 'undefined' && window.REPROCESS_TOKEN) ? window.REPROCESS_TOKEN : null;
        this.reprocessTokenSource = this.reprocessToken ? 'window' : null;
        this.pendingReprocess = null;
        
        this.initializeElements();
        this.updateReprocessFootnote();
        this.showNowPlayingPlaceholder();
        this.bindEvents();
        this.initRealtimeUpdates();
        this.startMetricsPolling();
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
        
        // Mobile mini-player elements
        this.mobileMiniPlayer = document.getElementById('mobileMiniPlayer');
        this.mobilePlayPauseBtn = document.getElementById('mobilePlayPauseBtn');
        this.mobilePlayIcon = document.getElementById('mobilePlayIcon');
        this.mobilePauseIcon = document.getElementById('mobilePauseIcon');
        this.mobilePrevBtn = document.getElementById('mobilePrevBtn');
        this.mobileNextBtn = document.getElementById('mobileNextBtn');
        this.mobileProgressContainer = document.getElementById('mobileProgressContainer');
        this.mobileProgressBar = document.getElementById('mobileProgressBar');
        this.mobileCurrentTimeEl = document.getElementById('mobileCurrentTime');
        this.mobileNowPlayingTitle = document.getElementById('mobileNowPlayingTitle');
        this.mobileNowPlayingThumb = document.getElementById('mobileNowPlayingThumb');
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
        this.channelFilters = document.getElementById('channelFilters');
        this.contentTypeFilters = document.getElementById('contentTypeFilters');
        this.complexityFilters = document.getElementById('complexityFilters');
        this.languageFilters = document.getElementById('languageFilters');
        this.summaryTypeFilters = document.getElementById('summaryTypeFilters');
        
        // Content area
        this.contentGrid = document.getElementById('contentGrid');
        this.resultsTitle = document.getElementById('resultsTitle');
        this.resultsSubtitle = document.getElementById('resultsSubtitle');
        this.resultsCount = document.getElementById('resultsCount');
        this.heroBadges = document.getElementById('heroBadges');
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

        // Realtime banner
        this.realtimeBanner = document.getElementById('realtimeBanner');
       this.realtimeBannerText = document.getElementById('realtimeBannerText');
       this.realtimeRefreshBtn = document.getElementById('realtimeRefreshBtn');
       this.realtimeDismissBtn = document.getElementById('realtimeDismissBtn');

        // Metrics panel
        this.metricsPanel = document.getElementById('metricsPanel');
        this.metricsLastIngestEl = document.getElementById('metricsLastIngest');
        this.metricsCountersEl = document.getElementById('metricsCounters');
        this.metricsSseEl = document.getElementById('metricsSse');

        // Reprocess modal
        this.reprocessModal = document.getElementById('reprocessModal');
        this.reprocessText = document.getElementById('reprocessText');
        this.reprocessAudioToggle = document.getElementById('reprocessAudioToggle');
        this.reprocessFootnote = document.getElementById('reprocessFootnote');
        this.reprocessTokenReset = document.getElementById('reprocessTokenReset');
        this.confirmReprocessBtn = document.getElementById('confirmReprocessBtn');
        this.cancelReprocessBtn = document.getElementById('cancelReprocessBtn');
    }

    bindEvents() {
        // Audio events
        this.audioElement.addEventListener('loadedmetadata', () => this.updateDuration());
        this.audioElement.addEventListener('timeupdate', () => this.updateProgress());
        this.audioElement.addEventListener('ended', () => this.playNext('auto'));
        this.audioElement.addEventListener('canplay', () => this.handleCanPlay());
        this.audioElement.addEventListener('error', () => this.handleAudioError());
        // Reflect play/pause immediately in card buttons and controls
        this.audioElement.addEventListener('play', () => { this.isPlaying = true; this.updatePlayButton(); this.updatePlayingCard(); });
        this.audioElement.addEventListener('pause', () => { 
            this.isPlaying = false; 
            this.updatePlayButton(); 
            this.updatePlayingCard();
            // Clean up scrub state when pausing to prevent conflicts
            this._cleanupScrubState();
        });
        
        // Player controls
        this.playPauseBtn.addEventListener('click', () => this.togglePlayPause());
        this.prevBtn.addEventListener('click', () => this.playPrevious());
        this.nextBtn.addEventListener('click', () => this.playNext());
        this.progressContainer.addEventListener('click', (e) => this.seekTo(e));
        this.progressContainer.addEventListener('mousedown', (e) => this.beginProgressDrag(e, false));
        if (this.volumeBtn) this.volumeBtn.addEventListener('click', () => this.toggleMute());
        
        // Mobile mini-player controls
        if (this.mobilePlayPauseBtn) this.mobilePlayPauseBtn.addEventListener('click', () => this.togglePlayPause());
        if (this.mobilePrevBtn) this.mobilePrevBtn.addEventListener('click', () => this.playPrevious());
        if (this.mobileNextBtn) this.mobileNextBtn.addEventListener('click', () => this.playNext());
        if (this.mobileProgressContainer) {
            this.mobileProgressContainer.addEventListener('click', (e) => this.seekToMobile(e));
            this.mobileProgressContainer.addEventListener('mousedown', (e) => this.beginProgressDrag(e, true));
            this.mobileProgressContainer.addEventListener('touchstart', (e) => this.beginProgressDrag(e, true), { passive: true });
        }
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
        
        // Radio button sort controls in sidebar - use delegation for dynamic content
        document.addEventListener('click', (e) => {
            const label = e.target.closest('label');
            if (label && label.querySelector('input[name="sortBy"]')) {
                const radio = label.querySelector('input[name="sortBy"]');
                if (radio && !radio.checked) {
                    this.setSortMode(radio.value);
                }
            }
        });
        
        // Show more sort options toggle
        const toggleMoreSorts = document.getElementById('toggleMoreSorts');
        const showMoreSorts = document.getElementById('showMoreSorts');
        if (toggleMoreSorts && showMoreSorts) {
            toggleMoreSorts.addEventListener('click', () => {
                const isHidden = showMoreSorts.classList.contains('hidden');
                showMoreSorts.classList.toggle('hidden');
                toggleMoreSorts.textContent = isHidden ? 'Show less' : 'Show more';
            });
        }
        
        // Show more languages toggle
        const toggleMoreLanguages = document.getElementById('toggleMoreLanguages');
        const showMoreLanguages = document.getElementById('showMoreLanguages');
        if (toggleMoreLanguages && showMoreLanguages) {
            toggleMoreLanguages.addEventListener('click', () => {
                const isHidden = showMoreLanguages.classList.contains('hidden');
                showMoreLanguages.classList.toggle('hidden');
                toggleMoreLanguages.textContent = isHidden ? 'Show less' : 'Show more';
            });
        }
        
        // Show more categories toggle - bind after content loads
        this.bindShowMoreToggles();
        
        // Select All / Clear All buttons for Categories
        const selectAllCategories = document.getElementById('selectAllCategories');
        const clearAllCategories = document.getElementById('clearAllCategories');
        if (selectAllCategories) {
            selectAllCategories.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="category"]').forEach(cb => { cb.checked = true; });
                document.querySelectorAll('input[data-filter="subcategory"]').forEach(cb => { cb.checked = true; });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }
        if (clearAllCategories) {
            clearAllCategories.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="category"]').forEach(cb => { cb.checked = false; });
                document.querySelectorAll('input[data-filter="subcategory"]').forEach(cb => { cb.checked = false; });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }

        // Select All / Clear All buttons for Channels
        const selectAllChannels = document.getElementById('selectAllChannels');
        const clearAllChannels = document.getElementById('clearAllChannels');
        if (selectAllChannels) {
            selectAllChannels.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="channel"]').forEach(cb => { cb.checked = true; });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }
        if (clearAllChannels) {
            clearAllChannels.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="channel"]').forEach(cb => { cb.checked = false; });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }
        
        // Select All / Clear All buttons for Content Types
        const selectAllContentTypes = document.getElementById('selectAllContentTypes');
        const clearAllContentTypes = document.getElementById('clearAllContentTypes');
        if (selectAllContentTypes) {
            selectAllContentTypes.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="content_type"]').forEach(cb => {
                    cb.checked = true;
                });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }
        if (clearAllContentTypes) {
            clearAllContentTypes.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="content_type"]').forEach(cb => {
                    cb.checked = false;
                });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }

        // Select All / Clear All buttons for Summary Types
        const selectAllSummaryTypes = document.getElementById('selectAllSummaryTypes');
        const clearAllSummaryTypes = document.getElementById('clearAllSummaryTypes');
        if (selectAllSummaryTypes) {
            selectAllSummaryTypes.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="summary_type"]').forEach(cb => {
                    cb.checked = true;
                });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }
        if (clearAllSummaryTypes) {
            clearAllSummaryTypes.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="summary_type"]').forEach(cb => {
                    cb.checked = false;
                });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }

        // UI controls
        this.queueToggle.addEventListener('click', () => this.toggleQueue());
        if (this.queueClearBtn) this.queueClearBtn.addEventListener('click', () => this.clearQueue());
        // Play All button removed - auto-playlist handles this
        if (this.listViewBtn) this.listViewBtn.addEventListener('click', () => this.setViewMode('list'));
        
        // Mobile sidebar controls
        const mobileFiltersToggle = document.getElementById('mobileFiltersToggle');
        const closeSidebar = document.getElementById('closeSidebar');
        const sidebar = document.getElementById('sidebar');
        
        if (mobileFiltersToggle) {
            mobileFiltersToggle.addEventListener('click', () => this.openMobileSidebar());
        }
        if (closeSidebar) {
            closeSidebar.addEventListener('click', () => this.closeMobileSidebar());
        }
        // Close sidebar when clicking outside on mobile
        if (sidebar) {
            sidebar.addEventListener('click', (e) => {
                if (e.target === sidebar) this.closeMobileSidebar();
            });
        }
        if (this.gridViewBtn) this.gridViewBtn.addEventListener('click', () => this.setViewMode('grid'));
        this.updateViewToggle();
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
        this.audioElement.addEventListener('volumechange', () => this.updateMuteIcon());

        // Delegated filter "only" button handlers  
        document.addEventListener('click', (e) => {
            const onlyBtn = e.target.closest('[data-filter-only]');
            if (!onlyBtn) return;
            e.stopPropagation();
            const filterType = onlyBtn.dataset.filterOnly;
            const filterValue = onlyBtn.dataset.filterOnlyValue;
            const parentCategory = onlyBtn.dataset.parentCategory || null;
            console.log('🔍 Only button clicked:', { filterType, filterValue, parentCategory });
            this.applyFilterFromChip(filterType, filterValue, parentCategory);
        });

        // Delegated card actions
        if (this.contentGrid) {
            this.contentGrid.addEventListener('click', (e) => this.onClickCardAction(e));
            // Seek on thumbnail progress bar (subtle, bottom of thumbnail)
            this.contentGrid.addEventListener('click', (e) => {
                const el = e.target.closest('[data-card-progress-container]');
                if (!el) return;
                if (this._dragEndedAt && (Date.now() - this._dragEndedAt) < 300) { return; }
                e.stopPropagation();
                this.seekOnCardScrub(el, e);
                // Guard against card click navigation following the seek
                this._suppressOpen = true;
                setTimeout(() => { this._suppressOpen = false; }, 200);
            });
            // Drag seek on thumbnail bar
            this.contentGrid.addEventListener('mousedown', (e) => {
                const el = e.target.closest('[data-card-progress-container]');
                if (!el) return;
                e.preventDefault();
                this.beginCardScrubDrag(el, e.clientX);
            });
            this.contentGrid.addEventListener('touchstart', (e) => {
                const el = e.target.closest('[data-card-progress-container]');
                if (!el) return;
                const t = e.touches[0];
                this.beginCardScrubDrag(el, t.clientX);
            }, { passive: true });
            // Hover tooltip for timestamp while moving over the bar
            this.contentGrid.addEventListener('mousemove', (e) => {
                const el = e.target.closest('[data-card-progress-container]');
                if (!el) { this.hideScrubTooltip(); return; }
                this.showScrubTooltip(el, e);
            });
            this.contentGrid.addEventListener('mouseleave', (e) => {
                if (!e.relatedTarget || !e.currentTarget.contains(e.relatedTarget)) {
                    this.hideScrubTooltip();
                }
            });
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

        if (this.realtimeRefreshBtn) {
            this.realtimeRefreshBtn.addEventListener('click', () => this.refreshForRealtime());
        }
        if (this.realtimeDismissBtn) {
            this.realtimeDismissBtn.addEventListener('click', () => this.dismissRealtimeBanner());
        }

        if (this.confirmReprocessBtn) {
            this.confirmReprocessBtn.addEventListener('click', () => this.submitReprocess());
        }
        if (this.cancelReprocessBtn) {
            this.cancelReprocessBtn.addEventListener('click', () => this.closeReprocessModal());
        }
        if (this.reprocessTokenReset) {
            this.reprocessTokenReset.addEventListener('click', (event) => {
                event.preventDefault();
                this.resetStoredReprocessToken();
            });
        }

        window.addEventListener('beforeunload', () => this.shutdownRealtime());
        window.addEventListener('pagehide', () => this.shutdownRealtime());
    }

    async loadInitialData() {
        try {
            // Apply theme at startup
            this.applyTheme(this.themeMode);
            this.updateThemeChecks();
            // Load filters first to avoid race with initial content fetch
            await this.loadFilters();
            await this.waitForFiltersReady({ min: 1, timeoutMs: 3000 });
            await this.loadContent();
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
            if (!this.currentAudio) {
                const playableItems = this.getPlayableItems(this.currentItems);
                if (playableItems.length) {
                    this.setCurrentFromItem(playableItems[0]);
                } else {
                    this.showNowPlayingPlaceholder();
                }
            }
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showError('Failed to load dashboard data');
        } finally {
            this.initialLoadComplete = true;
            this.flushRealtimeBuffer(true);
        }
    }

    // Realtime ingest event handling -------------------------------------------------

    initRealtimeUpdates() {
        if (typeof window === 'undefined') return;
        if (this.disableRealtimeSSE) {
            console.info('Realtime SSE disabled by flag; using polling fallback');
            this.startPollingFallback();
            return;
        }
        if (window.EventSource) {
            this.connectEventSource();
        } else {
            console.warn('EventSource not supported; falling back to polling');
            this.startPollingFallback();
        }
    }

    connectEventSource() {
        if (typeof window === 'undefined' || !window.EventSource) return;
        if (this.eventSource) {
            try { this.eventSource.close(); } catch (_) {}
        }
        try {
            const source = new EventSource('/api/report-events');
            this.eventSource = source;
            source.addEventListener('open', () => {
                this.realtimeBackoff = 1000;
                if (this.realtimeReconnectTimer) {
                    window.clearTimeout(this.realtimeReconnectTimer);
                    this.realtimeReconnectTimer = null;
                }
                this.stopPollingFallback();
                this.requestMetricsRefresh(500);
            });
            source.addEventListener('error', () => {
                try { source.close(); } catch (_) {}
                this.eventSource = null;
                this.scheduleRealtimeReconnect();
                this.startPollingFallback();
            });
            const safeParse = (evt) => {
                try {
                    return JSON.parse(evt.data || '{}') || {};
                } catch (error) {
                    console.error('Failed to parse SSE event payload', error);
                    return {};
                }
            };

            const successEvents = ['report-added', 'report-synced', 'audio-synced', 'reprocess-complete'];
            successEvents.forEach((name) => {
                source.addEventListener(name, (evt) => {
                    const payload = safeParse(evt);
                    this.handleReportAddedEvent(payload, { transport: 'sse', eventName: name });
                });
            });

            const infoEvents = ['reprocess-scheduled', 'reprocess-requested'];
            infoEvents.forEach((name) => {
                source.addEventListener(name, (evt) => {
                    const payload = safeParse(evt);
                    this.handleReprocessLifecycle(name, payload);
                });
            });

            const failureEvents = [
                'report-sync-failed',
                'report-sync-error',
                'audio-sync-failed',
                'audio-sync-error',
                'reprocess-error'
            ];
            failureEvents.forEach((name) => {
                source.addEventListener(name, (evt) => {
                    const payload = safeParse(evt);
                    this.handleRealtimeFailure(name, payload);
                });
            });
        } catch (error) {
            console.error('Failed to connect to report events', error);
            this.scheduleRealtimeReconnect();
            this.startPollingFallback();
        }
    }

    scheduleRealtimeReconnect() {
        if (typeof window === 'undefined') return;
        if (this.realtimeReconnectTimer) return;
        const delay = this.realtimeBackoff || 1000;
        this.realtimeReconnectTimer = window.setTimeout(() => {
            this.realtimeReconnectTimer = null;
            this.connectEventSource();
        }, delay);
        this.realtimeBackoff = Math.min((this.realtimeBackoff || 1000) * 2, 30000);
    }

    startPollingFallback() {
        if (typeof window === 'undefined') return;
        if (this.pollTimer) return;
        this.pollTimer = window.setInterval(() => this.pollLatestReport(), 45000);
    }

    stopPollingFallback() {
        if (typeof window === 'undefined') return;
        if (this.pollTimer) {
            window.clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
    }

    async pollLatestReport() {
        try {
            const response = await fetch('/api/reports?latest=true', { cache: 'no-store' });
            if (!response.ok) return;
            const payload = await response.json();
            if (!payload || !payload.report) return;
            this.handleReportAddedEvent(payload.report, { transport: 'poll', eventName: 'report-synced' });
        } catch (error) {
            console.warn('Polling latest report failed', error);
        }
    }

    handleReportAddedEvent(data = {}, meta = {}) {
        if (!data) return;
        const eventName = (meta.eventName || 'report-added').toLowerCase();
        let videoId = data.video_id || data.videoId || data.id || null;
        if (!videoId && meta.videoId) videoId = meta.videoId;
        if (!videoId) {
            console.warn('Realtime event missing video_id', data, meta);
            return;
        }

        let summaryTypes = data.summary_types || data.summaryTypes || [];
        if (!Array.isArray(summaryTypes)) {
            summaryTypes = summaryTypes ? [summaryTypes] : [];
        }
        const singleType = data.summary_type || data.summaryType;
        if (singleType) summaryTypes.push(singleType);
        summaryTypes = [...new Set(summaryTypes.map((v) => String(v)).filter(Boolean))];

        let timestamp = data.timestamp || data.indexed_at || data.indexedAt || data.created_at || data.updated_at || null;
        if (!timestamp) {
            timestamp = new Date().toISOString();
        }
        const tsValue = this.normalizeTimestamp(timestamp);
        const currentTs = this.normalizeTimestamp(this.latestIndexedAt);
        const bypassRecencyCheck = ['audio-synced', 'reprocess-complete'].includes(eventName);
        if (!bypassRecencyCheck && currentTs && tsValue && tsValue <= currentTs) {
            return;
        }
        if (tsValue && (!currentTs || tsValue > currentTs)) {
            this.latestIndexedAt = timestamp;
        }

        if (eventName === 'audio-synced') {
            this.showToast(`Audio ready for ${this.describeVideo(data)}`, 'success');
        }
        if (eventName === 'reprocess-complete') {
            this.showToast(`Reprocess finished for ${this.describeVideo(data)}`, 'success');
        }

        this.realtimeEventBuffer.push({ videoId, summaryTypes, timestamp, meta: { ...meta, eventName } });
        this.scheduleRealtimeFlush();
        this.requestMetricsRefresh(2000);
    }

    scheduleRealtimeFlush() {
        if (typeof window === 'undefined') return;
        if (this.realtimeFlushTimer) return;
        this.realtimeFlushTimer = window.setTimeout(() => this.flushRealtimeBuffer(), 800);
    }

    flushRealtimeBuffer(force = false) {
        if (this.realtimeFlushTimer) {
            window.clearTimeout(this.realtimeFlushTimer);
            this.realtimeFlushTimer = null;
        }
        if (!this.initialLoadComplete && !force) {
            return;
        }
        if (!this.realtimeEventBuffer.length) return;

        const buffer = this.realtimeEventBuffer.splice(0);
        const uniqueVideoIds = new Set(buffer.map((evt) => evt.videoId).filter(Boolean));
        const newCount = uniqueVideoIds.size || buffer.length;
        const eventNames = buffer.map((evt) => (evt.meta && evt.meta.eventName) ? evt.meta.eventName : 'report-added');
        this.realtimePendingCount += newCount;

        const now = Date.now();
        const sinceLast = now - (this.lastRealtimeRefresh || 0);
        const canAutoRefresh = (this.currentPage === 1) || force;

        if (canAutoRefresh && sinceLast > 2000) {
            this.lastRealtimeRefresh = now;
            this.currentPage = 1;
            Promise.resolve(this.loadContent())
                .catch((error) => console.error('Realtime refresh failed', error))
                .finally(() => {
                    this.realtimePendingCount = 0;
                    this.hideRealtimeBanner();
                    this.requestMetricsRefresh(1200);
                });
        } else {
            this.showRealtimeBanner(this.realtimePendingCount, eventNames);
            this.requestMetricsRefresh(2000);
        }
    }

    showRealtimeBanner(count, eventNames = []) {
        if (!this.realtimeBanner || !this.realtimeBannerText) return;
        let label = count === 1 ? '1 update available' : `${count} updates available`;
        if (eventNames.length === 1) {
            label = `${this.formatEventLabel(eventNames[0])} ready`;
        }
        this.realtimeBannerText.textContent = label;
        this.realtimeBanner.classList.remove('hidden');
        this.realtimeBanner.setAttribute('aria-hidden', 'false');
    }

    hideRealtimeBanner() {
        if (!this.realtimeBanner) return;
        this.realtimeBanner.classList.add('hidden');
        this.realtimeBanner.setAttribute('aria-hidden', 'true');
    }

    shutdownRealtime() {
        if (typeof window !== 'undefined') {
            if (this.realtimeReconnectTimer) {
                window.clearTimeout(this.realtimeReconnectTimer);
                this.realtimeReconnectTimer = null;
            }
            if (this.realtimeFlushTimer) {
                window.clearTimeout(this.realtimeFlushTimer);
                this.realtimeFlushTimer = null;
            }
        }
        if (this.eventSource) {
            try {
                this.eventSource.close();
            } catch (_) {
                // already closed
            }
            this.eventSource = null;
        }
        this.stopPollingFallback();
        if (this.metricsTimer) {
            window.clearInterval(this.metricsTimer);
            this.metricsTimer = null;
        }
        if (this.metricsRefreshTimer) {
            window.clearTimeout(this.metricsRefreshTimer);
            this.metricsRefreshTimer = null;
        }
    }

    startMetricsPolling() {
        if (typeof window === 'undefined') return;
        if (this.metricsTimer) {
            window.clearInterval(this.metricsTimer);
            this.metricsTimer = null;
        }
        this.fetchMetrics();
        this.metricsTimer = window.setInterval(() => this.fetchMetrics(), 60000);
    }

    async fetchMetrics() {
        try {
            const response = await fetch('/api/metrics', { cache: 'no-store' });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            this.metricsData = data;
            this.updateMetricsUI(data);
        } catch (error) {
            console.warn('Failed to load metrics snapshot', error);
        }
    }

    updateMetricsUI(data) {
        if (!data || !this.metricsPanel) return;

        const success = Number(data.ingest_success ?? data.ingest_success_total ?? data.ingest_success_count ?? 0);
        const failure = Number(data.ingest_failure ?? data.ingest_failure_total ?? data.ingest_failure_count ?? 0);
        if (this.metricsCountersEl) {
            this.metricsCountersEl.textContent = `Ingest ✓ ${success} • ✕ ${failure}`;
        }

        const sseClients = Number(data.sse_clients_current ?? data.sse_clients ?? 0);
        if (this.metricsSseEl) {
            this.metricsSseEl.textContent = `SSE clients: ${sseClients}`;
        }

        const lastVideo = data.last_ingest_video || data.last_ingest_id || '';
        const lastTimestamp = data.last_ingest_timestamp || data.last_ingest_time || data.last_ingest_at || '';
        if (this.metricsLastIngestEl) {
            if (lastVideo || lastTimestamp) {
                const label = this.truncateText(lastVideo || '—', 18);
                const relative = this.formatRelativeTime(lastTimestamp);
                const parts = [`Last ingest: ${label}`];
                if (relative) parts.push(relative);
                this.metricsLastIngestEl.textContent = parts.join(' • ');
            } else {
                this.metricsLastIngestEl.textContent = 'Last ingest: —';
            }
        }
    }

    requestMetricsRefresh(delay = 2000) {
        if (typeof window === 'undefined') return;
        if (this.metricsRefreshTimer) {
            window.clearTimeout(this.metricsRefreshTimer);
        }
        this.metricsRefreshTimer = window.setTimeout(() => this.fetchMetrics(), delay);
    }

    handleReprocessLifecycle(eventName, payload = {}) {
        const label = this.describeVideo(payload);
        if (eventName === 'reprocess-scheduled') {
            this.showToast(`Reprocess scheduled for ${label}`, 'info');
        }
        if (eventName === 'reprocess-requested') {
            this.showToast(`Reprocess started for ${label}`, 'info');
        }
        this.requestMetricsRefresh(2500);
    }

    handleRealtimeFailure(eventName, payload = {}) {
        const label = this.describeVideo(payload);
        const message = payload.message || payload.error || 'Unexpected error';
        const text = `${this.formatEventLabel(eventName)} for ${label} failed: ${message}`;
        this.showToast(text, 'error');
        this.requestMetricsRefresh(2000);
    }

    describeVideo(payload = {}) {
        const title = payload.title || payload.video_title;
        const videoId = payload.video_id || payload.videoId || payload.id;
        if (title) return this.truncateText(title, 40);
        if (videoId) return this.truncateText(videoId, 16);
        return 'item';
    }

    formatEventLabel(name) {
        const map = {
            'report-added': 'New report',
            'report-synced': 'Report update',
            'audio-synced': 'Audio update',
            'reprocess-scheduled': 'Reprocess scheduled',
            'reprocess-requested': 'Reprocess started',
            'reprocess-complete': 'Reprocess complete',
            'report-sync-failed': 'Report sync failed',
            'report-sync-error': 'Report sync error',
            'audio-sync-failed': 'Audio sync failed',
            'audio-sync-error': 'Audio sync error',
            'reprocess-error': 'Reprocess error'
        };
        return map[name] || name.replace(/[-_]/g, ' ');
    }

    async refreshForRealtime() {
        this.hideRealtimeBanner();
        this.realtimePendingCount = 0;
        this.currentPage = 1;
        try {
            await this.loadContent();
        } catch (error) {
            console.error('Realtime refresh failed', error);
        }
    }

    dismissRealtimeBanner() {
        this.realtimePendingCount = 0;
        this.hideRealtimeBanner();
    }

    normalizeTimestamp(value) {
        if (!value) return 0;
        const parsed = Date.parse(value);
        return Number.isNaN(parsed) ? 0 : parsed;
    }

    updateLatestIndexFromItems(items) {
        if (!Array.isArray(items) || !items.length) return;
        if (this.currentPage !== 1) return;
        const firstTs = items[0]?.indexed_at || items[0]?.indexedAt || null;
        const tsValue = this.normalizeTimestamp(firstTs);
        const current = this.normalizeTimestamp(this.latestIndexedAt);
        if (tsValue && (!current || tsValue >= current)) {
            this.latestIndexedAt = firstTs;
        }
    }

    shouldDisableRealtimeSSE() {
        if (typeof window === 'undefined') {
            return false;
        }
        try {
            const params = new URLSearchParams(window.location.search);
            if (params.has('noSSE') || params.get('disableSSE') === '1') {
                return true;
            }
            if (window.localStorage) {
                const stored = window.localStorage.getItem('ytv2.disableSSE');
                if (stored === '1') {
                    return true;
                }
            }
        } catch (error) {
            console.warn('Unable to evaluate SSE disable flag', error);
        }
        return false;
    }

    getPlayableItems(items = this.currentItems) {
        if (!Array.isArray(items)) return [];
        return items.filter(item => item && item.media && item.media.has_audio);
    }

    rebuildPlaylist(items = this.currentItems) {
        const playable = this.getPlayableItems(items);
        this.playlist = playable.map(item => item.file_stem);
        return playable;
    }

    getAudioSourceForItem(item) {
        if (!item || !item.media || !item.media.has_audio) return null;
        if (item.media.audio_url) return item.media.audio_url;
        const videoId = item.video_id;
        if (videoId) return `/exports/by_video/${videoId}.mp3`;
        const reportId = item.file_stem;
        return reportId ? `/exports/${reportId}.mp3` : null;
    }

    resetAudioElement() {
        if (!this.audioElement) return;
        try {
            this.audioElement.pause();
        } catch (_) {}
        this.audioElement.removeAttribute('src');
        this.audioElement.load();
        if (this.progressBar) this.progressBar.style.width = '0%';
        if (this.currentTimeEl) this.currentTimeEl.textContent = '0:00';
        if (this.totalTimeEl) this.totalTimeEl.textContent = '0:00';
    }

    showNowPlayingPlaceholder(item = null) {
        this.currentAudio = null;
        this.isPlaying = false;
        this.resetAudioElement();

        if (this.nowPlayingPreview) this.nowPlayingPreview.classList.remove('hidden');

        if (this.nowPlayingTitle) {
            if (item && item.title) {
                const label = item.title || 'Summary';
                this.nowPlayingTitle.textContent = `${label} (no audio)`;
            } else {
                this.nowPlayingTitle.textContent = 'Select an audio summary';
            }
        }

        if (this.nowPlayingMeta) {
            this.nowPlayingMeta.textContent = item ? 'Audio not available' : 'Choose a summary with audio';
        }

        if (this.nowPlayingThumb) {
            if (item && item.thumbnail_url) {
                this.nowPlayingThumb.src = item.thumbnail_url;
                this.nowPlayingThumb.classList.remove('hidden');
            } else {
                this.nowPlayingThumb.classList.add('hidden');
            }
        }

        this.updatePlayButton();
        this.updatePlayingCard();
        this.updateNowPlayingPreview();
    }

    // Wait until filters are mounted and at least some have their checked state applied
    async waitForFiltersReady({ min = 1, timeoutMs = 3000 } = {}) {
        const start = performance.now();
        const ready = () => document.querySelectorAll('input[data-filter]').length >= min;
        const checkedReady = () => Array.from(document.querySelectorAll('input[data-filter]')).some(el => el.checked);
        while (!(ready() && checkedReady())) {
            if (performance.now() - start > timeoutMs) break;
            await new Promise(r => requestAnimationFrame(r));
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
            
            this.renderFilterSection(filters.categories, this.categoryFilters, 'category');
            this.renderFilterSection(filters.channels, this.channelFilters, 'channel');
            this.renderFilterSection(filters.content_type, this.contentTypeFilters, 'content_type');
            this.renderFilterSection(filters.complexity_level, this.complexityFilters, 'complexity');
            this.renderLanguageFilters(filters.languages || []);
            this.renderFilterSection(filters.summary_type, this.summaryTypeFilters, 'summary_type');
            
            // Bind show more toggles after content is loaded
            this.bindShowMoreToggles();
            
            // Fix 1: Initialize currentFilters after filters render
            // This ensures visual state (checkboxes) matches internal state
            this.currentFilters = this.computeFiltersFromDOM();
            this.updateHeroBadges();
            console.log('Initialized currentFilters after render:', this.currentFilters);
            
        } catch (error) {
            console.error('Failed to load filters:', error);
        }
    }
    
    bindShowMoreToggles() {
        // Show more categories toggle
        const toggleMoreCategories = document.getElementById('toggleMoreCategories');
        const showMoreCategories = document.getElementById('showMoreCategories');
        if (toggleMoreCategories && showMoreCategories) {
            toggleMoreCategories.addEventListener('click', () => {
                const isHidden = showMoreCategories.classList.contains('hidden');
                showMoreCategories.classList.toggle('hidden');
                toggleMoreCategories.textContent = isHidden ? 'Show less' : 'Show more';
            });
        }
        
        // Show more channels toggle
        const toggleMoreChannels = document.getElementById('toggleMoreChannels');
        const showMoreChannels = document.getElementById('showMoreChannels');
        if (toggleMoreChannels && showMoreChannels) {
            toggleMoreChannels.addEventListener('click', () => {
                const isHidden = showMoreChannels.classList.contains('hidden');
                showMoreChannels.classList.toggle('hidden');
                toggleMoreChannels.textContent = isHidden ? 'Show less' : 'Show more';
            });
        }

        // Show more content types toggle
        const toggleMoreContentTypes = document.getElementById('toggleMoreContentTypes');
        const showMoreContentTypes = document.getElementById('showMoreContentTypes');
        if (toggleMoreContentTypes && showMoreContentTypes) {
            toggleMoreContentTypes.addEventListener('click', () => {
                const isHidden = showMoreContentTypes.classList.contains('hidden');
                showMoreContentTypes.classList.toggle('hidden');
                toggleMoreContentTypes.textContent = isHidden ? 'Show less' : 'Show more';
            });
        }
    }

    renderFilterSection(items, container, filterType) {
        if (!items || items.length === 0) {
            container.innerHTML = '<p class="text-xs text-slate-500 dark:text-slate-400">No data available</p>';
            return;
        }
        
        // Check if this is hierarchical data (categories with subcategories)
        const isHierarchical = filterType === 'category' && items.some(item => item.subcategories && item.subcategories.length > 0);
        
        // Show first 3 items in main area
        const mainItems = items.slice(0, 3);
        const additionalItems = items.slice(3);
        
        // Create hierarchical filter HTML for categories with subcategories
        const createHierarchicalHTML = (item) => {
            const hasSubcategories = item.subcategories && item.subcategories.length > 0;
            const categoryId = `category-${item.value.replace(/[^a-zA-Z0-9]/g, '-')}`;
            
            let html = `
                <div class="category-group mb-2">
                    <div class="flex items-center space-x-2 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700 rounded px-2 py-1 transition-colors">
                        <input type="checkbox" 
                               value="${this.escapeHtml(item.value)}" 
                               data-filter="${filterType}"
                               data-category-parent="${this.escapeHtml(item.value)}"
                               checked
                               class="rounded border-slate-300 dark:border-slate-600 text-audio-500 focus:ring-audio-500 focus:ring-offset-0">
                        ${hasSubcategories ? `
                            <button class="category-expand-btn text-slate-400 hover:text-slate-600 p-1" 
                                    data-category-target="${categoryId}">
                                <svg class="w-3 h-3 transform transition-transform" viewBox="0 0 12 12">
                                    <path d="M4 2L8 6L4 10" stroke="currentColor" stroke-width="1.5" fill="none"/>
                                </svg>
                            </button>
                        ` : '<div class="w-5"></div>'}
                        <span class="text-sm text-slate-700 dark:text-slate-200 flex-1">${this.escapeHtml(item.value)}</span>
                        <span class="text-xs text-slate-400 dark:text-slate-500 mr-2">${item.count}</span>
                        <button class="filter-only-btn text-xs text-audio-600 hover:text-audio-700 hover:underline" 
                                data-filter-only="category" 
                                data-filter-only-value="${this.escapeHtml(item.value)}"
                                title="Show only ${this.escapeHtml(item.value)}">only</button>
                    </div>
                    ${hasSubcategories ? `
                        <div id="${categoryId}" class="subcategory-list ml-8 mt-1 hidden">
                            ${item.subcategories.map(sub => `
                                <label class="flex items-center space-x-2 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700 rounded px-2 py-1 transition-colors">
                                    <input type="checkbox" 
                                           value="${this.escapeHtml(sub.value)}" 
                                           data-filter="subcategory"
                                           data-parent-category="${this.escapeHtml(item.value)}"
                                           checked
                                           class="rounded border-slate-300 dark:border-slate-600 text-audio-500 focus:ring-audio-500 focus:ring-offset-0">
                                    <span class="text-sm text-slate-600 dark:text-slate-300 flex-1">${this.escapeHtml(sub.value)}</span>
                                    <span class="text-xs text-slate-400 dark:text-slate-500 mr-2">${sub.count}</span>
                                    <button class="filter-only-btn text-xs text-audio-600 hover:text-audio-700 hover:underline" 
                                            data-filter-only="subcategory" 
                                            data-filter-only-value="${this.escapeHtml(sub.value)}"
                                            data-parent-category="${this.escapeHtml(item.value)}"
                                            title="Show only ${this.escapeHtml(sub.value)}">only</button>
                                </label>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>
            `;
            return html;
        };
        
        // Create simple filter HTML for non-hierarchical items
        const createFilterHTML = (item) => `
            <div class="flex items-center space-x-2 hover:bg-slate-50 dark:hover:bg-slate-700 rounded px-2 py-1 transition-colors">
                <label class="flex items-center space-x-2 cursor-pointer flex-1">
                    <input type="checkbox" 
                           value="${this.escapeHtml(item.value)}" 
                           data-filter="${filterType}"
                           checked
                           class="rounded border-slate-300 dark:border-slate-600 text-audio-500 focus:ring-audio-500 focus:ring-offset-0">
                    <span class="text-sm text-slate-700 dark:text-slate-200">${this.escapeHtml(item.value)}</span>
                    <span class="text-xs text-slate-400 dark:text-slate-500">${item.count}</span>
                </label>
                <button class="text-xs text-audio-600 dark:text-audio-400 hover:text-audio-700 dark:hover:text-audio-300 transition-colors cursor-pointer" 
                        data-filter-only="${filterType}" 
                        data-filter-only-value="${this.escapeHtml(item.value)}"
                        title="Show only ${this.escapeHtml(item.value)}">only</button>
            </div>
        `;
        
        // Choose the appropriate HTML creator
        const htmlCreator = isHierarchical ? createHierarchicalHTML : createFilterHTML;
        
        // Render main items - insert before existing show more structure
        const mainHTML = mainItems.map(htmlCreator).join('');
        
        // Find the existing structure elements 
        const existingShowMore = container.querySelector(`[id^="showMore"]`);
        const existingToggle = container.querySelector(`[id^="toggleMore"]`);
        
        if (existingShowMore && existingToggle) {
            // Replace everything before the show more div
            const showMoreHTML = existingShowMore.outerHTML;
            const toggleHTML = existingToggle.outerHTML;
            container.innerHTML = mainHTML + showMoreHTML + toggleHTML;
            
            // Re-get elements after innerHTML change
            const showMoreContainer = container.querySelector(`[id^="showMore"]`);
            const toggleButton = container.querySelector(`[id^="toggleMore"]`);
            
            // Render additional items in show more section
            if (additionalItems.length > 0 && showMoreContainer) {
                showMoreContainer.innerHTML = additionalItems.map(htmlCreator).join('');
                
                // Show the toggle button
                if (toggleButton) toggleButton.classList.remove('hidden');
            } else {
                // Hide toggle button if no additional items
                if (toggleButton) toggleButton.classList.add('hidden');
            }
        } else {
            // No show more functionality, render all items
            container.innerHTML = items.map(htmlCreator).join('');
        }

        // Bind filter change events to all checkboxes
        container.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', () => this.handleFilterChange());
        });
        
        // Add expand/collapse functionality for hierarchical categories
        if (isHierarchical) {
            container.querySelectorAll('.category-expand-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const targetId = btn.dataset.categoryTarget;
                    const subcategoryList = document.getElementById(targetId);
                    const arrow = btn.querySelector('svg');
                    
                    if (subcategoryList) {
                        const isHidden = subcategoryList.classList.contains('hidden');
                        subcategoryList.classList.toggle('hidden');
                        arrow.style.transform = isHidden ? 'rotate(90deg)' : 'rotate(0deg)';
                    }
                });
            });
            
            // Handle parent-child checkbox relationships
            this.bindCategoryCheckboxLogic(container);
        }
    }
    
    bindCategoryCheckboxLogic(container) {
        // Handle parent category checkbox changes
        container.querySelectorAll('input[data-category-parent]').forEach(parentCheckbox => {
            parentCheckbox.addEventListener('change', () => {
                const categoryName = parentCheckbox.dataset.categoryParent;
                const subcategoryCheckboxes = container.querySelectorAll(`input[data-parent-category="${categoryName}"]`);
                
                // When parent is checked/unchecked, update all subcategories
                subcategoryCheckboxes.forEach(subCheckbox => {
                    subCheckbox.checked = parentCheckbox.checked;
                });
                
                this.handleFilterChange();
            });
        });
        
        // Handle subcategory checkbox changes  
        container.querySelectorAll('input[data-parent-category]').forEach(subCheckbox => {
            subCheckbox.addEventListener('change', () => {
                const categoryName = subCheckbox.dataset.parentCategory;
                const parentCheckbox = container.querySelector(`input[data-category-parent="${categoryName}"]`);
                const allSubcategoryCheckboxes = container.querySelectorAll(`input[data-parent-category="${categoryName}"]`);
                
                if (parentCheckbox) {
                    // Check if all subcategories are checked
                    const allChecked = Array.from(allSubcategoryCheckboxes).every(cb => cb.checked);
                    const someChecked = Array.from(allSubcategoryCheckboxes).some(cb => cb.checked);
                    
                    // Update parent checkbox state
                    parentCheckbox.checked = allChecked;
                    parentCheckbox.indeterminate = !allChecked && someChecked;
                }
                
                this.handleFilterChange();
            });
        });
    }

    renderLanguageFilters(languages) {
        const mainContainer = this.languageFilters;
        const showMoreContainer = document.getElementById('showMoreLanguages');
        const toggleButton = document.getElementById('toggleMoreLanguages');
        
        if (!languages || languages.length === 0) {
            mainContainer.innerHTML = '<p class="text-xs text-slate-500 dark:text-slate-400">No language data available</p>';
            return;
        }
        
        // Show first 3 languages in main area
        const mainLanguages = languages.slice(0, 3);
        const additionalLanguages = languages.slice(3);
        
        // Render main languages (preserve the showMoreLanguages structure) - default all to checked
        const mainHTML = mainLanguages.map(item => `
            <label class="flex items-center space-x-2 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700 rounded px-2 py-1 transition-colors">
                <input type="checkbox" 
                       value="${this.escapeHtml(item.value)}" 
                       data-filter="language"
                       checked
                       class="rounded border-slate-300 dark:border-slate-600 text-audio-500 focus:ring-audio-500 focus:ring-offset-0">
                <span class="text-sm text-slate-700 dark:text-slate-200 flex-1">${this.escapeHtml(item.value)}</span>
                <span class="text-xs text-slate-400 dark:text-slate-500">${item.count}</span>
            </label>
        `).join('');
        
        // Update main container while preserving structure
        const existingStructure = mainContainer.innerHTML;
        const showMoreIndex = existingStructure.indexOf('<div id="showMoreLanguages"');
        if (showMoreIndex !== -1) {
            mainContainer.innerHTML = mainHTML + existingStructure.substring(showMoreIndex);
        } else {
            mainContainer.innerHTML = mainHTML;
        }
        
        // Render additional languages in show more section
        if (additionalLanguages.length > 0 && showMoreContainer) {
            showMoreContainer.innerHTML = additionalLanguages.map(item => `
                <label class="flex items-center space-x-2 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700 rounded px-2 py-1 transition-colors">
                    <input type="checkbox" 
                           value="${this.escapeHtml(item.value)}" 
                           data-filter="language"
                           checked
                           class="rounded border-slate-300 dark:border-slate-600 text-audio-500 focus:ring-audio-500 focus:ring-offset-0">
                    <span class="text-sm text-slate-700 dark:text-slate-200 flex-1">${this.escapeHtml(item.value)}</span>
                    <span class="text-xs text-slate-400 dark:text-slate-500">${item.count}</span>
                </label>
            `).join('');
            
            // Show the toggle button
            if (toggleButton) toggleButton.classList.remove('hidden');
        } else {
            // Hide toggle button if no additional languages
            if (toggleButton) toggleButton.classList.add('hidden');
        }
        
        // Add event listeners to all language checkboxes
        mainContainer.querySelectorAll('input[type="checkbox"][data-filter="language"]').forEach(checkbox => {
            checkbox.addEventListener('change', () => this.handleFilterChange());
        });
    }

    computeFiltersFromDOM() {
        const filters = {};
        document.querySelectorAll('input[data-filter]').forEach(el => {
            const k = el.getAttribute('data-filter');
            (filters[k] ||= []);
            if (el.checked) filters[k].push(el.value);
        });
        
        // Add parent category context for subcategories
        const selectedSubcategories = document.querySelectorAll('input[data-filter="subcategory"]:checked');
        if (selectedSubcategories.length > 0) {
            const parentCategories = new Set();
            selectedSubcategories.forEach(el => {
                const parent = el.getAttribute('data-parent-category');
                if (parent) parentCategories.add(parent);
            });
            if (parentCategories.size > 0) {
                filters.parentCategory = Array.from(parentCategories);
            }
        }
        
        return filters;
    }

    // Hierarchical facet reader: parents + children grouped by parent
    computeFacetState() {
        const categories = new Set();
        const subcats = {};
        // Parent categories explicitly checked
        document.querySelectorAll('input[data-filter="category"]').forEach(el => {
            const name = el.value;
            const anyChildChecked = Array.from(document.querySelectorAll(`input[data-filter="subcategory"][data-parent-category="${CSS.escape(name)}"]`)).some(sc => sc.checked);
            if (el.checked || anyChildChecked) categories.add(name);
        });
        // Children grouped by parent
        document.querySelectorAll('input[data-filter="subcategory"]').forEach(el => {
            if (!el.checked) return;
            const parent = el.getAttribute('data-parent-category');
            if (!parent) return;
            (subcats[parent] ||= []).push(el.value);
        });
        return { categories: Array.from(categories), subcats };
    }

    async loadContent() {
        const params = new URLSearchParams();
        
        // Add search query
        if (this.searchQuery) params.append('q', this.searchQuery);
        
        // Fix 2: Recompute state from DOM right before fetching (prevents drift)
        this.currentFilters = this.computeFiltersFromDOM();
        this.updateHeroBadges();
        const facet = this.computeFacetState();
        
        // Helper functions (OpenAI's drop-in solution)
        const getAllOptions = (filterType) =>
            Array.from(document.querySelectorAll(`input[data-filter="${filterType}"]`))
                .map(el => el.value);

        const anySelected = (filters) =>
            Object.values(filters).some(arr => Array.isArray(arr) && arr.length > 0);

        const noneSelected = (filters) =>
            !anySelected(filters);

        // REQUIRE Category selection (original logic)
        if (!this.searchQuery && (!facet.categories || facet.categories.length === 0)) {
            this.currentItems = [];
            this.renderContent([]);
            this.renderPagination({ page: 1, size: 12, total_count: 0, total_pages: 0, has_next: false, has_prev: false });
            this.updateResultsInfo({ page: 1, size: 12, total_count: 0, total_pages: 0 });
            this.contentGrid.innerHTML = `
                <div class="text-center py-12 text-slate-400">
                    <div class="text-lg mb-2">Choose one or more categories</div>
                    <div class="text-sm">Clear Categories = no categories selected → no results</div>
                </div>`;
            return;
        }

        // REQUIRE Channel selection when any channels exist but none selected
        const hasChannelSelection = this.currentFilters.channel && this.currentFilters.channel.length > 0;
        const hasChannelOptions = document.querySelectorAll('input[data-filter="channel"]').length > 0;
        if (!this.searchQuery && hasChannelOptions && !hasChannelSelection) {
            this.currentItems = [];
            this.renderContent([]);
            this.renderPagination({ page: 1, size: 12, total_count: 0, total_pages: 0, has_next: false, has_prev: false });
            this.updateResultsInfo({ page: 1, size: 12, total_count: 0, total_pages: 0 });
            this.contentGrid.innerHTML = `
                <div class="text-center py-12 text-slate-400">
                    <div class="text-lg mb-2">Choose one or more channels</div>
                    <div class="text-sm">Clear Channels = no channels selected → no results</div>
                </div>`;
            return;
        }

        // Build effectiveFilters by treating "ALL selected" as no filter for that type
        const effectiveFilters = {};
        Object.entries(this.currentFilters).forEach(([filterType, selectedValues]) => {
            const allValues = getAllOptions(filterType);
            const sel = Array.isArray(selectedValues) ? selectedValues : [];
            if (sel.length === 0) {
                // none selected for this type → contributes nothing here
                return;
            }
            if (sel.length < allValues.length) {
                // some selected → apply filter
                effectiveFilters[filterType] = sel;
            }
            // if sel.length === allValues.length → treat as unfiltered for this type
        });

        // Override category logic using hierarchical facets
        if (facet.categories && facet.categories.length) {
            const allCats = getAllOptions('category');
            if (facet.categories.length < allCats.length) {
                effectiveFilters.category = facet.categories;
            } else {
                delete effectiveFilters.category; // all → unfiltered
            }
        }

        // Quick sanity logs (temporarily)
        console.debug('DOM->currentFilters:', this.currentFilters);
        console.debug('effectiveFilters:', effectiveFilters);

        // ✅ Require selection model:
        // none selected across ALL types → show nothing and stop
        if (noneSelected(this.currentFilters) && !this.searchQuery) {
            console.debug('Hit empty state: no filters selected');
            this.currentItems = [];
            this.renderContent([]);
            this.renderPagination({ page: 1, size: 12, total_count: 0, total_pages: 0, has_next: false, has_prev: false });
            this.updateResultsInfo({ page: 1, size: 12, total_count: 0, total_pages: 0 });
            this.contentGrid.innerHTML = `
                <div class="text-center py-12 text-slate-400">
                    <div class="text-lg mb-2">Choose one or more filters</div>
                    <div class="text-sm">Clear All = nothing selected → no results</div>
                </div>`;
            return;
        }

        // Helper function to normalize parameter values (per OpenAI recommendation)
        const normalizeLabel = (label) => {
            return String(label)
                .trim()                    // Remove leading/trailing whitespace
                .replace(/–/g, '-')        // Convert en-dash to hyphen
                .replace(/\s+/g, ' ')      // Collapse multiple spaces
                .substring(0, 100);        // Prevent extremely long parameters
        };

        // Check if server will handle subcategory filtering (to disable client-side narrowing)
        const hasServerSubcatFilter = Array.isArray(effectiveFilters.subcategory) && effectiveFilters.subcategory.length > 0;
        console.log(`[YTV2] Server subcategory filtering: ${hasServerSubcatFilter}`);
        
        // Build params with special handling for subcategories
        Object.entries(effectiveFilters).forEach(([key, values]) => {
            if (key === 'subcategory') {
                // For subcategories, we need to send parentCategory instead of category
                values.forEach(subcatValue => {
                    const normalizedSubcat = normalizeLabel(subcatValue);
                    console.log(`[YTV2] Adding param: subcategory=${normalizedSubcat} (original: ${subcatValue})`);
                    params.append('subcategory', normalizedSubcat);
                    
                    // Find the parent category for this subcategory
                    const subcatInput = document.querySelector(`input[data-filter="subcategory"][value="${CSS.escape(subcatValue)}"]`);
                    if (subcatInput && subcatInput.dataset.parentCategory) {
                        const normalizedParent = normalizeLabel(subcatInput.dataset.parentCategory);
                        console.log(`[YTV2] Adding param: parentCategory=${normalizedParent} (for subcategory: ${subcatValue})`);
                        params.append('parentCategory', normalizedParent);
                    }
                });
            } else if (key === 'category' && effectiveFilters.subcategory && effectiveFilters.subcategory.length > 0) {
                // Skip category if we have subcategories (parentCategory will be used instead)
                console.log(`[YTV2] Skipping category param because subcategories are present`);
            } else {
                // Handle all other filter types normally
                values.forEach(v => {
                    const normalizedValue = normalizeLabel(v);
                    console.log(`[YTV2] Adding param: ${key}=${normalizedValue} (original: ${v})`);
                    params.append(key, normalizedValue);
                });
            }
        });
        
        // Deduplicate parentCategory parameters (per OpenAI recommendation)
        const dedupeParam = (key) => {
            const all = params.getAll(key);
            if (all.length > 1) {
                const unique = [...new Set(all)];
                params.delete(key);
                unique.forEach(v => params.append(key, v));
                console.log(`[YTV2] Deduplicated ${key}: ${all.length} -> ${unique.length} values`);
            }
        };
        dedupeParam('parentCategory');
        
        console.debug('Final URL params:', params.toString());
        
        // Add pagination and sorting
        params.append('page', this.currentPage.toString());
        params.append('size', '12'); // Show 12 items per page
        params.append('sort', this.currentSort);

        try {
            const requestUrl = `/api/reports?${params}`;
            console.log('[YTV2] Request URL:', requestUrl); // Debug logging per OpenAI
            const response = await fetch(requestUrl);
            const data = await response.json();
            
            // Handle API errors (per OpenAI recommendation)
            if (!response.ok) {
                console.error('API error:', data);
                this.showError(data?.message || 'Failed to load content');
                return; // Don't try to process pagination/items
            }
            
            let items = data.reports || data.data || [];
            console.log(`[YTV2] Items from server: ${items.length}`);

            // 🚫 Skip client-side narrowing if server already filtered by subcategory
            if (hasServerSubcatFilter) {
                console.log(`[YTV2] Skipping client-side narrowing - server already filtered by subcategory`);
            } else {
                console.log(`[YTV2] Applying legacy client-side subcategory narrowing`);
                // Client-side subcategory narrowing (per parent). Within a selected
                // parent, if some-but-not-all subcats are checked, keep only those.
                const restrictingParents = Object.entries(facet.subcats)
                    .filter(([parent, arr]) => {
                        const total = document.querySelectorAll(`input[data-filter="subcategory"][data-parent-category="${CSS.escape(parent)}"]`).length;
                        return Array.isArray(arr) && arr.length > 0 && arr.length < total;
                    })
                    .map(([parent]) => parent);

                if (restrictingParents.length) {
                    const allowedByParent = new Map(Object.entries(facet.subcats));
                    items = items.filter(it => {
                        const cats = Array.isArray(it.analysis?.category) ? it.analysis.category : [it.analysis?.category].filter(Boolean);
                        const sub = it.analysis?.subcategory || '';
                        // If item matches any restricting parent, it must satisfy its subcat list
                        for (const p of restrictingParents) {
                            if (cats.includes(p)) {
                                const allowed = allowedByParent.get(p) || [];
                                return allowed.includes(sub);
                            }
                        }
                        // Otherwise, if item belongs to a selected parent with no subcat restriction, allow
                        if (facet.categories && facet.categories.length) {
                            return cats.some(c => facet.categories.includes(c));
                        }
                        // If no parents selected (unlikely due to require-selection), keep as-is
                        return true;
                    });
                }
            }
            console.log(`[YTV2] Final items after narrowing: ${items.length}`);


            this.currentItems = items;
            this.updateLatestIndexFromItems(items);
            this.renderContent(this.currentItems);
            this.renderPagination(data.pagination);
            this.updateResultsInfo(data.pagination);
            const playableItems = this.rebuildPlaylist(this.currentItems);
            if (playableItems.length > 0) {
                this.currentTrackIndex = 0;
                this.setCurrentFromItem(playableItems[0]);
            } else {
                this.currentTrackIndex = -1;
                this.showNowPlayingPlaceholder();
            }
            this.renderQueue();
        } catch (error) {
            console.error('Failed to load content:', error);
            this.showError('Failed to load content');
        }
    }

    renderContent(items) {
        // Safety check for undefined items
        if (!items || !Array.isArray(items)) {
            console.warn('renderContent called with invalid items:', items);
            this.contentGrid.innerHTML = '<div class="text-center py-8 text-gray-400">No summaries available</div>';
            return;
        }
        
        // Show helpful message when no items to display
        if (items.length === 0) {
            const hasActiveFilters = Object.keys(this.currentFilters).some(key => 
                this.currentFilters[key] && this.currentFilters[key].length > 0
            );
            
            // Helper functions for empty state
            const anySelected = (filters) =>
                Object.values(filters).some(arr => Array.isArray(arr) && arr.length > 0);
            
            const hasQueryOrFilters = this.searchQuery || anySelected(this.currentFilters);
            this.contentGrid.innerHTML = hasQueryOrFilters
                ? `<div class="text-center py-12 text-slate-400">
                     <div class="text-lg mb-2">No matches found</div>
                     <div class="text-sm">Try adjusting your filters or search terms</div>
                   </div>`
                : `<div class="text-center py-12 text-slate-400">
                     <div class="text-lg mb-2">Choose one or more filters</div>
                     <div class="text-sm">Nothing is selected—select filters to see results</div>
                   </div>`;
            return;
        }
        
        const html = this.viewMode === 'grid'
            ? `<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">${items.map(i => this.createGridCard(i)).join('')}</div>`
            : items.map(i => this.createContentCard(i)).join('');
        this.contentGrid.innerHTML = html;

        // Make whole card clickable (except controls)
        this.contentGrid.querySelectorAll('[data-card]').forEach(card => {
            card.addEventListener('click', (e) => {
                if (this._suppressOpen) { e.preventDefault(); e.stopPropagation(); return; }
                // Ignore if click on a control, action, or filter chip
                if (e.target.closest('[data-control]') || e.target.closest('[data-action]') || e.target.closest('[data-filter-chip]')) return;
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

        // Bind filter chip click handlers
        this.contentGrid.querySelectorAll('[data-filter-chip]').forEach(chip => {
            chip.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent card click
                const filterType = chip.dataset.filterChip;
                const filterValue = chip.dataset.filterValue;
                const parent = chip.dataset.parentCategory || null;
                this.applyFilterFromChip(filterType, filterValue, parent);
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
            // If tapping Listen on the currently selected item, toggle play/pause
            if (this.currentAudio && this.currentAudio.id === id) {
                this.togglePlayPause();
            } else {
                this.playAudio(id);
            }
            this.sendTelemetry('cta_listen', { id });
        }
        if (action === 'read') { this.handleRead(id); this.sendTelemetry('cta_read', { id }); }
        if (action === 'watch') { this.openYoutube(card.dataset.videoId); this.sendTelemetry('cta_watch', { id, video_id: card.dataset.videoId }); }
        if (action === 'delete') { this._lastDeleteTrigger = btn; this.toggleDeletePopover(card, true); }
        if (action === 'menu') { this.toggleKebabMenu(card, true, btn); }
        if (action === 'menu-close') { this.toggleKebabMenu(card, false); }
        if (action === 'copy-link') { this.copyLink(card, id); this.toggleKebabMenu(card, false); }
        if (action === 'reprocess') {
            this.toggleKebabMenu(card, false);
            this.openReprocessModal(id, card);
        }
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
        if (readBtn) { 
            readBtn.setAttribute('aria-controls', region.id); 
            readBtn.setAttribute('aria-expanded', 'true');
            // Update arrow to point down when expanded
            const arrow = readBtn.querySelector('span[aria-hidden="true"]');
            if (arrow) arrow.innerHTML = '▼';
        }
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
        if (readBtn) {
            readBtn.setAttribute('aria-expanded', 'false');
            // Update arrow back to right when collapsed
            const arrow = readBtn.querySelector('span[aria-hidden="true"]');
            if (arrow) arrow.innerHTML = '›';
        }
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
            // Insert at card level to span full width
            card.appendChild(region);
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
          <div class="mt-3 mx-[-1rem] md:mx-[-1rem] sm:mx-0 rounded-xl bg-white/70 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 p-3 md:p-4">
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
        // Use new normalization method to handle both string and object summary content
        let summaryContent = data.summary;
        let summaryType = data.summary?.type;

        // Handle different data structures
        if (typeof summaryContent === 'string') {
            summaryRaw = summaryContent;
        } else if (summaryContent && typeof summaryContent === 'object') {
            // First try direct properties (summary.comprehensive, summary.summary, etc.)
            if (summaryContent.content) {
                summaryRaw = this.normalizeSummaryContent(summaryContent.content, summaryType);
            } else {
                summaryRaw = this.normalizeSummaryContent(summaryContent, summaryType);
            }
        }

        // Additional fallbacks if normalization didn't work - prioritize direct summary_text field
        if (!summaryRaw) summaryRaw = data.summary_text || data.analysis?.summary || data.analysis?.summary_text || data.summary_preview || '';
        
        // Fallback to bullet arrays if available
        if (!summaryRaw && Array.isArray(data.summary?.bullets)) {
            summaryRaw = data.summary.bullets
                .map(b => (typeof b === 'string' ? `• ${b}` : ''))
                .filter(Boolean)
                .join('\n');
        }
        if (!summaryRaw && Array.isArray(data.analysis?.key_points)) {
            summaryRaw = data.analysis.key_points.map(b => typeof b === 'string' ? `• ${b}` : '').filter(Boolean).join('\n');
        }

        // Final string coercion and cleanup
        summaryRaw = String(summaryRaw || '').replace(/\r\n?/g, '\n').trim();
        const summary = this.formatKeyPoints(summaryRaw);

        return `
          <div class="mt-3 mx-[-1rem] md:mx-[-1rem] sm:mx-0 rounded-xl bg-white/80 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 p-3 md:p-4 space-y-3 md:space-y-4" data-expanded>
            ${badges.length ? `<div class="flex items-center gap-2.5 text-slate-600 dark:text-slate-300 text-sm flex-wrap">${badges.join('')}</div>` : ''}
            <h4 class="sr-only" data-expanded-title>Summary</h4>
            <div class="prose prose-sm sm:prose-base prose-slate dark:prose-invert max-w-none leading-6 sm:leading-7 w-full break-words">${summary}</div>
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

    openReprocessModal(reportId, card) {
        if (!this.reprocessModal) {
            this.showToast('Reprocess dialog unavailable', 'error');
            return;
        }
        const item = (this.currentItems || []).find((x) => x.file_stem === reportId) || null;
        const title = item?.title || card?.querySelector('h3')?.textContent?.trim() || reportId;
        const videoId = item?.video_id || card?.dataset.videoId;
        if (!videoId) {
            this.showToast('Missing video id for reprocess', 'error');
            return;
        }

        this.pendingReprocess = {
            id: reportId,
            videoId,
            title,
            hasAudio: Boolean(item?.media?.has_audio || card?.dataset.hasAudio === 'true')
        };

        if (this.reprocessText) {
            const safeTitle = this.escapeHtml(title || 'this video');
            this.reprocessText.innerHTML = `Re-run the summarizer for <strong>${safeTitle}</strong>?`;
        }
        if (this.reprocessAudioToggle) {
            this.reprocessAudioToggle.checked = Boolean(this.pendingReprocess.hasAudio);
        }

        this.updateReprocessFootnote();

        this.reprocessModal.classList.remove('hidden');
        this.reprocessModal.classList.add('flex');
        this.reprocessModal.setAttribute('aria-hidden', 'false');
        const focusTarget = this.confirmReprocessBtn || this.cancelReprocessBtn;
        if (focusTarget) focusTarget.focus();
    }

    closeReprocessModal() {
        if (this.reprocessModal) {
            this.reprocessModal.classList.add('hidden');
            this.reprocessModal.classList.remove('flex');
            this.reprocessModal.setAttribute('aria-hidden', 'true');
        }
        if (this.confirmReprocessBtn) {
            this.confirmReprocessBtn.disabled = false;
        }
        this.pendingReprocess = null;
    }

    async submitReprocess() {
        if (!this.pendingReprocess) return;
        const videoId = this.pendingReprocess.videoId;
        if (!videoId) {
            this.showToast('Missing video id for reprocess', 'error');
            return;
        }
        const regenerateAudio = this.reprocessAudioToggle ? !!this.reprocessAudioToggle.checked : true;
        const token = this.getReprocessToken();
        if (!token) {
            this.showToast('Reprocess token required', 'warn');
            return;
        }

        if (this.confirmReprocessBtn) {
            this.confirmReprocessBtn.disabled = true;
        }

        try {
            const payload = {
                video_id: videoId,
                summary_types: ['comprehensive'],
                regenerate_audio: regenerateAudio
            };
            const response = await fetch('/api/reprocess', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Reprocess-Token': token
                },
                body: JSON.stringify(payload)
            });
            if (!response.ok) {
                const text = await response.text();
                throw new Error(text || `HTTP ${response.status}`);
            }
            this.showToast(`Reprocess scheduled for ${this.describeVideo(this.pendingReprocess)}`, 'success');
            this.requestMetricsRefresh(2000);
            this.closeReprocessModal();
        } catch (error) {
            console.error('Reprocess request failed', error);
            this.showToast(`Reprocess failed: ${error.message || error}`, 'error');
        } finally {
            if (this.confirmReprocessBtn) {
                this.confirmReprocessBtn.disabled = false;
            }
        }
    }

    async handleDelete(id, cardEl) {
        try {
            // Optimistic UI: show busy state
            const pop = cardEl.querySelector('[data-delete-popover]');
            if (pop) pop.classList.add('pointer-events-none', 'opacity-60');

            // Use video_id from card dataset, not the generic id
            const videoId = cardEl.dataset.videoId;
            if (!videoId) {
                throw new Error('No video ID found on card');
            }

            // Use the proper DELETE endpoint format with video_id
            const res = await fetch(`/api/delete/${encodeURIComponent(videoId)}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!res.ok) {
                const errorText = await res.text();
                throw new Error(`HTTP ${res.status}: ${errorText}`);
            }
            
            const result = await res.json();
            
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
            this.showToast(`Delete failed: ${err.message}`, 'error');
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
        // Normalize field names between SQLite and PostgreSQL APIs
        const title = item.title || 'Untitled';
        const channel = item.channel ?? item.channel_name ?? 'Unknown Channel';
        const analysis = item.analysis ?? item.analysis_json ?? {};
        const fileStem = item.file_stem ?? item.video_id ?? '';

        // Create normalized item for consistent access
        const normalizedItem = { ...item, title, channel, analysis, file_stem: fileStem, summary_type: item.summary_variant || item.summary_type || 'unknown' };

        const duration = this.formatDuration(normalizedItem.duration_seconds || 0);
        
        const hasAudio = normalizedItem.media?.has_audio;
        const href = `/${normalizedItem.file_stem}.json?v=2`;
        const buttonDurations = this.getButtonDurations(normalizedItem);
        const { categories, subcats, subcatPairs } = this.extractCatsAndSubcats(normalizedItem);
        const totalSecs = (normalizedItem.media_metadata && normalizedItem.media_metadata.mp3_duration_seconds) ? normalizedItem.media_metadata.mp3_duration_seconds : (normalizedItem.duration_seconds || 0);
        const totalDur = (normalizedItem.media_metadata && normalizedItem.media_metadata.mp3_duration_seconds)
            ? this.formatDuration(normalizedItem.media_metadata.mp3_duration_seconds)
            : (normalizedItem.duration_seconds ? this.formatDuration(normalizedItem.duration_seconds) : '');

        const isPlaying = this.currentAudio && this.currentAudio.id === normalizedItem.file_stem && this.isPlaying;
        const channelInitial = (normalizedItem.channel || '?').trim().charAt(0).toUpperCase();
        return `
            <div data-card data-report-id=\"${normalizedItem.file_stem}\" data-video-id=\"${normalizedItem.video_id || ''}\" data-has-audio=\"${hasAudio ? 'true' : 'false'}\" data-href=\"${href}\" title=\"Open summary\" tabindex=\"0\" class=\"group relative list-layout cursor-pointer overflow-hidden rounded-2xl border border-white/60 dark:border-slate-800/70 bg-white/85 dark:bg-slate-900/65 backdrop-blur-lg p-4 sm:p-5 shadow-lg transition-all duration-200 hover:-translate-y-1 hover:shadow-2xl ${isPlaying ? 'is-playing' : ''}\" style=\"--thumbW: 240px;\">
                <div class=\"card-glow absolute inset-0 bg-gradient-to-br from-audio-500/15 via-transparent to-indigo-500/20\"></div>
                <div class=\"relative flex flex-col sm:flex-row gap-3 sm:gap-4 items-start\">
                    <div class=\"relative w-full sm:w-56 aspect-video overflow-hidden rounded-xl bg-slate-100/90 dark:bg-slate-800/80 ring-1 ring-slate-200/70 dark:ring-slate-700/60 shadow-inner flex-shrink-0\">
                        ${normalizedItem.thumbnail_url ? `<img src=\"${normalizedItem.thumbnail_url}\" alt=\"thumbnail\" loading=\"lazy\" class=\"absolute inset-0 w-full h-full object-cover\">` : ''}
                        <div class=\"absolute inset-0 flex items-center justify-center pointer-events-none ${isPlaying ? '' : 'hidden'}\" data-card-eq>
                            <div class=\"px-2 py-1 rounded-md bg-black/45 backdrop-blur\">
                                <div class=\"flex items-end gap-1.5 text-white\">
                                    <span class=\"w-0.5 sm:w-1 h-3 sm:h-4 bg-current waveform-bar\" style=\"--delay:0\"></span>
                                    <span class=\"w-0.5 sm:w-1 h-4 sm:h-6 bg-current waveform-bar\" style=\"--delay:1\"></span>
                                    <span class=\"w-0.5 sm:w-1 h-6 sm:h-8 bg-current waveform-bar\" style=\"--delay:2\"></span>
                                    <span class=\"w-0.5 sm:w-1 h-4 sm:h-6 bg-current waveform-bar\" style=\"--delay:3\"></span>
                                    <span class=\"w-0.5 sm:w-1 h-3 sm:h-4 bg-current waveform-bar\" style=\"--delay:4\"></span>
                                </div>
                            </div>
                        </div>
                        <div class=\"absolute inset-x-4 bottom-3 h-1.5 bg-black/25 rounded-full overflow-hidden cursor-pointer\" data-card-progress-container data-total-seconds=\"${totalSecs}\">
                            <div class=\"h-full bg-gradient-to-r from-audio-500 to-indigo-500\" style=\"width:0%\" data-card-progress role=\"progressbar\" aria-valuemin=\"0\" aria-valuemax=\"100\" aria-valuenow=\"0\"></div>
                        </div>
                    </div>
                    <div class=\"flex-1 min-w-0\">
                        <div class=\"flex items-start justify-between gap-3\">
                            <div class=\"flex-1 min-w-0 pr-12 space-y-3\">
                                <h3 class=\"text-base sm:text-lg font-semibold text-slate-800 dark:text-slate-100 group-hover:text-audio-700 transition-colors line-clamp-2\">
                                    ${this.escapeHtml(normalizedItem.title)}
                                </h3>
                                <div class=\"flex flex-wrap items-center gap-2.5.5 text-xs leading-tight text-slate-600 dark:text-slate-300\">
                                    <span class=\"inline-flex items-center justify-center w-6 h-6 rounded-full bg-white/80 dark:bg-slate-800/80 border border-white/60 dark:border-slate-700/70 text-[11px] font-semibold text-slate-600 dark:text-slate-200 shadow-sm\">${channelInitial}</span>
                                    <button class=\"truncate max-w-[12rem] hover:text-audio-600 dark:hover:text-audio-400 transition-colors text-left\" data-filter-chip=\"channel\" data-filter-value=\"${this.escapeHtml(normalizedItem.channel || '')}\" title=\"Filter by ${this.escapeHtml(normalizedItem.channel || '')}\">${this.escapeHtml(normalizedItem.channel || '')}</button>
                                    ${this.renderLanguageChip(normalizedItem.analysis?.language)}
                                    ${this.renderSummaryTypeChip(normalizedItem.summary_type)}
                                    ${isPlaying ? '<span class=\"inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-audio-100 text-audio-700 text-[10px] font-semibold shadow-sm\"><span class=\"inline-flex h-1.5 w-1.5 rounded-full bg-audio-500\"></span>Now playing</span>' : ''}
                                </div>
                                ${categories.length ? `
                                  <div class=\"mt-1 flex items-center gap-1.5.5 flex-wrap\">
                                    ${categories.map(cat => this.renderChip(cat, 'category')).join('')}
                                  </div>` : ''}
                                ${Array.isArray(subcatPairs) && subcatPairs.length ? `
                                  <div class=\"mt-1 flex items-center gap-1.5.5 flex-wrap\">
                                    ${subcatPairs.map(([p, sc]) => this.renderChip(sc, 'subcategory', false, p)).join('')}
                                  </div>` : ''}
                            </div>
                            <div class=\"absolute top-3 right-3 z-20\">
                              <button class=\"p-2 rounded-full border border-white/50 dark:border-slate-700/70 bg-white/80 dark:bg-slate-900/70 shadow-sm hover:shadow transition\" data-action=\"menu\" aria-label=\"More options\" aria-haspopup=\"menu\" aria-expanded=\"false\">
                                <svg class=\"w-5 h-5 text-slate-500 dark:text-slate-300\" viewBox=\"0 0 24 24\" fill=\"currentColor\"><circle cx=\"5\" cy=\"12\" r=\"1.5\"/><circle cx=\"12\" cy=\"12\" r=\"1.5\"/><circle cx=\"19\" cy=\"12\" r=\"1.5\"/></svg>
                              </button>
                              <div class=\"absolute right-0 mt-2 w-44 bg-white/95 dark:bg-slate-800/95 backdrop-blur border border-slate-200 dark:border-slate-700 rounded-xl shadow-2xl hidden z-50\" data-kebab-menu role=\"menu\">
                                <button class=\"w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors\" role=\"menuitem\" data-action=\"copy-link\">Copy link</button>
                                <button class=\"w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors\" role=\"menuitem\" data-action=\"reprocess\">Reprocess…</button>
                                <button class=\"w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors\" role=\"menuitem\" data-action=\"delete\">Delete…</button>
                              </div>
                            </div>
                            <div class=\"absolute top-16 right-3 hidden z-50\" data-delete-popover>
                              <div class=\"bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-3 text-sm\">
                                <div class=\"mb-2 text-slate-700 dark:text-slate-200\">Delete this summary?</div>
                                <div class=\"flex items-center gap-2.5 justify-end\">
                                  <button class=\"px-2 py-1 rounded border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700\" data-action=\"cancel-delete\">Cancel</button>
                                  <button class=\"px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700\" data-action=\"confirm-delete\">Delete</button>
                                </div>
                              </div>
                            </div>
                        </div>

                        <div class=\"mt-5 flex flex-wrap items-center gap-2.5 text-sm font-medium\">\n                          <button class=\"inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-audio-600 text-white shadow-md shadow-audio-500/30 hover:bg-audio-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-audio-300/80 transition-colors\" data-action=\"read\">\n                            <span class=\"inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/15 text-white\"><svg class=\"w-3.5 h-3.5\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M4 5a2 2 0 012-2h4a2 2 0 012 2v14a1 1 0 01-1.447.894L9 18.118l-2.553 1.776A1 1 0 015 19V5z\"/><path d=\"M12 3h4a2 2 0 012 2v14a1 1 0 01-1.447.894L17 18.118l-2.553 1.776A1 1 0 0113 19V5a2 2 0 00-1-1.732\"/></svg></span>\n                            <span class=\"flex items-center gap-1.5\">\n                              <span class=\"font-semibold\">Read</span>\n                              ${buttonDurations.read ? `<span class=\"text-[11px] font-medium opacity-80\">${buttonDurations.read}</span>` : ''}\n                            </span>\n                          </button>\n                          ${hasAudio ? `<button class=\"inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-gradient-to-r from-audio-500 to-indigo-500 text-white shadow-md shadow-indigo-500/30 hover:from-audio-400 hover:to-indigo-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300/80 transition-colors\" data-action=\"listen\" data-default-label=\"Listen\" data-playing-label=\"Pause\" data-listen-button>\n                            <span class=\"inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/15 text-white\"><svg data-icon-play class=\"w-3.5 h-3.5\" viewBox=\"0 0 24 24\" fill=\"currentColor\"><path d=\"M8 5v14l11-7z\"/></svg><svg data-icon-pause class=\"w-3.5 h-3.5 hidden\" viewBox=\"0 0 24 24\" fill=\"currentColor\"><path d=\"M6 5h3v14H6zm9 0h3v14h-3z\"/></svg></span>\n                            <span class=\"flex items-center gap-1.5\" data-label-wrapper>\n                              <span class=\"font-semibold\" data-label>Listen</span>\n                              ${buttonDurations.listen ? `<span class=\"text-[11px] font-medium opacity-90\" data-duration>${buttonDurations.listen}</span>` : ''}\n                            </span>\n                          </button>` : ''}\n                          <button class=\"inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-violet-600 text-white shadow-md shadow-violet-500/30 hover:bg-violet-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-300/80 transition-colors\" data-action=\"watch\">\n                            <span class=\"inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/15 text-white\"><svg class=\"w-3.5 h-3.5\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M10 9l5 3-5 3V9z\"/></svg></span>\n                            <span class=\"flex items-center gap-1.5\">\n                              <span class=\"font-semibold\">Watch</span>\n                              ${buttonDurations.watch ? `<span class=\"text-[11px] font-medium opacity-80\">${buttonDurations.watch}</span>` : ''}\n                            </span>\n                          </button>\n                        </div>\n                        <section role=\"region\" aria-live=\"polite\" hidden data-expand-region></section>
                    </div>
                </div>
            </div>
        `;
    }

    createGridCard(item) {
        // Normalize field names between SQLite and PostgreSQL APIs
        const title = item.title || 'Untitled';
        const channel = item.channel ?? item.channel_name ?? 'Unknown Channel';
        const analysis = item.analysis ?? item.analysis_json ?? {};
        const fileStem = item.file_stem ?? item.video_id ?? '';

        // Create normalized item for consistent access
        const normalizedItem = { ...item, title, channel, analysis, file_stem: fileStem, summary_type: item.summary_variant || item.summary_type || 'unknown' };

        const duration = this.formatDuration(normalizedItem.duration_seconds || 0);
        const href = `/${normalizedItem.file_stem}.json?v=2`;
        const isPlaying = this.currentAudio && this.currentAudio.id === normalizedItem.file_stem && this.isPlaying;
        const channelInitial = (normalizedItem.channel || '?').trim().charAt(0).toUpperCase();
        const buttonDurations = this.getButtonDurations(normalizedItem);
        const { categories, subcats, subcatPairs } = this.extractCatsAndSubcats(normalizedItem);
        const totalSecs = (normalizedItem.media_metadata && normalizedItem.media_metadata.mp3_duration_seconds) ? normalizedItem.media_metadata.mp3_duration_seconds : (normalizedItem.duration_seconds || 0);
        const totalDur = (normalizedItem.media_metadata && normalizedItem.media_metadata.mp3_duration_seconds)
            ? this.formatDuration(normalizedItem.media_metadata.mp3_duration_seconds)
            : (normalizedItem.duration_seconds ? this.formatDuration(normalizedItem.duration_seconds) : '');
        const hasAudio = Boolean(normalizedItem.media && normalizedItem.media.has_audio);
        return `
        <div data-card data-report-id=\"${normalizedItem.file_stem}\" data-video-id=\"${normalizedItem.video_id || ''}\" data-has-audio=\"${hasAudio ? 'true' : 'false'}\" data-href=\"${href}\" title=\"Open summary\" tabindex=\"0\" class=\"group relative cursor-pointer overflow-hidden rounded-2xl border border-white/60 dark:border-slate-800/70 bg-white/85 dark:bg-slate-900/65 backdrop-blur-lg shadow-lg transition-all duration-200 hover:-translate-y-1 hover:shadow-2xl ${isPlaying ? 'is-playing' : ''}\">
            <div class=\"card-glow absolute inset-0 bg-gradient-to-br from-audio-500/15 via-transparent to-indigo-500/20\"></div>
            <div class=\"relative aspect-video bg-slate-100/90 dark:bg-slate-800/80 overflow-hidden\">
                ${normalizedItem.thumbnail_url ? `<img src=\"${normalizedItem.thumbnail_url}\" alt=\"thumbnail\" loading=\"lazy\" class=\"absolute inset-0 w-full h-full object-cover\">` : ''}
                <div class=\"absolute inset-0 flex items-center justify-center pointer-events-none ${isPlaying ? '' : 'hidden'}\" data-card-eq>
                    <div class=\"px-2 py-1 rounded-md bg-black/45 backdrop-blur\">
                        <div class=\"flex items-end gap-1.5 text-white\">
                            <span class=\"w-0.5 sm:w-1 h-3 sm:h-4 waveform-bar\" style=\"--delay:0\"></span>
                            <span class=\"w-0.5 sm:w-1 h-4 sm:h-6 waveform-bar\" style=\"--delay:1\"></span>
                            <span class=\"w-0.5 sm:w-1 h-6 sm:h-8 waveform-bar\" style=\"--delay:2\"></span>
                            <span class=\"w-0.5 sm:w-1 h-4 sm:h-6 waveform-bar\" style=\"--delay:3\"></span>
                            <span class=\"w-0.5 sm:w-1 h-3 sm:h-4 waveform-bar\" style=\"--delay:4\"></span>
                        </div>
                    </div>
                </div>
                <div class=\"absolute inset-x-3 bottom-3 h-1.5 bg-black/25 rounded-full overflow-hidden cursor-pointer\" data-card-progress-container data-total-seconds=\"${totalSecs}\">
                    <div class=\"h-full bg-gradient-to-r from-audio-500 to-indigo-500\" style=\"width:0%\" data-card-progress role=\"progressbar\" aria-valuemin=\"0\" aria-valuemax=\"100\" aria-valuenow=\"0\"></div>
                </div>
                <div class=\"absolute top-3 right-3 z-20\">
                  <button class=\"p-2 rounded-full border border-white/50 dark:border-slate-700/70 bg-white/85 dark:bg-slate-900/70 shadow-sm hover:shadow transition\" data-action=\"menu\" aria-label=\"More options\" aria-haspopup=\"menu\" aria-expanded=\"false\">
                    <svg class=\"w-5 h-5 text-slate-500 dark:text-slate-300\" viewBox=\"0 0 24 24\" fill=\"currentColor\"><circle cx=\"5\" cy=\"12\" r=\"1.5\"/><circle cx=\"12\" cy=\"12\" r=\"1.5\"/><circle cx=\"19\" cy=\"12\" r=\"1.5\"/></svg>
                  </button>
                  <div class=\"absolute right-0 mt-2 w-40 bg-white/95 dark:bg-slate-800/95 backdrop-blur border border-slate-200 dark:border-slate-700 rounded-xl shadow-2xl hidden z-50\" data-kebab-menu role=\"menu\">
                    <button class=\"w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors\" role=\"menuitem\" data-action=\"copy-link\">Copy link</button>
                    <button class=\"w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors\" role=\"menuitem\" data-action=\"delete\">Delete…</button>
                  </div>
                </div>
                <div class=\"absolute top-16 right-3 hidden z-50\" data-delete-popover>
                  <div class=\"bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-2 text-xs\">
                    <div class=\"mb-2 text-slate-700 dark:text-slate-200\">Delete this summary?</div>
                    <div class=\"flex items-center gap-2.5 justify-end\">
                      <button class=\"px-2 py-1 rounded border border-slate-200 dark:border-slate-700\" data-action=\"cancel-delete\">Cancel</button>
                      <button class=\"px-2 py-1 rounded bg-red-600 text-white\" data-action=\"confirm-delete\">Delete</button>
                    </div>
                  </div>
                </div>
            </div>
            <div class=\"relative p-4 space-y-3\">
                <h3 class=\"text-sm font-semibold text-slate-800 dark:text-slate-100 group-hover:text-audio-700 transition-colors line-clamp-2\">${this.escapeHtml(normalizedItem.title)}</h3>
                <div class=\"flex flex-wrap items-center gap-2.5.5 text-xs leading-tight text-slate-600 dark:text-slate-300\">
                    <span class=\"inline-flex items-center justify-center w-5 h-5 rounded-full bg-white/80 dark:bg-slate-800/80 border border-white/60 dark:border-slate-700/70 text-[10px] font-semibold text-slate-600 dark:text-slate-200 shadow-sm\">${channelInitial}</span>
                    <button class=\"truncate max-w-[9rem] hover:text-audio-600 dark:hover:text-audio-400 transition-colors text-left\" data-filter-chip=\"channel\" data-filter-value=\"${this.escapeHtml(normalizedItem.channel || '')}\" title=\"Filter by ${this.escapeHtml(normalizedItem.channel || '')}\">${this.escapeHtml(normalizedItem.channel || '')}</button>
                    ${this.renderLanguageChip(normalizedItem.analysis?.language)}
                    ${this.renderSummaryTypeChip(normalizedItem.summary_type)}
                    ${isPlaying ? '<span class=\"inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-audio-100 text-audio-700 text-[10px] font-semibold shadow-sm\"><span class=\"inline-flex h-1.5 w-1.5 rounded-full bg-audio-500\"></span>Now playing</span>' : ''}
                </div>
                ${categories.length ? `<div class=\"flex flex-wrap gap-1.5\">${categories.map(cat => this.renderChip(cat, 'category', true)).join('')}</div>` : ''}
                ${Array.isArray(subcatPairs) && subcatPairs.length ? `<div class=\"flex flex-wrap gap-1.5\">${subcatPairs.map(([p, sc]) => this.renderChip(sc, 'subcategory', true, p)).join('')}</div>` : ''}
                <div class=\"flex flex-wrap items-center gap-2.5 pt-1 text-sm font-medium\">\n                    <button class=\"inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-audio-600 text-white shadow-md shadow-audio-500/30 hover:bg-audio-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-audio-300/80 transition-colors\" data-action=\"read\">\n                        <span class=\"inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/15 text-white\"><svg class=\"w-3.5 h-3.5\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M4 5a2 2 0 012-2h4a2 2 0 012 2v14a1 1 0 01-1.447.894L9 18.118l-2.553 1.776A1 1 0 015 19V5z\"/><path d=\"M12 3h4a2 2 0 012 2v14a1 1 0 01-1.447.894L17 18.118l-2.553 1.776A1 1 0 0113 19V5a2 2 0 00-1-1.732\"/></svg></span>\n                        <span class=\"flex items-center gap-1.5\">\n                            <span class=\"font-semibold\">Read</span>\n                            ${buttonDurations.read ? `<span class=\"text-[11px] font-medium opacity-80\">${buttonDurations.read}</span>` : ''}\n                        </span>\n                    </button>\n                    ${hasAudio ? `<button class=\"inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-gradient-to-r from-audio-500 to-indigo-500 text-white shadow-md shadow-indigo-500/30 hover:from-audio-400 hover:to-indigo-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300/80 transition-colors\" data-action=\"listen\" data-default-label=\"Listen\" data-playing-label=\"Pause\" data-listen-button>\n                        <span class=\"inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/15 text-white\"><svg data-icon-play class=\"w-3.5 h-3.5\" viewBox=\"0 0 24 24\" fill=\"currentColor\"><path d=\"M8 5v14l11-7z\"/></svg><svg data-icon-pause class=\"w-3.5 h-3.5 hidden\" viewBox=\"0 0 24 24\" fill=\"currentColor\"><path d=\"M6 5h3v14H6zm9 0h3v14h-3z\"/></svg></span>\n                        <span class=\"flex items-center gap-1.5\" data-label-wrapper>\n                            <span class=\"font-semibold\" data-label>Listen</span>\n                            ${buttonDurations.listen ? `<span class=\"text-[11px] font-medium opacity-90\" data-duration>${buttonDurations.listen}</span>` : ''}\n                        </span>\n                    </button>` : `<button class=\"inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full border border-white/15 bg-white/6 text-white/50 cursor-not-allowed\" disabled>\n                        <span class=\"inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/10 text-white/60\"><svg class=\"w-3.5 h-3.5\" viewBox=\"0 0 24 24\" fill=\"currentColor\"><path d=\"M8 5v14l11-7z\"/></svg></span>\n                        <span class=\"font-semibold\">Listen</span>\n                    </button>`}\n                    <button class=\"inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-violet-600 text-white shadow-md shadow-violet-500/30 hover:bg-violet-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-300/80 transition-colors\" data-action=\"watch\">\n                        <span class=\"inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/15 text-white\"><svg class=\"w-3.5 h-3.5\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M10 9l5 3-5 3V9z\"/></svg></span>\n                        <span class=\"flex items-center gap-1.5\">\n                            <span class=\"font-semibold\">Watch</span>\n                            ${buttonDurations.watch ? `<span class=\"text-[11px] font-medium opacity-80\">${buttonDurations.watch}</span>` : ''}\n                        </span>\n                    </button>\n                </div>\n                <section role=\"region\" aria-live=\"polite\" hidden data-expand-region></section>
                    </div>
                </div>
            </div>
        `;
    }

    createGridCard(item) {
        // Normalize field names between SQLite and PostgreSQL APIs
        const title = item.title || 'Untitled';
        const channel = item.channel ?? item.channel_name ?? 'Unknown Channel';
        const analysis = item.analysis ?? item.analysis_json ?? {};
        const fileStem = item.file_stem ?? item.video_id ?? '';

        // Create normalized item for consistent access
        const normalizedItem = { ...item, title, channel, analysis, file_stem: fileStem, summary_type: item.summary_variant || item.summary_type || 'unknown' };

        const duration = this.formatDuration(normalizedItem.duration_seconds || 0);
        const href = `/${normalizedItem.file_stem}.json?v=2`;
        const isPlaying = this.currentAudio && this.currentAudio.id === normalizedItem.file_stem && this.isPlaying;
        const channelInitial = (normalizedItem.channel || '?').trim().charAt(0).toUpperCase();
        const buttonDurations = this.getButtonDurations(normalizedItem);
        const { categories, subcats, subcatPairs } = this.extractCatsAndSubcats(normalizedItem);
        const totalSecs = (normalizedItem.media_metadata && normalizedItem.media_metadata.mp3_duration_seconds) ? normalizedItem.media_metadata.mp3_duration_seconds : (normalizedItem.duration_seconds || 0);
        const totalDur = (normalizedItem.media_metadata && normalizedItem.media_metadata.mp3_duration_seconds)
            ? this.formatDuration(normalizedItem.media_metadata.mp3_duration_seconds)
            : (normalizedItem.duration_seconds ? this.formatDuration(normalizedItem.duration_seconds) : '');
        const hasAudio = Boolean(normalizedItem.media && normalizedItem.media.has_audio);
        return `
        <div data-card data-report-id=\"${normalizedItem.file_stem}\" data-video-id=\"${normalizedItem.video_id || ''}\" data-has-audio=\"${hasAudio ? 'true' : 'false'}\" data-href=\"${href}\" title=\"Open summary\" tabindex=\"0\" class=\"group relative cursor-pointer overflow-hidden rounded-2xl border border-white/60 dark:border-slate-800/70 bg-white/85 dark:bg-slate-900/65 backdrop-blur-lg shadow-lg transition-all duration-200 hover:-translate-y-1 hover:shadow-2xl ${isPlaying ? 'is-playing' : ''}\">
            <div class=\"card-glow absolute inset-0 bg-gradient-to-br from-audio-500/15 via-transparent to-indigo-500/20\"></div>
            <div class=\"relative aspect-video bg-slate-100/90 dark:bg-slate-800/80 overflow-hidden\">
                ${normalizedItem.thumbnail_url ? `<img src=\"${normalizedItem.thumbnail_url}\" alt=\"thumbnail\" loading=\"lazy\" class=\"absolute inset-0 w-full h-full object-cover\">` : ''}
                <div class=\"absolute inset-0 flex items-center justify-center pointer-events-none ${isPlaying ? '' : 'hidden'}\" data-card-eq>
                    <div class=\"px-2 py-1 rounded-md bg-black/45 backdrop-blur\">
                        <div class=\"flex items-end gap-1.5 text-white\">
                            <span class=\"w-0.5 sm:w-1 h-3 sm:h-4 waveform-bar\" style=\"--delay:0\"></span>
                            <span class=\"w-0.5 sm:w-1 h-4 sm:h-6 waveform-bar\" style=\"--delay:1\"></span>
                            <span class=\"w-0.5 sm:w-1 h-6 sm:h-8 waveform-bar\" style=\"--delay:2\"></span>
                            <span class=\"w-0.5 sm:w-1 h-4 sm:h-6 waveform-bar\" style=\"--delay:3\"></span>
                            <span class=\"w-0.5 sm:w-1 h-3 sm:h-4 waveform-bar\" style=\"--delay:4\"></span>
                        </div>
                    </div>
                </div>
                <div class=\"absolute inset-x-3 bottom-3 h-1.5 bg-black/25 rounded-full overflow-hidden cursor-pointer\" data-card-progress-container data-total-seconds=\"${totalSecs}\">
                    <div class=\"h-full bg-gradient-to-r from-audio-500 to-indigo-500\" style=\"width:0%\" data-card-progress role=\"progressbar\" aria-valuemin=\"0\" aria-valuemax=\"100\" aria-valuenow=\"0\"></div>
                </div>
                <div class=\"absolute top-3 right-3 z-20\">
                  <button class=\"p-2 rounded-full border border-white/50 dark:border-slate-700/70 bg-white/85 dark:bg-slate-900/70 shadow-sm hover:shadow transition\" data-action=\"menu\" aria-label=\"More options\" aria-haspopup=\"menu\" aria-expanded=\"false\">
                    <svg class=\"w-5 h-5 text-slate-500 dark:text-slate-300\" viewBox=\"0 0 24 24\" fill=\"currentColor\"><circle cx=\"5\" cy=\"12\" r=\"1.5\"/><circle cx=\"12\" cy=\"12\" r=\"1.5\"/><circle cx=\"19\" cy=\"12\" r=\"1.5\"/></svg>
                  </button>
                  <div class=\"absolute right-0 mt-2 w-40 bg-white/95 dark:bg-slate-800/95 backdrop-blur border border-slate-200 dark:border-slate-700 rounded-xl shadow-2xl hidden z-50\" data-kebab-menu role=\"menu\">
                    <button class=\"w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors\" role=\"menuitem\" data-action=\"copy-link\">Copy link</button>
                    <button class=\"w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors\" role=\"menuitem\" data-action=\"delete\">Delete…</button>
                  </div>
                </div>
                <div class=\"absolute top-16 right-3 hidden z-50\" data-delete-popover>
                  <div class=\"bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-2 text-xs\">
                    <div class=\"mb-2 text-slate-700 dark:text-slate-200\">Delete this summary?</div>
                    <div class=\"flex items-center gap-2.5 justify-end\">
                      <button class=\"px-2 py-1 rounded border border-slate-200 dark:border-slate-700\" data-action=\"cancel-delete\">Cancel</button>
                      <button class=\"px-2 py-1 rounded bg-red-600 text-white\" data-action=\"confirm-delete\">Delete</button>
                    </div>
                  </div>
                </div>
            </div>
            <div class=\"relative p-4 space-y-3\">
                <h3 class=\"text-sm font-semibold text-slate-800 dark:text-slate-100 group-hover:text-audio-700 transition-colors line-clamp-2\">${this.escapeHtml(normalizedItem.title)}</h3>
                <div class=\"flex flex-wrap items-center gap-2.5 text-xs text-slate-600 dark:text-slate-300\">
                    <span class=\"inline-flex items-center justify-center w-5 h-5 rounded-full bg-white/80 dark:bg-slate-800/80 border border-white/60 dark:border-slate-700/70 text-[10px] font-semibold text-slate-600 dark:text-slate-200 shadow-sm\">${channelInitial}</span>
                    <button class=\"truncate max-w-[9rem] hover:text-audio-600 dark:hover:text-audio-400 transition-colors text-left\" data-filter-chip=\"channel\" data-filter-value=\"${this.escapeHtml(normalizedItem.channel || '')}\" title=\"Filter by ${this.escapeHtml(normalizedItem.channel || '')}\">${this.escapeHtml(normalizedItem.channel || '')}</button>
                    ${this.renderLanguageChip(normalizedItem.analysis?.language)}
                    ${this.renderSummaryTypeChip(normalizedItem.summary_type)}
                    ${isPlaying ? '<span class=\"inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-audio-100 text-audio-700 text-[10px] font-semibold shadow-sm\"><span class=\"inline-flex h-1.5 w-1.5 rounded-full bg-audio-500\"></span>Now playing</span>' : ''}
                </div>
                ${categories.length ? `<div class=\"flex flex-wrap gap-1.5\">${categories.map(cat => this.renderChip(cat, 'category', true)).join('')}</div>` : ''}
                ${Array.isArray(subcatPairs) && subcatPairs.length ? `<div class=\"flex flex-wrap gap-1.5\">${subcatPairs.map(([p, sc]) => this.renderChip(sc, 'subcategory', true, p)).join('')}</div>` : ''}
                <div class=\"flex flex-wrap items-center gap-2.5 pt-1 text-xs font-medium\">
                    <button class=\"inline-flex items-center gap-1.5.5 px-3 py-1.5 rounded-full bg-audio-600 text-white shadow-md hover:bg-audio-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-audio-400\" data-action=\"read\">
                        <span>Read</span>
                        ${buttonDurations.read ? `<span class=\"text-[11px] font-medium opacity-80\">${buttonDurations.read}</span>` : ''}
                    </button>
                    ${hasAudio ? `<button class=\"inline-flex items-center gap-1.5.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-audio-500 to-indigo-500 text-white shadow-md hover:from-audio-400 hover:to-indigo-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-300/80\" data-action=\"listen\">
                        <span>Listen</span>
                        ${buttonDurations.listen ? `<span class=\"text-[11px] font-medium opacity-90\">${buttonDurations.listen}</span>` : ''}
                    </button>` : `<button class=\"inline-flex items-center gap-1.5.5 px-3 py-1.5 rounded-full border border-white/40 dark:border-slate-800/70 bg-white/60 dark:bg-slate-900/50 text-slate-400 dark:text-slate-500 cursor-not-allowed\" disabled>
                        <span>Listen</span>
                        <span class=\"text-[11px] font-medium opacity-70\">N/A</span>
                    </button>`}
                    <button class=\"inline-flex items-center gap-1.5.5 px-3 py-1.5 rounded-full border border-white/60 dark:border-slate-700/70 bg-white/80 dark:bg-slate-900/60 text-slate-700 dark:text-slate-200 hover:bg-white/95 dark:hover:bg-slate-800 transition-colors\" data-action=\"watch\">
                        <span>Watch</span>
                        ${buttonDurations.watch ? `<span class=\"text-[11px] font-medium opacity-80\">${buttonDurations.watch}</span>` : ''}
                    </button>
                </div>
                <section role=\"region\" aria-live=\"polite\" hidden data-expand-region></section>
            </div>
        </div>`;
    }

    fmtFilterKey(key) {
        const map = {
            category: 'Category',
            categories: 'Category',
            channel: 'Channel',
            channels: 'Channel',
            content_type: 'Content',
            content_type_filters: 'Content',
            summary_type: 'Summary',
            language: 'Language'
        };
        return map[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    updateHeroBadges() {
        const heroBadges = this.heroBadges || document.getElementById('heroBadges');
        if (!heroBadges) return;
        this.heroBadges = heroBadges;
        const sections = [];

        // Always show search queries
        if (this.searchQuery) {
            sections.push({
                type: 'search',
                label: 'Search',
                value: this.searchQuery
            });
        }

        // Follow the same logic as filtering: only show chips when user is actively excluding categories
        const categoryFilters = this.currentFilters?.category || [];
        const allCategories = Array.from(document.querySelectorAll('input[data-filter="category"]')).map(el => el.value);

        // Show category chips ONLY when some categories are unchecked (actively filtering)
        // When all categories are selected = no filter applied = no chips shown
        if (categoryFilters.length > 0 && categoryFilters.length < allCategories.length) {
            categoryFilters.forEach(val =>
                sections.push({
                    type: 'category',
                    label: 'Category',
                    value: val
                })
            );
        }

        // Create horizontal scrolling container for chips
        if (sections.length > 0) {
            heroBadges.innerHTML = `
                <div class="flex overflow-x-auto pb-2 space-x-2 scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-600 scrollbar-track-transparent"
                     style="max-height: 80px; scrollbar-width: thin;">
                    ${sections.map(({ type, label, value }) => `
                        <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/40 dark:border-white/10 bg-white/70 dark:bg-white/5 text-slate-600 dark:text-slate-200 whitespace-nowrap flex-shrink-0">
                            <span class="uppercase tracking-wide text-[10px] text-slate-400 dark:text-slate-500">${this.escapeHtml(String(label))}</span>
                            <span class="text-[11px] font-medium">${this.escapeHtml(String(value))}</span>
                            <button class="ml-1 hover:bg-slate-200 dark:hover:bg-slate-600 rounded-full p-0.5 transition-colors"
                                    data-remove-filter="${type}"
                                    data-filter-value="${this.escapeHtml(String(value))}"
                                    title="Remove filter">
                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                                </svg>
                            </button>
                        </span>
                    `).join('')}
                </div>
            `;
        } else {
            heroBadges.innerHTML = '';
        }

        // Add click handlers for remove buttons
        heroBadges.querySelectorAll('[data-remove-filter]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const filterType = btn.dataset.removeFilter;
                const filterValue = btn.dataset.filterValue;
                this.removeFilterChip(filterType, filterValue);
            });
        });

        heroBadges.classList.toggle('hidden', sections.length === 0);
    }

    removeFilterChip(filterType, filterValue) {
        if (filterType === 'search') {
            // Clear search
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.value = '';
                this.searchQuery = '';
            }
        } else if (filterType === 'category') {
            // Uncheck specific category
            const categoryInput = document.querySelector(`input[data-filter="category"][value="${filterValue}"]`);
            if (categoryInput) categoryInput.checked = false;
        } else if (filterType === 'subcategory') {
            // Uncheck specific subcategory
            const subcategoryInput = document.querySelector(`input[data-filter="subcategory"][value="${filterValue}"]`);
            if (subcategoryInput) subcategoryInput.checked = false;
        }

        // Update filters and reload
        this.currentFilters = this.computeFiltersFromDOM();
        this.updateHeroBadges();
        this.loadContent();
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
        // Always keep SUMMARIZERNATOR as the main title
        this.resultsTitle.textContent = 'SUMMARIZERNATOR';

        // Update subtitle based on current state
        if (this.searchQuery) {
            if (this.resultsSubtitle) this.resultsSubtitle.textContent = `Search results for "${this.searchQuery}"`;
        } else if (this.currentFilters && Object.keys(this.currentFilters).length) {
            if (this.resultsSubtitle) this.resultsSubtitle.textContent = 'Refined by your current filters';
        } else {
            if (this.resultsSubtitle) this.resultsSubtitle.textContent = 'Your daily audio briefing';
        }

        // Create navigation arrows with the pagination text
        const canGoBack = pagination.page > 1;
        const canGoForward = pagination.page < pagination.pages;

        const leftArrow = canGoBack
            ? `<button class="inline-flex items-center text-slate-600 hover:text-slate-800 dark:text-slate-300 dark:hover:text-slate-100 transition-colors mr-2" data-nav="prev" title="Previous page">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
                </svg>
               </button>`
            : `<span class="inline-block w-4 mr-2"></span>`;

        const rightArrow = canGoForward
            ? `<button class="inline-flex items-center text-slate-600 hover:text-slate-800 dark:text-slate-300 dark:hover:text-slate-100 transition-colors ml-2" data-nav="next" title="Next page">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                </svg>
               </button>`
            : `<span class="inline-block w-4 ml-2"></span>`;

        this.resultsCount.innerHTML =
            `${leftArrow}${pagination.total} summaries found • Page ${pagination.page} of ${pagination.pages}${rightArrow}`;

        this.updateHeroBadges();

        // Add click handlers for navigation arrows
        this.resultsCount.querySelectorAll('[data-nav]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const direction = e.currentTarget.dataset.nav;
                if (direction === 'prev' && pagination.page > 1) {
                    this.currentPage = pagination.page - 1;
                    this.loadContent();
                } else if (direction === 'next' && pagination.page < pagination.pages) {
                    this.currentPage = pagination.page + 1;
                    this.loadContent();
                }
            });
        });
    }

    async playAudio(reportId) {
        try {
            // Clean up any leftover state from previous sessions
            this._cleanupScrubState();
            
            // Find the report data
            const reportCard = document.querySelector(`[data-report-id="${reportId}"]`);
            if (!reportCard) return;

            if (reportCard.dataset.hasAudio !== 'true') {
                this.showToast('Audio not available for this summary', 'warn');
                return;
            }

            const item = (this.currentItems || []).find(x => x.file_stem === reportId);
            const audioSrc = this.getAudioSourceForItem(item);
            if (!audioSrc) {
                this.showToast('Audio not available for this summary', 'warn');
                return;
            }

            // Extract report info from the card
            const title = item?.title || reportCard.querySelector('h3').textContent.trim();
            
            // Reset per-card progress bars
            try { document.querySelectorAll('[data-card-progress]').forEach(el => { el.style.width = '0%'; el.setAttribute('aria-valuenow', '0'); }); } catch(_) {}

            // Update current track info and mini player
            if (item) {
                this.setCurrentFromItem(item);
            } else {
                // Fallback: ensure audio metadata is set even if item missing
                this.currentAudio = { id: reportId, title, src: audioSrc };
                this.resetAudioElement();
                if (this.audioElement) {
                    this.audioElement.src = audioSrc;
                    this.audioElement.load();
                }
                if (this.nowPlayingTitle) this.nowPlayingTitle.textContent = title;
                if (this.nowPlayingMeta) this.nowPlayingMeta.textContent = 'Ready';
                this.updateNowPlayingPreview();
                this.updatePlayButton();
            }

            // Queue management (Phase 3)
            if (this.flags.queueEnabled && Array.isArray(this.currentItems)) {
                this.rebuildPlaylist();
                this.currentTrackIndex = this.playlist.indexOf(reportId);
                if (this.currentTrackIndex < 0) this.currentTrackIndex = 0;
                this.renderQueue();
                this.saveQueue();
            } else {
                this.rebuildPlaylist();
                this.currentTrackIndex = this.playlist.indexOf(reportId);
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
        // Apply any pending seek set by a card-scrub on a non-active card
        if (typeof this._pendingSeek === 'number') {
            const duration = this.audioElement.duration;
            const pct = Math.max(0, Math.min(1, this._pendingSeek));
            if (duration && !isNaN(duration)) this.audioElement.currentTime = pct * duration;
            this._pendingSeek = null;
        }
    }

    updatePlayButton() {
        const hasTrack = !!this.currentAudio;
        if (this.playPauseBtn) {
            this.playPauseBtn.disabled = !hasTrack;
            this.playPauseBtn.classList.toggle('opacity-60', !hasTrack);
            this.playPauseBtn.classList.toggle('cursor-not-allowed', !hasTrack);
        }
        if (this.prevBtn) {
            const enablePrev = hasTrack && Array.isArray(this.playlist) && this.playlist.length > 1;
            this.prevBtn.disabled = !enablePrev;
            this.prevBtn.classList.toggle('opacity-60', !enablePrev);
            this.prevBtn.classList.toggle('cursor-not-allowed', !enablePrev);
        }
        if (this.nextBtn) {
            const enableNext = hasTrack && Array.isArray(this.playlist) && this.playlist.length > 1;
            this.nextBtn.disabled = !enableNext;
            this.nextBtn.classList.toggle('opacity-60', !enableNext);
            this.nextBtn.classList.toggle('cursor-not-allowed', !enableNext);
        }

        if (this.isPlaying) {
            this.playIcon.classList.add('hidden');
            this.pauseIcon.classList.remove('hidden');
        } else {
            this.playIcon.classList.remove('hidden');
            this.pauseIcon.classList.add('hidden');
        }
        
        // Update mobile play button
        if (this.mobilePlayIcon && this.mobilePauseIcon) {
            if (this.isPlaying) {
                this.mobilePlayIcon.classList.add('hidden');
                this.mobilePauseIcon.classList.remove('hidden');
            } else {
                this.mobilePlayIcon.classList.remove('hidden');
                this.mobilePauseIcon.classList.add('hidden');
            }
        }
        
        // Show/hide mobile mini-player
        if (this.mobileMiniPlayer) {
            if (this.currentAudio) {
                this.mobileMiniPlayer.classList.remove('hidden', 'translate-y-full');
                this.mobileMiniPlayer.classList.add('translate-y-0');
            } else {
                this.mobileMiniPlayer.classList.add('translate-y-full');
                setTimeout(() => {
                    this.mobileMiniPlayer.classList.add('hidden');
                }, 300);
            }
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
        if (!this.listViewBtn || !this.gridViewBtn) return;

        const activeClasses = ['bg-audio-600', 'text-white', 'shadow-lg'];
        const inactiveClasses = ['bg-white/80', 'dark:bg-slate-900/70', 'text-slate-600', 'dark:text-slate-200', 'border', 'border-white/60', 'dark:border-slate-700/70', 'shadow-sm'];

        [this.listViewBtn, this.gridViewBtn].forEach(btn => {
            btn.classList.remove(...activeClasses, ...inactiveClasses);
            btn.classList.add(...inactiveClasses);
        });

        const activeBtn = this.viewMode === 'grid' ? this.gridViewBtn : this.listViewBtn;
        activeBtn.classList.remove(...inactiveClasses);
        activeBtn.classList.add(...activeClasses);

        this.updateHeroBadges();
    }

    setCurrentFromItem(item) {
        if (!item) {
            this.showNowPlayingPlaceholder();
            return;
        }

        const audioSrc = this.getAudioSourceForItem(item);
        if (!audioSrc) {
            this.showNowPlayingPlaceholder(item);
            return;
        }

        this.currentAudio = {
            id: item.file_stem,
            title: item.title,
            src: audioSrc
        };
        this.isPlaying = false;

        this.resetAudioElement();
        if (this.audioElement) {
            this.audioElement.src = audioSrc;
            this.audioElement.load();
        }

        if (this.nowPlayingTitle) {
            this.nowPlayingTitle.textContent = item.title || 'Audio summary';
        }
        if (this.nowPlayingMeta) {
            this.nowPlayingMeta.textContent = 'Ready';
        }

        if (this.nowPlayingThumb) {
            if (item.thumbnail_url) {
                this.nowPlayingThumb.src = item.thumbnail_url;
                this.nowPlayingThumb.classList.remove('hidden');
            } else {
                this.nowPlayingThumb.classList.add('hidden');
            }
        }

        this.updateNowPlayingPreview();
        this.updatePlayingCard();
        this.updatePlayButton();
    }

    updatePlayingCard() {
        // Card highlight
        this.contentGrid.querySelectorAll('[data-card]').forEach(card => {
            card.classList.remove('is-playing');
        });
        let active = null;
        if (this.currentAudio) {
            active = this.contentGrid.querySelector(`[data-report-id="${this.currentAudio.id}"]`);
            if (active) active.classList.add('is-playing');
        }

        // Update Listen buttons to reflect playing state
        const listenButtons = this.contentGrid.querySelectorAll('[data-listen-button]');
        listenButtons.forEach(btn => {
            const defaultLabel = btn.dataset.defaultLabel || 'Listen';
            const playingLabel = btn.dataset.playingLabel || 'Pause';
            const labelEl = btn.querySelector('[data-label]');
            const playIcon = btn.querySelector('[data-icon-play]');
            const pauseIcon = btn.querySelector('[data-icon-pause]');
            const isActive = !!(active && active.contains(btn));
            const isPlayingActive = isActive && this.isPlaying;

            if (labelEl) labelEl.textContent = isPlayingActive ? playingLabel : defaultLabel;
            btn.setAttribute('aria-pressed', String(isPlayingActive));
            if (playIcon && pauseIcon) {
                if (isPlayingActive) {
                    playIcon.classList.add('hidden');
                    pauseIcon.classList.remove('hidden');
                } else {
                    playIcon.classList.remove('hidden');
                    pauseIcon.classList.add('hidden');
                }
            }

            btn.classList.toggle('ring-2', isActive);
            btn.classList.toggle('ring-indigo-300/60', isActive);
        });

        // Toggle thumbnail equalizer overlay on active playing card
        this.contentGrid.querySelectorAll('[data-card] [data-card-eq]').forEach(eq => {
            const isOnActive = !!(active && active.contains(eq));
            if (isOnActive && this.isPlaying) eq.classList.remove('hidden');
            else eq.classList.add('hidden');
        });
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
            
            // Update mobile mini-player
            if (this.mobileProgressBar) {
                this.mobileProgressBar.style.width = `${progress}%`;
            }
            if (this.mobileCurrentTimeEl) {
                this.mobileCurrentTimeEl.textContent = this.formatDuration(currentTime);
            }
            if (this.mobileNowPlayingTitle && this.currentAudio) {
                this.mobileNowPlayingTitle.textContent = this.currentAudio.title;
            }
            // Update mobile mini-player thumbnail
            if (this.mobileNowPlayingThumb && this.currentAudio) {
                const cardImg = document.querySelector(`[data-report-id="${this.currentAudio.id}"] img`);
                if (cardImg && cardImg.src) {
                    this.mobileNowPlayingThumb.src = cardImg.src;
                    this.mobileNowPlayingThumb.classList.remove('hidden');
                    // Hide placeholder
                    const placeholder = this.mobileNowPlayingThumb.nextElementSibling;
                    if (placeholder) placeholder.style.display = 'none';
                } else {
                    this.mobileNowPlayingThumb.classList.add('hidden');
                    // Show placeholder
                    const placeholder = this.mobileNowPlayingThumb.nextElementSibling;
                    if (placeholder) placeholder.style.display = 'flex';
                }
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
                // Update inline mini scrub + time
                const timeEl = card && card.querySelector('[data-card-time]');
                const totalEl = card && card.querySelector('[data-card-total]');
                const scrubBar = card && card.querySelector('[data-card-scrubbar]');
                if (timeEl) timeEl.textContent = this.formatDuration(currentTime);
                if (totalEl && duration) totalEl.textContent = this.formatDuration(duration);
                if (scrubBar) scrubBar.style.width = `${progress}%`;
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

    // UI helpers
    getLangFlag(lang) {
        const code = String(lang || '').toLowerCase();
        const map = {
            en: '🇬🇧', fr: '🇫🇷', es: '🇪🇸', de: '🇩🇪', it: '🇮🇹', pt: '🇵🇹',
            ru: '🇷🇺', ja: '🇯🇵', zh: '🇨🇳', ko: '🇰🇷', hi: '🇮🇳', nl: '🇳🇱',
            sv: '🇸🇪', no: '🇳🇴', da: '🇩🇰', fi: '🇫🇮', pl: '🇵🇱', tr: '🇹🇷'
        };
        return map[code] || '';
    }

    renderLanguageChip(lang) {
        if (!lang) return '';
        const flag = this.getLangFlag(lang);
        const label = flag ? `${flag}` : this.escapeHtml(lang);
        return `<span class="inline-flex items-center text-[11px] px-1 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200">${label}</span>`;
    }

    renderSummaryTypeChip(type) {
        if (!type || type === 'unknown') return '';

        const labels = {
            'audio': 'Audio',
            'audio-missing': 'Audio (missing)',
            'bullet-points': 'Bullet Points',
            'comprehensive': 'Comprehensive',
            'unknown': 'Unknown'
        };

        const label = labels[type] || type;

        // Use muted colors for audio-missing and unknown
        const isMuted = type === 'audio-missing' || type === 'unknown';
        const colorClass = isMuted
            ? 'bg-slate-200 dark:bg-slate-600 text-slate-600 dark:text-slate-400'
            : 'bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-300';

        return `<button class="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded ${colorClass}"
                 data-filter-chip="summary_type"
                 data-filter-value="${this.escapeHtml(type)}"
                 title="Filter by ${this.escapeHtml(label)}">${this.escapeHtml(label)}</button>`;
    }

    renderChip(text, type = 'category', small = false, parent = null) {
        const base = small ? 'text-[10px] px-3 py-1' : 'text-xs px-3 py-1.5 tracking-wide';
        const color = type === 'subcategory'
            ? 'border border-blue-500/35 bg-blue-500/10 text-blue-600 dark:text-blue-300 hover:bg-blue-500/20 dark:hover:bg-blue-500/25'
            : 'bg-gradient-to-r from-audio-500/15 to-indigo-500/20 border border-audio-500/35 text-audio-700 dark:text-audio-100 shadow-inner shadow-audio-500/10 hover:from-audio-500/25 hover:to-indigo-500/25';
        const t = this.escapeHtml(text || '');
        const dataParent = parent ? ` data-parent-category="${this.escapeHtml(parent)}"` : '';
        return `<button class="relative z-10 inline-flex items-center ${base} rounded-full font-medium ${color} hover:opacity-90 transition-all cursor-pointer" data-filter-chip="${type}" data-filter-value="${t}"${dataParent} title="Click to filter by ${t}">${t}</button>`;
    }

    // Normalize categories & subcategories (prefer new subcategories_json structure)
    extractCatsAndSubcats(item) {
        // Check for new structured subcategories_json field first
        let subcategoriesStructure = null;
        if (item?.subcategories_json) {
            try {
                subcategoriesStructure = JSON.parse(item.subcategories_json);
            } catch (e) {
                console.warn('Failed to parse subcategories_json:', e, item.subcategories_json);
            }
        }
        
        // Also check for pre-parsed categories from SQLiteContentIndex
        if (!subcategoriesStructure && item?.analysis?.categories?.length) {
            subcategoriesStructure = { categories: item.analysis.categories };
        }

        // Use new structured data if available
        if (subcategoriesStructure?.categories?.length) {
            const categories = subcategoriesStructure.categories
                .map(c => c?.category)
                .filter(Boolean)
                .slice(0, 3);

            const subcatPairs = subcategoriesStructure.categories.flatMap(c => {
                const parent = c?.category;
                if (!parent || !Array.isArray(c?.subcategories)) return [];
                return c.subcategories.map(sc => [parent, sc]);
            });

            const subcats = Array.from(new Set(subcatPairs.map(([, s]) => s)));

            // Debug logging for new structured data
            console.log('New Structured Data:', {
                title: item.title,
                categories,
                subcatPairs,
                subcats
            });

            return { categories, subcats, subcatPairs };
        }

        // Fall back to legacy logic if no structured data
        const rich = Array.isArray(item?.analysis?.categories) ? item.analysis.categories : [];

        let categories = [];
        
        // Prefer schema_version >= 2 structured data
        if (item?.analysis?.schema_version >= 2 && Array.isArray(item?.analysis?.categories)) {
            categories = item.analysis.categories.map(c => c?.category).filter(Boolean);
        } else {
            // Legacy path with comma-split guard
            const catsRich = rich.map(c => c?.category).filter(Boolean);
            const catsLegacy = Array.isArray(item?.analysis?.category)
                ? item.analysis.category
                : (item?.analysis?.category ? [item.analysis.category] : []);
            
            categories = Array.from(new Set([...catsRich, ...catsLegacy]))
                .flatMap(cat => {
                    // If we get a comma-separated string, split it into separate categories
                    if (typeof cat === 'string' && cat.includes(',')) {
                        return cat.split(',').map(c => c.trim()).filter(Boolean);
                    }
                    return [cat];
                })
                .filter(Boolean);
        }
        
        categories = categories.slice(0, 3);

        // Debug logging for troubleshooting
        if (categories.length > 1) {
            console.log('Multi-category Debug:', {
                title: item.title,
                originalCategory: item?.analysis?.category,
                originalCategories: item?.analysis?.categories,
                processedCategories: categories
            });
        }

        // Build [parent, subcat] pairs from rich
        const pairsRich = rich.flatMap(c => {
            const parent = c?.category;
            if (!parent) return [];
            const arr = Array.isArray(c?.subcategories) ? c.subcategories
                      : (c?.subcategory ? [c.subcategory] : []);
            return (arr || []).map(sc => [parent, sc]);
        });

        // Legacy fallbacks: attach subcategory to ALL categories (not just first)
        const legacySubs = Array.isArray(item?.analysis?.subcategories)
            ? item.analysis.subcategories
            : (item?.analysis?.subcategory ? [item.analysis.subcategory] : []);
        const legacyPairs = [];
        if (categories.length && legacySubs.length) {
            // Smart pairing: only pair subcategories with their correct parent category
            for (const subcategory of legacySubs) {
                if (subcategory && !categories.includes(subcategory)) {
                    // Find the correct parent category for this subcategory
                    const correctParent = SUBCATEGORY_PARENTS[subcategory];
                    
                    if (correctParent && categories.includes(correctParent)) {
                        // Pair with correct parent if it's in the categories list
                        legacyPairs.push([correctParent, subcategory]);
                    } else if (categories.length > 0) {
                        // Fall back to first category if correct parent not found/available
                        legacyPairs.push([categories[0], subcategory]);
                    }
                }
            }
        }

        const seen = new Set();
        const subcatPairs = [...pairsRich, ...legacyPairs].filter(([p, s]) => {
            const k = `${p}|${s}`;
            if (!p || !s || seen.has(k)) return false;
            seen.add(k);
            return true;
        });
        const subcats = Array.from(new Set(subcatPairs.map(([, s]) => s)));
        
        // Debug logging for legacy fallback
        if (categories.length > 1) {
            console.log('Legacy Fallback Debug:', {
                title: item.title,
                categories,
                legacySubs,
                legacyPairs,
                subcatPairs,
                subcats
            });
        }
        
        return { categories, subcats, subcatPairs };
    }

    updateNowPlayingPreview() {
        if (!this.nowPlayingPreview) return;
        this.nowPlayingPreview.classList.remove('hidden');
        if (!this.currentAudio && this.nowPlayingTitle) {
            const text = (this.nowPlayingTitle.textContent || '').trim();
            if (!text) {
                this.nowPlayingTitle.textContent = 'Select an audio summary';
            }
        }
    }

    seekTo(event) {
        const rect = this.progressContainer.getBoundingClientRect();
        const raw = (event.clientX - rect.left) / rect.width;
        const percentage = Math.max(0, Math.min(1, raw));
        const duration = this.audioElement.duration;
        if (duration && !isNaN(duration)) {
            this.audioElement.currentTime = percentage * duration;
        }
    }

    // Seek when clicking on a card's progress bar
    seekOnCardScrub(el, event) {
        const card = el.closest('[data-report-id]');
        if (!card) return;
        const id = card.dataset.reportId;
        const rect = el.getBoundingClientRect();
        const clientX = ('clientX' in event) ? event.clientX : (event.touches && event.touches[0] ? event.touches[0].clientX : 0);
        const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
        
        // If this card is already playing, seek immediately
        if (this.currentAudio && this.currentAudio.id === id && this.audioElement) {
            const duration = this.audioElement.duration;
            if (duration && !isNaN(duration)) {
                this.audioElement.currentTime = pct * duration;
            }
            return;
        }
        
        // Otherwise, start playing this card and seek when ready
        this._pendingSeek = pct;
        this.playAudio(id);
    }

    beginCardScrubDrag(el, startX) {
        const card = el.closest('[data-report-id]');
        if (!card) return;
        
        // Prevent conflicting drag operations
        if (this._dragState) return;
        
        const id = card.dataset.reportId;
        this._dragState = { el, id };
        this._suppressOpen = true; // prevent card open after drag-end click
        
        let finalSeekPct = 0;
        
        const onMove = (clientX) => {
            const rect = el.getBoundingClientRect();
            const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
            finalSeekPct = pct;
            
            // Update visual progress bar immediately
            const bar = el.querySelector('[data-card-progress]');
            if (bar) bar.style.width = `${pct * 100}%`;
            
            // Check if this is the currently active card (dynamic check during drag)
            const isCurrentlyActive = this.currentAudio && this.currentAudio.id === id && this.isPlaying;
            if (isCurrentlyActive && this.audioElement) {
                const duration = this.audioElement.duration;
                if (duration && !isNaN(duration)) {
                    this.audioElement.currentTime = pct * duration;
                }
            }
        };
        
        const move = (e) => onMove(e.clientX);
        const moveTouch = (e) => onMove(e.touches[0].clientX);
        
        const up = () => {
            // Check if this was a non-active card drag that needs to start playback
            const wasActiveCard = this.currentAudio && this.currentAudio.id === id && this.isPlaying;
            if (!wasActiveCard) {
                this._pendingSeek = finalSeekPct;
                this.playAudio(id);
            }
            cleanup();
        };
        const cleanup = () => {
            window.removeEventListener('mousemove', move);
            window.removeEventListener('mouseup', up);
            window.removeEventListener('touchmove', moveTouch);
            window.removeEventListener('touchend', up);
            this._dragState = null;
            this._dragEndedAt = Date.now();
            setTimeout(() => { this._suppressOpen = false; }, 100);
        };
        window.addEventListener('mousemove', move);
        window.addEventListener('mouseup', up);
        window.addEventListener('touchmove', moveTouch, { passive: true });
        window.addEventListener('touchend', up);
        onMove(startX);
    }

    ensureScrubTooltip() {
        if (this.scrubTooltipEl) return this.scrubTooltipEl;
        const el = document.createElement('div');
        el.id = 'scrubTooltip';
        el.className = 'pointer-events-none fixed text-[10px] px-1.5 py-0.5 rounded bg-black/70 text-white hidden z-50';
        document.body.appendChild(el);
        this.scrubTooltipEl = el;
        return el;
    }

    showScrubTooltip(container, event) {
        const el = this.ensureScrubTooltip();
        const rect = container.getBoundingClientRect();
        const clientX = event.clientX;
        const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
        // Prefer live duration if this is the active card
        let seconds = 0;
        const card = container.closest('[data-report-id]');
        let total = 0;
        if (this.currentAudio && card && this.currentAudio.id === card.dataset.reportId && this.audioElement.duration) {
            total = this.audioElement.duration;
            seconds = total * pct;
        } else {
            total = parseFloat(container.getAttribute('data-total-seconds') || '0');
            seconds = total * pct;
        }
        el.textContent = `${this.formatDuration(seconds)} / ${this.formatDuration(total)}`;
        el.style.left = Math.round(clientX + 8) + 'px';
        el.style.top = Math.round(rect.top - 18) + 'px';
        el.classList.remove('hidden');
    }

    hideScrubTooltip() {
        if (this.scrubTooltipEl) this.scrubTooltipEl.classList.add('hidden');
    }

    handleSearch() {
        this.searchQuery = this.searchInput.value.trim();
        this.currentPage = 1;
        this.updateHeroBadges();
        this.loadContent();
    }

    setSortMode(mode) {
        this.currentSort = mode;
        this.currentPage = 1;
        this.updateSortToggle();
        this.updateRadioSortUI();
        
        // Scroll to top of results to make sorting change visible
        const mainContent = document.querySelector('main');
        if (mainContent) {
            mainContent.scrollTop = 0;
        }
        
        // Clear current content and show loading to indicate change
        if (this.contentGrid) {
            this.contentGrid.innerHTML = '<div class="col-span-full text-center py-8 text-slate-500">Loading sorted results...</div>';
        }
        
        this.loadContent();
    }

    updateSortToggle() {
        if (!this.sortToolbar) return;
        this.sortToolbar.querySelectorAll('[data-sort]').forEach(btn => {
            const active = btn.dataset.sort === this.currentSort;
            if (active) {
                // Apply selected state
                btn.classList.add('bg-audio-500', 'text-white', 'dark:bg-audio-600');
                btn.classList.remove('bg-white', 'dark:bg-slate-700', 'text-slate-700', 'dark:text-slate-200');
            } else {
                // Apply unselected state
                btn.classList.remove('bg-audio-500', 'text-white', 'dark:bg-audio-600');
                btn.classList.add('bg-white', 'dark:bg-slate-700', 'text-slate-700', 'dark:text-slate-200');
            }
        });
    }

    updateRadioSortUI() {
        // Update radio button states
        document.querySelectorAll('input[name="sortBy"]').forEach(radio => {
            const isSelected = radio.value === this.currentSort;
            const radioDiv = radio.nextElementSibling;
            const innerDiv = radioDiv.querySelector('div');
            
            if (isSelected) {
                radio.checked = true;
                radioDiv.classList.remove('border-slate-300', 'dark:border-slate-600');
                radioDiv.classList.add('border-audio-500');
                innerDiv.classList.remove('bg-transparent');
                innerDiv.classList.add('bg-audio-500');
            } else {
                radio.checked = false;
                radioDiv.classList.remove('border-audio-500');
                radioDiv.classList.add('border-slate-300', 'dark:border-slate-600');
                innerDiv.classList.remove('bg-audio-500');
                innerDiv.classList.add('bg-transparent');
            }
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

    applyFilterFromChip(filterType, filterValue, parentCategory = null) {
        console.log('🔍 Filter chip clicked:', { filterType, filterValue, parentCategory });
        
        // Only clear filters of the same type (preserve other filter types)
        if (filterType === 'channel') {
            // For channels, only clear other channel filters (preserve categories, etc.)
            document.querySelectorAll('input[data-filter="channel"]').forEach(cb => {
                cb.checked = false;
            });
        } else if (filterType === 'category') {
            // For categories, only clear category and subcategory filters (preserve channels, etc.)
            document.querySelectorAll('input[data-filter="category"], input[data-filter="subcategory"]').forEach(cb => {
                cb.checked = false;
            });
        } else if (filterType === 'subcategory') {
            // For subcategories, clear all category-related filters (same as category chips)
            document.querySelectorAll('input[data-filter="category"], input[data-filter="subcategory"]').forEach(cb => {
                cb.checked = false;
            });
        } else {
            // For other filter types (content_type, complexity, language), only clear that specific type
            document.querySelectorAll(`input[data-filter="${filterType}"]`).forEach(cb => {
                cb.checked = false;
            });
        }
        
        // Apply the clicked filter
        let checkbox = null;
        if (filterType === 'subcategory' && parentCategory) {
            const sel = `input[data-filter="subcategory"][data-parent-category="${CSS.escape(parentCategory)}"][value="${CSS.escape(filterValue)}"]`;
            checkbox = document.querySelector(sel);
        }
        if (!checkbox) {
            checkbox = document.querySelector(`input[data-filter="${filterType}"][value="${CSS.escape(filterValue)}"]`);
        }
        if (checkbox) {
            checkbox.checked = true;
            // If it's a subcategory, also check its parent category
            if (filterType === 'subcategory') {
                const parent = parentCategory || checkbox.dataset.parentCategory;
                if (parent) {
                    const parentCheckbox = document.querySelector(`input[data-filter="category"][value="${CSS.escape(parent)}"]`);
                    if (parentCheckbox) {
                        parentCheckbox.checked = true;
                    }
                }
            }
        }
        
        // Trigger filter update
        this.handleFilterChange();
        
        // Show visual feedback that filter was applied
        this.showFilterAppliedFeedback(filterType, filterValue);
    }

    clearAllFilters() {
        document.querySelectorAll('input[type="checkbox"][data-filter]').forEach(cb => {
            cb.checked = false;
        });
        this.currentFilters = {};
        this.loadContent();
    }

    showFilterAppliedFeedback(filterType, filterValue) {
        // Simple toast notification or could expand the filter drawer
        console.log(`Applied ${filterType} filter: ${filterValue}`);
        // Could add a subtle visual indicator here
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
        const playableItems = this.rebuildPlaylist();
        if (!playableItems.length) {
            this.showToast('No audio summaries available', 'warn');
            return;
        }
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

    formatReadingTime(minutes) {
        if (!minutes || isNaN(minutes)) return null;
        
        if (minutes < 1) return '< 1 min';
        return `${minutes} min`;
    }

    getButtonDurations(item) {
        const durations = {};
        
        
        // Read duration from media_metadata.estimated_reading_minutes or calculate from word_count
        if (item.media_metadata?.estimated_reading_minutes) {
            durations.read = this.formatReadingTime(item.media_metadata.estimated_reading_minutes);
        } else if (item.word_count) {
            // Fallback: calculate reading time from word_count (200 words per minute)
            const readingMinutes = Math.max(1, Math.round(item.word_count / 200));
            durations.read = this.formatReadingTime(readingMinutes);
        }
        
        // Listen duration from media_metadata.mp3_duration_seconds
        if (item.media_metadata?.mp3_duration_seconds) {
            durations.listen = this.formatDuration(item.media_metadata.mp3_duration_seconds);
        }
        
        // Watch duration from media_metadata.video_duration_seconds or fallback to duration_seconds
        const videoDuration = item.media_metadata?.video_duration_seconds || item.duration_seconds;
        if (videoDuration) {
            durations.watch = this.formatDuration(videoDuration);
        }
        
        return durations;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    truncateText(value, max = 24) {
        if (!value) return '';
        const str = String(value);
        if (str.length <= max) return str;
        return `${str.slice(0, max - 1)}…`;
    }

    formatRelativeTime(value) {
        if (!value) return '';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '';
        const diffMs = Date.now() - date.getTime();
        const absMs = Math.abs(diffMs);
        if (absMs < 5000) return 'just now';
        const units = [
            { label: 'day', ms: 86400000 },
            { label: 'hour', ms: 3600000 },
            { label: 'minute', ms: 60000 },
            { label: 'second', ms: 1000 }
        ];
        for (const { label, ms } of units) {
            if (absMs >= ms || label === 'second') {
                const valueRounded = Math.round(absMs / ms);
                if (valueRounded === 0) return 'just now';
                const plural = valueRounded === 1 ? label : `${label}s`;
                return diffMs >= 0 ? `${valueRounded} ${plural} ago` : `in ${valueRounded} ${plural}`;
            }
        }
        return '';
    }

    getReprocessToken(forcePrompt = false) {
        if (!forcePrompt && this.reprocessToken) {
            return this.reprocessToken;
        }
        try {
            if (!forcePrompt && this.reprocessTokenSource !== 'prompt') {
                const stored = localStorage.getItem('ytv2.reprocessToken');
                if (stored) {
                    this.reprocessToken = stored;
                    this.reprocessTokenSource = 'storage';
                    this.updateReprocessFootnote();
                    return stored;
                }
            }
        } catch (_) {
            // ignore storage errors
        }

        if (!forcePrompt && this.reprocessTokenSource !== 'window' && typeof window !== 'undefined' && window.REPROCESS_TOKEN) {
            this.reprocessToken = window.REPROCESS_TOKEN;
            this.reprocessTokenSource = 'window';
            this.updateReprocessFootnote();
            return this.reprocessToken;
        }

        const entered = typeof window !== 'undefined' ? window.prompt('Enter reprocess token') : null;
        if (entered) {
            this.reprocessToken = entered.trim();
            this.reprocessTokenSource = 'prompt';
            try { localStorage.setItem('ytv2.reprocessToken', this.reprocessToken); this.reprocessTokenSource = 'storage'; } catch (_) {}
            this.updateReprocessFootnote();
            return this.reprocessToken;
        }

        this.updateReprocessFootnote();
        return null;
    }

    resetStoredReprocessToken() {
        try { localStorage.removeItem('ytv2.reprocessToken'); } catch (_) {}
        if (typeof window !== 'undefined' && window.REPROCESS_TOKEN) {
            this.reprocessToken = window.REPROCESS_TOKEN;
            this.reprocessTokenSource = 'window';
        } else {
            this.reprocessToken = null;
            this.reprocessTokenSource = null;
        }
        this.updateReprocessFootnote();
        this.showToast('Reprocess token cleared. You will be prompted next time.', 'info');
    }

    updateReprocessFootnote() {
        if (!this.reprocessFootnote) return;
        let text = 'Provide the shared token when prompted.';
        if (this.reprocessTokenSource === 'window') {
            text = 'Token provided by backend configuration.';
        } else if (this.reprocessTokenSource === 'storage') {
            text = 'Using token saved locally. Change token to update.';
        } else if (this.reprocessTokenSource === 'prompt') {
            text = 'Token cached locally for quick access.';
        }
        this.reprocessFootnote.textContent = text;
    }

    /**
     * Format Key Points with structured markers if present, fallback to normal formatting
     * Detects "**Main topic:**" and "**Key points:**" markers and renders them nicely
     */
    /**
     * Normalize summary content - handle both string and object formats from chunked processing
     */
    normalizeSummaryContent(summaryContent, summaryType) {
        // If already a string, return as-is
        if (typeof summaryContent === 'string') {
            return summaryContent;
        }

        // If object, pick the right variant based on summary type
        if (typeof summaryContent === 'object' && summaryContent) {
            const type = (summaryType || '').toLowerCase().replace(/[-_\s]/g, '');
            const pick = (...candidates) => candidates.find(v => typeof v === 'string' && v.trim());

            if (type === 'keypoints' || type === 'bulletpoints') {
                return pick(summaryContent.bullet_points, summaryContent.key_points, summaryContent.comprehensive) || '';
            } else if (type === 'comprehensive') {
                return pick(summaryContent.comprehensive, summaryContent.bullet_points, summaryContent.key_points) || '';
            } else if (type === 'audio') {
                return pick(summaryContent.summary, summaryContent.comprehensive, summaryContent.bullet_points, summaryContent.key_points) || '';
            } else {
                // Default fallback: prefer bullet_points, then key_points, then comprehensive
                return pick(summaryContent.bullet_points, summaryContent.key_points, summaryContent.comprehensive) || '';
            }
        }

        return String(summaryContent || '');
    }

    formatKeyPoints(rawText) {
        if (!rawText || typeof rawText !== 'string') {
            return '<p>No summary available.</p>';
        }

        // Normalize line breaks and trim
        const text = rawText.replace(/\r\n?/g, '\n').trim();

        // Check for structured markers
        const hasMainTopic = /^(?:•\s*)?\*\*Main topic:\*\*\s*.+$/mi.test(text);
        const hasKeyPoints = /\*\*Key points:\*\*/i.test(text);

        // Check for comprehensive summary structure (headers + bullets)
        const hasComprehensiveStructure = this.hasComprehensiveStructure(text);

        // If we have structured markers, use special formatting
        if (hasMainTopic || hasKeyPoints) {
            return this.renderStructuredKeyPoints(text);
        }
        // If we have comprehensive structure, format it nicely
        else if (hasComprehensiveStructure) {
            return this.renderComprehensiveContent(text);
        }

        // Fallback to normal paragraph formatting
        return text
            .split('\n')
            .map(s => s.trim())
            .filter(Boolean)
            .map(p => `<p>${this.escapeHtml(p)}</p>`)
            .join('') || '<p>No summary available.</p>';
    }

    /**
     * Render structured Key Points with proper formatting
     */
    renderStructuredKeyPoints(text) {
        const parts = [];

        // 1) Extract main topic
        const mainTopicMatch = text.match(/^(?:•\s*)?\*\*Main topic:\*\*\s*(.+)$/mi);
        const mainTopic = mainTopicMatch ? mainTopicMatch[1].trim() : null;

        // 2) Extract takeaway if present
        const takeawayMatch = text.match(/\*\*Takeaway:\*\*\s*(.+?)(?=\*\*|$)/is);
        const takeaway = takeawayMatch ? takeawayMatch[1].trim() : null;
        
        // 3) Find content after "**Key points:**" marker, before takeaway
        const keyStartIdx = text.search(/\*\*Key points:\*\*/i);
        let bulletBlock = '';
        
        if (keyStartIdx >= 0) {
            // Take everything after the "Key points:" marker
            let bulletText = text.slice(keyStartIdx).replace(/\*\*Key points:\*\*/i, '').trim();
            // Stop at takeaway marker if present
            if (takeawayMatch) {
                const takeawayIdx = bulletText.search(/\*\*Takeaway:\*\*/i);
                if (takeawayIdx >= 0) {
                    bulletText = bulletText.slice(0, takeawayIdx).trim();
                }
            }
            bulletBlock = bulletText;
        } else {
            // No "Key points:" marker, use everything except main topic and takeaway
            bulletBlock = text;
            if (mainTopicMatch) {
                bulletBlock = bulletBlock.replace(mainTopicMatch[0], '').trim();
            }
            if (takeawayMatch) {
                bulletBlock = bulletBlock.replace(takeawayMatch[0], '').trim();
            }
        }

        // Strip any leftover takeaway lines from bullet block (belt-and-suspenders)
        bulletBlock = bulletBlock.replace(/^\s*(?:[•\-–—]\s*)?\*\*takeaway:\*\*.*$/gmi, '').trim();

        // 3) Process bullet points
        const lines = bulletBlock.split('\n')
            .map(s => s.trim())
            .filter(Boolean);

        // Precompile takeaway detection regex
        const TAKEAWAY_BULLET_RE = /^\s*(?:[•\-–—]\s*)?\*\*takeaway:\*\*/i;

        const bullets = [];
        for (const line of lines) {
            // Match lines starting with • - – — (bullet points, including Unicode dashes)
            if (/^(?:•|-|–|—)\s+/.test(line)) {
                const bulletContent = line.replace(/^(?:•|-|–|—)\s+/, '').trim();
                // Skip any bullet that is actually a Takeaway marker
                if (!TAKEAWAY_BULLET_RE.test(bulletContent)) {
                    bullets.push(bulletContent);
                }
            }
        }

        // 4) Build HTML
        if (mainTopic) {
            parts.push(`<div class="kp-heading">${this.escapeHtml(mainTopic)}</div>`);
        }

        if (bullets.length > 0) {
            const bulletHtml = bullets
                .map(bullet => `<li>${this.escapeHtml(bullet)}</li>`)
                .join('');
            parts.push(`<ul class="kp-list">${bulletHtml}</ul>`);
        } else if (bulletBlock) {
            // No clear bullets found, but we have content - preserve with line breaks
            parts.push(`<div class="kp-fallback">${this.escapeHtml(bulletBlock).replace(/\n/g, '<br>')}</div>`);
        }

        // Add takeaway as bold concluding statement
        if (takeaway) {
            parts.push(`<div class="kp-takeaway"><strong>${this.escapeHtml(takeaway)}</strong></div>`);
        }

        return parts.length > 0 ? parts.join('') : '<p>No summary available.</p>';
    }

    /**
     * Detect comprehensive summary structure (headers + organized content)
     */
    hasComprehensiveStructure(text) {
        // Look for patterns that indicate structured comprehensive summaries
        const hasHeaders = /^[A-Z][^.\n]*\s*$/m.test(text); // Lines that look like headers
        const hasBulletPoints = /^(?:\s*[-•*]\s+)/m.test(text); // Bullet points
        const hasStructuredSections = /^(?:Overview|What's New|Key|Main|Summary|Takeaway)[\s:]/mi.test(text);
        
        return (hasHeaders && hasBulletPoints) || hasStructuredSections;
    }

    /**
     * Render comprehensive content with proper structure
     */
    renderComprehensiveContent(text) {
        const lines = text.split('\n').map(line => line.trim()).filter(Boolean);
        const parts = [];
        let currentSection = null;
        let currentBullets = [];

        for (const line of lines) {
            // Remove "Comprehensive Summary:" prefix if present
            if (line.match(/^Comprehensive Summary:\s*/i)) {
                continue;
            }

            // Check if this is a header (short line without punctuation, or ends with specific patterns)
            const isHeader = (
                (line.length < 80 && !line.endsWith('.') && !line.startsWith('-') && !line.startsWith('•')) ||
                line.match(/^[A-Z][^.]*:?\s*$/) ||
                line.match(/^(?:Overview|What's New|Key|Main|Summary|Takeaway|Cameras?|Processing|Workflow)/i)
            );

            const isBullet = line.match(/^\s*[-•*]\s+/);

            if (isHeader) {
                // Flush any pending bullets
                if (currentBullets.length > 0) {
                    const bulletHtml = currentBullets.map(bullet => `<li>${this.escapeHtml(bullet)}</li>`).join('');
                    parts.push(`<ul class="kp-list">${bulletHtml}</ul>`);
                    currentBullets = [];
                }

                // Add header
                parts.push(`<div class="kp-heading">${this.escapeHtml(line.replace(/:\s*$/, ''))}</div>`);
                currentSection = line;
            } else if (isBullet) {
                // Extract bullet content
                const bulletContent = line.replace(/^\s*[-•*]\s+/, '').trim();
                currentBullets.push(bulletContent);
            } else if (line.trim()) {
                // Flush any pending bullets
                if (currentBullets.length > 0) {
                    const bulletHtml = currentBullets.map(bullet => `<li>${this.escapeHtml(bullet)}</li>`).join('');
                    parts.push(`<ul class="kp-list">${bulletHtml}</ul>`);
                    currentBullets = [];
                }

                // Add as paragraph
                parts.push(`<p class="mb-3">${this.escapeHtml(line)}</p>`);
            }
        }

        // Flush any remaining bullets
        if (currentBullets.length > 0) {
            const bulletHtml = currentBullets.map(bullet => `<li>${this.escapeHtml(bullet)}</li>`).join('');
            parts.push(`<ul class="kp-list">${bulletHtml}</ul>`);
        }

        return parts.length > 0 ? parts.join('') : '<p>No summary available.</p>';
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
                const playableItems = this.getPlayableItems();
                const playableIds = new Set(playableItems.map(item => item.file_stem));
                const filtered = data.playlist.filter(id => playableIds.has(id));
                this.playlist = filtered.length ? filtered : playableItems.map(item => item.file_stem);

                if (this.playlist.length) {
                    this.currentTrackIndex = Math.min(Math.max(0, data.index), this.playlist.length - 1);
                    const id = this.playlist[this.currentTrackIndex];
                    const item = playableItems.find(x => x.file_stem === id) || playableItems[0];
                    if (item) {
                        this.setCurrentFromItem(item);
                    }
                } else {
                    this.currentTrackIndex = -1;
                    this.showNowPlayingPlaceholder();
                }
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
        // Telemetry disabled to avoid 404 errors
        console.log('[telemetry:batch]', buf);
    }

    sendTelemetry(eventName, payload = {}) {
        const sampled = ['cta_listen','cta_watch'].includes(eventName) ? (Math.random() < 0.25) : true;
        if (!sampled) return;
        this.queueTelemetry({ event: eventName, ...payload, t: Date.now() });
    }

    // Mobile sidebar methods
    openMobileSidebar() {
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
            // Force display the sidebar on mobile by overriding responsive classes
            sidebar.classList.remove('hidden');
            sidebar.classList.add('flex');
            // Ensure it's shown as overlay on mobile
            sidebar.style.display = 'block';
            // Prevent body scroll when sidebar is open
            document.body.style.overflow = 'hidden';
        }
    }

    closeMobileSidebar() {
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
            // Hide the sidebar properly
            sidebar.classList.remove('flex');
            sidebar.classList.add('hidden');
            sidebar.style.display = '';
            // Restore body scroll
            document.body.style.overflow = '';
        }
    }

    // Mobile progress bar seek
    seekToMobile(event) {
        const rect = this.mobileProgressContainer.getBoundingClientRect();
        const raw = (event.clientX - rect.left) / rect.width;
        const percentage = Math.max(0, Math.min(1, raw));
        const duration = this.audioElement.duration;
        if (duration) this.audioElement.currentTime = percentage * duration;
    }

    // Clean up scrubbing state variables to prevent conflicts between sessions
    _cleanupScrubState() {
        this._pendingSeek = null;
        this._dragState = null;
        this._suppressOpen = false;
        this._dragEndedAt = null;
        
        // Clean up any lingering event listeners
        try {
            ['mousemove', 'mouseup', 'touchmove', 'touchend'].forEach(event => {
                window.removeEventListener(event, this._tempHandler);
            });
        } catch(e) { /* ignore */ }
    }

    // Progress bar drag handling for both desktop and mobile mini players
    beginProgressDrag(event, isMobile) {
        if (!this.audioElement || !this.currentAudio) return;
        
        // Prevent conflicting drag operations
        if (this._dragState) return;
        
        event.preventDefault();
        const container = isMobile ? this.mobileProgressContainer : this.progressContainer;
        const progressBar = isMobile ? this.mobileProgressBar : this.progressBar;
        
        const onMove = (clientX) => {
            const rect = container.getBoundingClientRect();
            const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
            
            // Update visual progress
            if (progressBar) progressBar.style.width = `${pct * 100}%`;
            
            // Seek audio
            const duration = this.audioElement.duration;
            if (duration && !isNaN(duration)) {
                this.audioElement.currentTime = pct * duration;
            }
        };
        
        const move = (e) => onMove(e.clientX);
        const moveTouch = (e) => onMove(e.touches[0].clientX);
        
        const cleanup = () => {
            window.removeEventListener('mousemove', move);
            window.removeEventListener('mouseup', cleanup);
            window.removeEventListener('touchmove', moveTouch);
            window.removeEventListener('touchend', cleanup);
        };
        
        window.addEventListener('mousemove', move);
        window.addEventListener('mouseup', cleanup);
        window.addEventListener('touchmove', moveTouch, { passive: true });
        window.addEventListener('touchend', cleanup);
        
        // Initial position
        const clientX = event.clientX || (event.touches && event.touches[0] ? event.touches[0].clientX : 0);
        onMove(clientX);
    }
}

// Initialize the dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.audioDashboard = new AudioDashboard();
    
    // Optional: Enable fetch interceptor for debugging (per OpenAI recommendation)
    // Uncomment the lines below to see all API requests in console
    /*
    (async () => {
        const _fetch = window.fetch;
        window.fetch = (...args) => {
            if (String(args[0]).includes('/api/reports?')) {
                console.log('[YTV2] REQUEST =>', args[0]);
            }
            return _fetch(...args);
        };
    })();
    */
});
