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

const REPROCESS_VARIANTS = [
    { id: 'comprehensive', label: 'Comprehensive', icon: '📝', kind: 'text' },
    { id: 'bullet-points', label: 'Key Points', icon: '🎯', kind: 'text' },
    { id: 'key-insights', label: 'Insights', icon: '💡', kind: 'text' },
    { id: 'audio', label: 'Audio (EN)', icon: '🎙️', kind: 'audio' },
    { id: 'audio-fr', label: 'Audio français', icon: '🎙️🇫🇷', kind: 'audio', language: 'fr', proficiency: true },
    { id: 'audio-es', label: 'Audio español', icon: '🎙️🇪🇸', kind: 'audio', language: 'es', proficiency: true }
];

const PROFICIENCY_LEVELS = [
    { level: 'beginner', icon: '🟢', labels: { default: 'Beginner', fr: 'Débutant', es: 'Principiante' } },
    { level: 'intermediate', icon: '🟡', labels: { default: 'Intermediate', fr: 'Intermédiaire', es: 'Intermedio' } },
    { level: 'advanced', icon: '🔵', labels: { default: 'Advanced', fr: 'Avancé', es: 'Avanzado' } }
];

const VARIANT_META_MAP = REPROCESS_VARIANTS.reduce((map, variant) => {
    map[variant.id] = variant;
    return map;
}, {});

const TEXT_VARIANT_ORDER = REPROCESS_VARIANTS.filter((variant) => variant.kind === 'text').map((variant) => variant.id);

// Reader display preferences (MVP): size, line, family, theme
const READER_SIZE_MAP = { s: 0.95, m: 1.0, l: 1.1, xl: 1.2, xxl: 1.3 };
const READER_LINE_MAP = { tight: 1.45, normal: 1.6, loose: 1.8 };
const READER_FAMILY_MAP = {
    sans: "Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', sans-serif",
    serif: "ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif"
};
const READER_THEMES = ['light','sepia','dark'];
const READER_PARA_STYLES = ['spaced','indented'];
const READER_JUSTIFY = ['left','justify'];
// Measure mapping: tuned per feedback
// - Previous 'medium'(70ch) becomes 'narrow'
// - Previous 'wide'(80ch) becomes 'medium'
// - New 'wide' at 90ch bridges the gap to 'full'
const READER_MEASURE_MAP = {
    narrow: '70ch',          // old Medium
    medium: '80ch',          // old Wide
    wide: 'calc((100% + 80ch)/2)', // midpoint between current wide (80ch) and full (100%)
    full: '100%'
};

class AudioDashboard {
    constructor() {
        this.currentAudio = null;
        this.playlist = [];
        this.currentTrackIndex = -1;
        this.isPlaying = false;
        // Read UI feature flags (non-breaking if missing)
        this.flags = (typeof window !== 'undefined' && window.UI_FLAGS) ? window.UI_FLAGS : {};
        this.config = (typeof window !== 'undefined' && window.DASHBOARD_CONFIG) ? window.DASHBOARD_CONFIG : {};
        const autoPlayConfig = this.config && this.config.autoPlayOnLoad;
        this.autoPlayOnLoad = autoPlayConfig === undefined;
        if (autoPlayConfig !== undefined) {
            const normalized = String(autoPlayConfig).toLowerCase();
            this.autoPlayOnLoad = !['false','0','no','off'].includes(normalized);
        }
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
        this.nasBaseUrl = '';
        this.nasBasicUser = '';
        this.nasBasicPass = '';
        this.basicAuthHeader = null;
        this.hasNasBridge = false;
        this.reprocessToken = null;
        this.reprocessTokenSource = null;
        this.pendingReprocess = null;

        // Filter state helpers
        this.initialSourceFilters = null;

        this.initializeElements();
        this.initNasConfig();
        this.updateReprocessFootnote();
        this.showNowPlayingPlaceholder();
        this.bindEvents();
        this.initRealtimeUpdates();
        // Only poll metrics when a NAS bridge is configured or flag enabled
        if (this.hasNasBridge || (this.flags && this.flags.metricsEnabled)) {
            this.startMetricsPolling();
        } else if (this.metricsPanel) {
            this.metricsPanel.classList.add('hidden');
        }
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

        // Top mini-player (desktop collapsed) elements
        this.topMiniPlayer = document.getElementById('topMiniPlayer');
        this.topPlayPauseBtn = document.getElementById('topPlayPauseBtn');
        this.topPlayIcon = document.getElementById('topPlayIcon');
        this.topPauseIcon = document.getElementById('topPauseIcon');
        this.topPrevBtn = document.getElementById('topPrevBtn');
        this.topNextBtn = document.getElementById('topNextBtn');
        this.topProgressContainer = document.getElementById('topProgressContainer');
        this.topProgressBar = document.getElementById('topProgressBar');
        this.topNowPlayingTitle = document.getElementById('topNowPlayingTitle');
        this.openFiltersTopBtn = document.getElementById('openFiltersTopBtn');
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
        this.sortSelect = document.getElementById('sortSelect');
        this.sourceFilters = document.getElementById('sourceFilters');
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
        this.wallViewBtn = document.getElementById('wallViewBtn');
        this.listViewBtnMobile = document.getElementById('listViewBtnMobile');
        this.gridViewBtnMobile = document.getElementById('gridViewBtnMobile');
        this.wallViewBtnMobile = document.getElementById('wallViewBtnMobile');
        this.sidebarCollapseToggle = document.getElementById('sidebarCollapseToggle');
        this.sidebarExpandToggle = document.getElementById('sidebarExpandToggle');
        this.sidebarElement = document.getElementById('sidebar');
        this.resultsHero = document.getElementById('resultsHero');
        
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
        this.sidebarCollapsed = localStorage.getItem('ytv2.sidebarCollapsed') === '1';
        this._collapsedForMobile = null;

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
        this.reprocessVariantGrid = document.getElementById('reprocessVariantGrid');
        this.reprocessLanguageLevel = document.getElementById('reprocessLanguageLevel');
        this.reprocessFootnote = document.getElementById('reprocessFootnote');
        this.reprocessTokenReset = document.getElementById('reprocessTokenReset');
        this.confirmReprocessBtn = document.getElementById('confirmReprocessBtn');
        this.cancelReprocessBtn = document.getElementById('cancelReprocessBtn');

        // Image controls in header
        this.imgModeThumbBtn = document.getElementById('imgModeThumbBtn');
        this.imgModeAiBtn = document.getElementById('imgModeAiBtn');
        this.imgModeRotateBtn = document.getElementById('imgModeRotateBtn');
        // Mobile image mode controls
        this.imgModeThumbBtnMobile = document.getElementById('imgModeThumbBtnMobile');
        this.imgModeAiBtnMobile = document.getElementById('imgModeAiBtnMobile');
        this.imgModeRotateBtnMobile = document.getElementById('imgModeRotateBtnMobile');
        // Settings menu controls
        this.viewListSettingBtn = document.getElementById('viewListSettingBtn');
        this.viewGridSettingBtn = document.getElementById('viewGridSettingBtn');
        this.viewWallSettingBtn = document.getElementById('viewWallSettingBtn');
        this.imgModeThumbSettingBtn = document.getElementById('imgModeThumbSettingBtn');
        this.imgModeAiSettingBtn = document.getElementById('imgModeAiSettingBtn');
        this.imgModeRotateSettingBtn = document.getElementById('imgModeRotateSettingBtn');
        // Admin token controls (Settings)
        this.adminTokenSetBtn = document.getElementById('adminTokenSetBtn');
        this.adminTokenClearBtn = document.getElementById('adminTokenClearBtn');

        // Image mode and hover-switch state
        this.imageMode = localStorage.getItem('ytv2.imageMode') || 'thumbnail';
        this.hoverSwitchEnabled = localStorage.getItem('ytv2.hoverSwitch') === '1';
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
        if (this.topProgressContainer) {
            this.topProgressContainer.addEventListener('click', (e) => this.seekToIn(this.topProgressContainer, e));
        }
        this.progressContainer.addEventListener('mousedown', (e) => this.beginProgressDrag(e, false));
        if (this.volumeBtn) this.volumeBtn.addEventListener('click', () => this.toggleMute());
        
        // Mobile mini-player controls
        if (this.mobilePlayPauseBtn) this.mobilePlayPauseBtn.addEventListener('click', () => this.togglePlayPause());
        if (this.mobilePrevBtn) this.mobilePrevBtn.addEventListener('click', () => this.playPrevious());
        if (this.mobileNextBtn) this.mobileNextBtn.addEventListener('click', () => this.playNext());
        // Top mini-player controls
        if (this.topPlayPauseBtn) this.topPlayPauseBtn.addEventListener('click', () => this.togglePlayPause());
        if (this.topPrevBtn) this.topPrevBtn.addEventListener('click', () => this.playPrevious());
        if (this.topNextBtn) this.topNextBtn.addEventListener('click', () => this.playNext());
        if (this.openFiltersTopBtn) this.openFiltersTopBtn.addEventListener('click', () => {
            this.sidebarCollapsed = false;
            localStorage.setItem('ytv2.sidebarCollapsed', '0');
            this.applySidebarCollapsedState();
            // focus the search field in sidebar if present
            setTimeout(() => { try { this.searchInput?.focus(); } catch(_){} }, 50);
        });
        if (this.mobileProgressContainer) {
            this.mobileProgressContainer.addEventListener('click', (e) => this.seekToMobile(e));
            this.mobileProgressContainer.addEventListener('mousedown', (e) => this.beginProgressDrag(e, true));
            this.mobileProgressContainer.addEventListener('touchstart', (e) => this.beginProgressDrag(e, true), { passive: true });
        }
        if (this.settingsToggle) this.settingsToggle.addEventListener('click', (e) => { e.stopPropagation(); this.toggleSettings(); });
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) refreshBtn.addEventListener('click', (e) => { e.preventDefault(); try { location.reload(); } catch(_) { window.location.href = window.location.href; } });
        if (this.settingsMenu) document.addEventListener('click', (e) => { if (!e.target.closest('#settingsMenu') && !e.target.closest('#settingsToggle')) this.closeSettings(); });
        if (this.themeButtons) this.themeButtons.forEach(btn => btn.addEventListener('click', () => this.setTheme(btn.dataset.theme)));
        if (this.cancelDeleteBtn) this.cancelDeleteBtn.addEventListener('click', () => this.closeConfirm());
        if (this.confirmDeleteBtn) this.confirmDeleteBtn.addEventListener('click', () => this.confirmDelete());

        // Image mode controls
        if (this.imgModeThumbBtn) this.imgModeThumbBtn.addEventListener('click', () => this.setImageMode('thumbnail'));
        if (this.imgModeAiBtn) this.imgModeAiBtn.addEventListener('click', () => this.setImageMode('ai'));
        if (this.imgModeRotateBtn) this.imgModeRotateBtn.addEventListener('click', () => this.setImageMode('rotate'));
        // Mobile bindings
        if (this.imgModeThumbBtnMobile) this.imgModeThumbBtnMobile.addEventListener('click', () => this.setImageMode('thumbnail'));
        if (this.imgModeAiBtnMobile) this.imgModeAiBtnMobile.addEventListener('click', () => this.setImageMode('ai'));
        if (this.imgModeRotateBtnMobile) this.imgModeRotateBtnMobile.addEventListener('click', () => this.setImageMode('rotate'));
        // Settings menu bindings (view + images)
        if (this.viewListSettingBtn) this.viewListSettingBtn.addEventListener('click', () => this.setViewMode('list'));
        if (this.viewGridSettingBtn) this.viewGridSettingBtn.addEventListener('click', () => this.setViewMode('grid'));
        if (this.viewWallSettingBtn) this.viewWallSettingBtn.addEventListener('click', () => this.setViewMode('wall'));
        if (this.imgModeThumbSettingBtn) this.imgModeThumbSettingBtn.addEventListener('click', () => this.setImageMode('thumbnail'));
        if (this.imgModeAiSettingBtn) this.imgModeAiSettingBtn.addEventListener('click', () => this.setImageMode('ai'));
        if (this.imgModeRotateSettingBtn) this.imgModeRotateSettingBtn.addEventListener('click', () => this.setImageMode('rotate'));
        // Admin token controls
        if (this.adminTokenSetBtn) this.adminTokenSetBtn.addEventListener('click', () => {
            this.closeSettings();
            const token = this.getReprocessToken(true);
            if (token) {
                this.showToast('Admin token saved locally', 'success');
            } else {
                this.showToast('Admin token not set', 'info');
            }
        });
        if (this.adminTokenClearBtn) this.adminTokenClearBtn.addEventListener('click', () => {
            this.closeSettings();
            this.resetStoredReprocessToken();
        });
        this.updateImageModeUI();
        
        // Search and filters
        this.searchInput.addEventListener('input', this.debounce(() => this.handleSearch(), 500));
        // Optional top search (mobile + desktop collapsed)
        this.searchInputTop = document.getElementById('searchInputTop');
        if (this.searchInputTop) {
            this.searchInputTop.addEventListener('input', this.debounce(() => {
                if (this.searchInput && this.searchInput.value !== this.searchInputTop.value) {
                    this.searchInput.value = this.searchInputTop.value;
                }
                this.handleSearch();
            }, 500));
        }
        // Header search (desktop)
        this.searchInputHeader = document.getElementById('searchInputHeader');
        if (this.searchInputHeader) {
            this.searchInputHeader.addEventListener('input', this.debounce(() => {
                const v = this.searchInputHeader.value;
                if (this.searchInput && this.searchInput.value !== v) this.searchInput.value = v;
                if (this.searchInputTop && this.searchInputTop.value !== v) this.searchInputTop.value = v;
                this.handleSearch();
            }, 500));
        }
        if (this.sortToolbar) {
            this.sortToolbar.querySelectorAll('[data-sort]').forEach(btn => {
                btn.addEventListener('click', () => this.setSortMode(btn.dataset.sort));
            });
        }
        
        // Compact sort select in header
        if (this.sortSelect) {
            this.sortSelect.value = this.currentSort;
            this.sortSelect.addEventListener('change', () => this.setSortMode(this.sortSelect.value));
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

        // Ensure kebab action for image-new always triggers (capture phase to beat other handlers)
        document.addEventListener('click', (e) => {
            const el = e.target.closest('[data-action="image-new"]');
            if (!el) return;
            e.preventDefault();
            e.stopPropagation();
            let id = null;
            const card = el.closest('[data-report-id]');
            if (card && card.dataset) id = card.dataset.reportId;
            if (!id) {
                const menu = el.closest('[data-kebab-menu][data-report-id]');
                if (menu && menu.getAttribute) id = menu.getAttribute('data-report-id');
            }
            if (id) this.handleCreateImagePrompt(id);
        }, true);
        const imageNewHandler = (e) => {
            const el = e.target.closest && e.target.closest('[data-action="image-new"]');
            if (!el) return;
            e.preventDefault();
            e.stopPropagation();
            let id = null;
            const card = el.closest('[data-report-id]');
            if (card && card.dataset) id = card.dataset.reportId;
            if (!id) {
                const menu = el.closest('[data-kebab-menu][data-report-id]');
                if (menu && menu.getAttribute) id = menu.getAttribute('data-report-id');
            }
            if (id) this.handleCreateImagePrompt(id);
        };
        document.addEventListener('pointerup', imageNewHandler, true);
        document.addEventListener('mousedown', imageNewHandler, true);
        
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

        // Global: Show all (select all) filters button
        const clearAllFiltersBtn = document.getElementById('clearAllFilters');
        if (clearAllFiltersBtn) {
            clearAllFiltersBtn.addEventListener('click', () => this.selectAllFilters());
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
        
        // Select All / Clear All buttons for Sources
        const selectAllSources = document.getElementById('selectAllSources');
        const clearAllSources = document.getElementById('clearAllSources');
        if (selectAllSources) {
            selectAllSources.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="source"]').forEach(cb => { cb.checked = true; });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }
        if (clearAllSources) {
            clearAllSources.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="source"]').forEach(cb => { cb.checked = false; });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }

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

        // Select All / Clear All buttons for Complexity
        const selectAllComplexities = document.getElementById('selectAllComplexities');
        const clearAllComplexities = document.getElementById('clearAllComplexities');
        if (selectAllComplexities) {
            selectAllComplexities.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="complexity"]').forEach(cb => { cb.checked = true; });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }
        if (clearAllComplexities) {
            clearAllComplexities.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="complexity"]').forEach(cb => { cb.checked = false; });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }

        // Select All / Clear All buttons for Languages
        const selectAllLanguages = document.getElementById('selectAllLanguages');
        const clearAllLanguages = document.getElementById('clearAllLanguages');
        if (selectAllLanguages) {
            selectAllLanguages.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="language"]').forEach(cb => { cb.checked = true; });
                this.currentFilters = this.computeFiltersFromDOM();
                this.updateHeroBadges();
                this.loadContent();
            });
        }
        if (clearAllLanguages) {
            clearAllLanguages.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="language"]').forEach(cb => { cb.checked = false; });
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
        
        // Mobile sidebar controls
        const mobileFiltersToggle = document.getElementById('mobileFiltersToggle');
        const closeSidebar = document.getElementById('closeSidebar');
        const sidebar = this.sidebarElement;
        
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
        this.desktopMediaQuery = window.matchMedia('(min-width: 1024px)');
        if (this.desktopMediaQuery?.addEventListener) {
            this.desktopMediaQuery.addEventListener('change', () => this.applySidebarCollapsedState());
        } else if (this.desktopMediaQuery?.addListener) {
            this.desktopMediaQuery.addListener(() => this.applySidebarCollapsedState());
        }

        const viewBindings = [
            { btn: this.listViewBtn, mode: 'list' },
            { btn: this.gridViewBtn, mode: 'grid' },
            { btn: this.wallViewBtn, mode: 'wall' },
            { btn: this.listViewBtnMobile, mode: 'list' },
            { btn: this.gridViewBtnMobile, mode: 'grid' },
            { btn: this.wallViewBtnMobile, mode: 'wall' }
        ];
        viewBindings.forEach(({ btn, mode }) => {
            if (!btn) return;
            btn.addEventListener('click', () => this.setViewMode(mode));
        });
        if (this.sidebarCollapseToggle) {
            this.sidebarCollapseToggle.addEventListener('click', () => {
                this.sidebarCollapsed = true;
                localStorage.setItem('ytv2.sidebarCollapsed', '1');
                this.applySidebarCollapsedState();
            });
        }
        if (this.sidebarExpandToggle) {
            this.sidebarExpandToggle.addEventListener('click', () => {
                this.sidebarCollapsed = false;
                localStorage.setItem('ytv2.sidebarCollapsed', '0');
                this.applySidebarCollapsedState();
            });
        }
        this.applySidebarCollapsedState();
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

    clearAllFilters() {
        try {
            // Uncheck all filter checkboxes
            document.querySelectorAll('input[type="checkbox"][data-filter]').forEach(cb => { cb.checked = false; });
            // Reset search
            const search = document.getElementById('searchInput');
            if (search) search.value = '';
            this.searchQuery = '';
            // Recompute and reload
            this.currentFilters = this.computeFiltersFromDOM();
            this.currentPage = 1;
            this.updateHeroBadges();
            this.loadContent();
        } catch (e) {
            console.warn('Failed to clear filters', e);
        }
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
                    if (this.autoPlayOnLoad) {
                        this.setCurrentFromItem(playableItems[0]);
                    } else {
                        this.showNowPlayingPlaceholder();
                    }
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
            const sseUrl = this.hasNasBridge ? this.buildSseUrl('/api/report-events') : '/api/report-events';
            const source = new EventSource(sseUrl);
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
            const response = await this.nasFetch('/api/reports?latest=true', { cache: 'no-store' });
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
            // Always fetch metrics from our own server to avoid CORS
            const response = await fetch('/api/metrics', { cache: 'no-store' });
            if (response.status === 404) {
                if (this.metricsPanel) this.metricsPanel.classList.add('hidden');
                return;
            }
            // Quiet expected 403 when metrics bridge is not available
            if (response.status === 403) {
                if (this.metricsPanel) this.metricsPanel.classList.add('hidden');
                return;
            }
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            this.metricsData = data;
            this.updateMetricsUI(data);
            if (this.metricsPanel) this.metricsPanel.classList.remove('hidden');
        } catch (error) {
            // Avoid noisy logs for expected 403s
            if (String(error?.message || '').includes('HTTP 403')) {
                if (this.metricsPanel) this.metricsPanel.classList.add('hidden');
                return;
            }
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

    initNasConfig() {
        const cfg = (typeof window !== 'undefined' && window.NAS_CONFIG) || {};
        this.nasBaseUrl = cfg.base_url || '';
        this.nasBasicUser = cfg.basic_user || '';
        this.nasBasicPass = cfg.basic_pass || '';
        this.hasNasBridge = Boolean(this.nasBaseUrl);

        if (!this.reprocessToken) {
            this.reprocessToken = (typeof window !== 'undefined' && window.REPROCESS_TOKEN) || null;
            this.reprocessTokenSource = this.reprocessToken ? 'window' : null;
        }

        if (!this.reprocessToken && typeof window !== 'undefined') {
            try {
                const stored = localStorage.getItem('ytv2.reprocessToken');
                if (stored) {
                    this.reprocessToken = stored;
                    this.reprocessTokenSource = 'storage';
                }
            } catch (_) {
                // Ignore storage errors
            }
        }

        if (this.nasBasicUser || this.nasBasicPass) {
            const credentials = `${this.nasBasicUser || ''}:${this.nasBasicPass || ''}`;
            this.basicAuthHeader = 'Basic ' + this.encodeBase64(credentials);
        }
    }

    joinNasUrl(path) {
        if (!path) return path;
        const asString = String(path);
        if (/^https?:\/\//i.test(asString)) {
            return asString;
        }
        if (!this.nasBaseUrl) return asString;
        try {
            return new URL(asString, this.nasBaseUrl).toString();
        } catch (error) {
            console.warn('Failed to build NAS URL', error);
            return asString;
        }
    }

    buildSseUrl(path) {
        if (!path) return path;
        const asString = String(path);
        if (/^https?:\/\//i.test(asString)) {
            return asString;
        }
        if (!this.nasBaseUrl) return asString;
        try {
            const url = new URL(asString, this.nasBaseUrl);
            if (this.nasBasicUser || this.nasBasicPass) {
                url.username = this.nasBasicUser || '';
                url.password = this.nasBasicPass || '';
            }
            url.searchParams.set('ngrok-skip-browser-warning', 'true');
            return url.toString();
        } catch (error) {
            console.warn('Failed to build SSE URL', error);
            return asString;
        }
    }

    nasFetch(path, options = {}) {
        if (!this.nasBaseUrl) {
            return fetch(path, options);
        }
        const url = this.joinNasUrl(path);
        const headers = new Headers(options.headers || {});
        if (this.basicAuthHeader) {
            headers.set('Authorization', this.basicAuthHeader);
        }
        headers.set('ngrok-skip-browser-warning', 'true');
        return fetch(url, { ...options, headers });
    }

    getPlayableItems(items = this.currentItems) {
        if (!Array.isArray(items)) return [];
        return items.filter(item => this.itemHasAudio(item));
    }

    rebuildPlaylist(items = this.currentItems) {
        const playable = this.getPlayableItems(items);
        this.playlist = playable.map(item => item.file_stem);
        return playable;
    }

    getAudioSourceForItem(item) {
        if (!this.itemHasAudio(item)) return null;
        // 1) Explicit URL from backend wins
        if (item?.media?.audio_url) {
            let url = this.normalizeAssetUrl(item.media.audio_url);
            if (item.audio_version) url += (url.includes('?') ? '&' : '?') + 'v=' + encodeURIComponent(String(item.audio_version));
            return url;
        }
        const reportId = item?.file_stem;
        const videoId = item?.video_id;
        const source = (item?.content_source || item?.source || '').toLowerCase();
        // 2) Standard mapped route by video id
        if (videoId) {
            let url = `/exports/by_video/${videoId}.mp3`;
            if (item.audio_version) url += `?v=${encodeURIComponent(String(item.audio_version))}`;
            return url;
        }
        // 3) Fallback to slug name
        if (reportId) {
            let url = `/exports/${reportId}.mp3`;
            if (item.audio_version) url += `?v=${encodeURIComponent(String(item.audio_version))}`;
            return url;
        }
        // 4) Legacy reddit naming under /exports/audio/reddit<slug>.mp3
        if (source === 'reddit' && reportId) {
            let url = `/exports/audio/reddit${reportId}.mp3`;
            if (item.audio_version) url += `?v=${encodeURIComponent(String(item.audio_version))}`;
            return url;
        }
        return null;
    }

    itemHasAudio(item) {
        if (!item) return false;
        const flag = Boolean(item.media && item.media.has_audio);
        const metaSecs = Number(item.media_metadata?.mp3_duration_seconds || item.media?.audio_duration_seconds || 0);
        const explicitUrl = Boolean(item.media && item.media.audio_url);
        return flag || explicitUrl || metaSecs > 0;
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
        this.refreshAudioVariantBlocks();
    }

    showNowPlayingPlaceholder(item = null) {
        this.currentAudio = null;
        this.isPlaying = false;
        this.resetAudioElement();
        document.body.classList.remove('has-current-audio');

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
            
            const sourceItems = (filters.content_source || filters.source || []).map(item => {
                const raw = (item.value ?? '').toString();
                const slug = raw.toLowerCase();
                const label = item.label || this.prettySourceLabel(slug || raw || 'other');
                return { ...item, value: slug || 'other', label };
            });
            this.renderFilterSection(sourceItems, this.sourceFilters, 'source');
            this.initialSourceFilters = sourceItems.slice();
            this.serverSourceFilters = sourceItems.slice();
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
            this.updateShowAllButtonVisibility();
            
        } catch (error) {
            console.error('Failed to load filters:', error);
        }
    }
    
    augmentSourceFiltersFromItems(items = []) {
        if (!Array.isArray(items) || !this.sourceFilters) return;
        const existingFilters = this.initialSourceFilters || [];
        const baseline = new Map(existingFilters.map(item => [item.value, { ...item }]));
        const knownSlugs = new Set(baseline.keys());

        const derivedCounts = new Map();
        for (const item of items) {
            const { slug, label } = this.inferSource(item);
            if (!slug) continue;
            const existing = derivedCounts.get(slug) || { value: slug, label, count: 0 };
            existing.count += 1;
            derivedCounts.set(slug, existing);
        }

        if (!derivedCounts.size) return;

        const serverDefined = Array.isArray(this.serverSourceFilters) && this.serverSourceFilters.length > 0;
        if (serverDefined) {
            let added = false;
            derivedCounts.forEach((entry, slug) => {
                if (!knownSlugs.has(slug)) {
                    baseline.set(slug, {
                        value: slug,
                        label: entry.label || this.prettySourceLabel(slug),
                        count: entry.count
                    });
                    knownSlugs.add(slug);
                    added = true;
                }
            });
            if (!added) return;
        } else {
            // No server counts; update in-place using derived data
            baseline.forEach((entry, slug) => {
                const derived = derivedCounts.get(slug);
                entry.count = Number.isFinite(derived?.count) ? derived.count : Number(entry.count) || 0;
            });
            derivedCounts.forEach((entry, slug) => {
                if (!baseline.has(slug)) {
                    baseline.set(slug, {
                        value: slug,
                        label: entry.label || this.prettySourceLabel(slug),
                        count: entry.count
                    });
                }
            });
        }

        const augmented = Array.from(baseline.values()).sort((a, b) => {
            if (b.count !== a.count) return b.count - a.count;
            return (a.label || a.value || '').localeCompare(b.label || b.value || '');
        });
        this.initialSourceFilters = augmented;

        const previouslySelected = new Set(this.currentFilters?.source || []);
        this.renderFilterSection(augmented, this.sourceFilters, 'source');

        const inputs = this.sourceFilters.querySelectorAll('input[data-filter="source"]');
        inputs.forEach((input) => {
            const value = input.value;
            if (previouslySelected.size === 0 || previouslySelected.has(value)) {
                input.checked = true;
            } else if (!knownSlugs.has(value)) {
                // auto-enable brand new sources
                input.checked = true;
            }
        });

        this.currentFilters = this.computeFiltersFromDOM();
        this.updateHeroBadges();
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
                        <span class="text-sm text-slate-700 dark:text-slate-200 flex-1">${this.escapeHtml(item.label || item.value)}</span>
                        <span class="text-xs text-slate-400 dark:text-slate-500 mr-2">${item.count}</span>
                        <button class="filter-only-btn text-xs text-audio-600 hover:text-audio-700 hover:underline" 
                                data-filter-only="category" 
                                data-filter-only-value="${this.escapeHtml(item.value)}"
                                title="Show only ${this.escapeHtml(item.label || item.value)}">only</button>
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
                                    <span class="text-sm text-slate-600 dark:text-slate-300 flex-1">${this.escapeHtml(sub.label || sub.value || sub)}</span>
                                    <span class="text-xs text-slate-400 dark:text-slate-500 mr-2">${sub.count}</span>
                                    <button class="filter-only-btn text-xs text-audio-600 hover:text-audio-700 hover:underline" 
                                            data-filter-only="subcategory" 
                                            data-filter-only-value="${this.escapeHtml(sub.value)}"
                                            data-parent-category="${this.escapeHtml(item.value)}"
                                            title="Show only ${this.escapeHtml(sub.label || sub.value || sub)}">only</button>
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
                    <span class="text-sm text-slate-700 dark:text-slate-200">${this.escapeHtml(item.label || item.value)}</span>
                    <span class="text-xs text-slate-400 dark:text-slate-500">${item.count}</span>
                </label>
                <button class="text-xs text-audio-600 dark:text-audio-400 hover:text-audio-700 dark:hover:text-audio-300 transition-colors cursor-pointer" 
                        data-filter-only="${filterType}" 
                        data-filter-only-value="${this.escapeHtml(item.value)}"
                        title="Show only ${this.escapeHtml(item.label || item.value)}">only</button>
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
                <span class="text-sm text-slate-700 dark:text-slate-200 flex-1">${this.escapeHtml(item.label || item.value)}</span>
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
                    <span class="text-sm text-slate-700 dark:text-slate-200 flex-1">${this.escapeHtml(item.label || item.value)}</span>
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
        // Show skeletons while fetching (only when we expect results)
        const showSkeletons = () => {
            if (!this.contentGrid) return;
            const skeleton = [];
            for (let i = 0; i < 12; i++) {
                skeleton.push(`
                <div class="animate-pulse rounded-xl border border-slate-200 dark:border-slate-700 bg-white/60 dark:bg-slate-800/60 p-4">
                  <div class="flex gap-4">
                    <div class="w-40 h-24 bg-slate-200 dark:bg-slate-700 rounded-lg"></div>
                    <div class="flex-1 space-y-3">
                      <div class="h-4 bg-slate-200 dark:bg-slate-700 rounded w-3/4"></div>
                      <div class="h-3 bg-slate-200 dark:bg-slate-700 rounded w-1/2"></div>
                      <div class="h-3 bg-slate-200 dark:bg-slate-700 rounded w-2/3"></div>
                      <div class="flex gap-2 mt-2">
                        <div class="h-6 w-20 bg-slate-200 dark:bg-slate-700 rounded-full"></div>
                        <div class="h-6 w-16 bg-slate-200 dark:bg-slate-700 rounded-full"></div>
                      </div>
                    </div>
                  </div>
                </div>`);
            }
            this.contentGrid.innerHTML = skeleton.join('');
        };

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

        // REQUIRE Source selection when any sources exist but none selected
        const hasSourceSelection = this.currentFilters.source && this.currentFilters.source.length > 0;
        const hasSourceOptions = document.querySelectorAll('input[data-filter="source"]').length > 0;
        if (!this.searchQuery && hasSourceOptions && !hasSourceSelection) {
            this.currentItems = [];
            this.renderContent([]);
            this.renderPagination({ page: 1, size: 12, total_count: 0, total_pages: 0, has_next: false, has_prev: false });
            this.updateResultsInfo({ page: 1, size: 12, total_count: 0, total_pages: 0 });
            this.contentGrid.innerHTML = `
                <div class="text-center py-12 text-slate-400">
                    <div class="text-lg mb-2">Choose one or more sources</div>
                    <div class="text-sm">Clear Sources = no sources selected → no results</div>
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
        // Render loading placeholders before fetching
        showSkeletons();
        
        const isWallMode = this.viewMode === 'wall';
        const requestedPage = isWallMode ? 1 : this.currentPage;
        const pageSize = isWallMode ? 500 : 12;

        const requestParams = new URLSearchParams(params);
        requestParams.append('page', requestedPage.toString());
        requestParams.append('size', pageSize.toString());
        requestParams.append('sort', this.currentSort);

        try {
            const requestUrl = `/api/reports?${requestParams}`;
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

            if (isWallMode) {
                const totalPagesFromServer = data.pagination?.pages ?? data.pagination?.total_pages ?? 1;
                if (totalPagesFromServer > 1 && items.length < (data.pagination?.total ?? data.pagination?.total_count ?? Infinity)) {
                    console.log(`[YTV2] Wall mode: fetching additional ${totalPagesFromServer - 1} pages`);
                    for (let page = 2; page <= totalPagesFromServer; page++) {
                        try {
                            const extraParams = new URLSearchParams(requestParams);
                            extraParams.set('page', page.toString());
                            const extraUrl = `/api/reports?${extraParams}`;
                            const extraResponse = await fetch(extraUrl);
                            const extraData = await extraResponse.json();
                            if (!extraResponse.ok) {
                                console.warn(`Wall mode extra page ${page} failed`, extraData);
                                break;
                            }
                            const extraItems = extraData.reports || extraData.data || [];
                            console.log(`[YTV2] Extra page ${page} returned ${extraItems.length} items`);
                            items = items.concat(extraItems);
                        } catch (extraErr) {
                            console.warn(`Wall mode extra page ${page} fetch threw`, extraErr);
                            break;
                        }
                    }
                }
            }

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
            this.augmentSourceFiltersFromItems(items);
            this.updateLatestIndexFromItems(items);

            const paginationMeta = data.pagination || {
                page: requestedPage,
                size: pageSize,
                total_count: items.length,
                total: items.length,
                total_pages: 1,
                pages: 1,
                has_next: false,
                has_prev: false
            };
            if (isWallMode) {
                paginationMeta.page = 1;
                paginationMeta.size = items.length;
                paginationMeta.total_pages = 1;
                paginationMeta.pages = 1;
                paginationMeta.has_next = false;
                paginationMeta.has_prev = false;
                if (typeof paginationMeta.total_count === 'number') {
                    paginationMeta.total = paginationMeta.total_count;
                } else {
                    paginationMeta.total = items.length;
                }
            }

            this.renderContent(this.currentItems);
            this.renderPagination(paginationMeta);
            this.updateResultsInfo(paginationMeta);
            const playableItems = this.rebuildPlaylist(this.currentItems);
            if (playableItems.length > 0) {
                if (this.currentAudio && this.playlist.includes(this.currentAudio.id)) {
                    this.currentTrackIndex = this.playlist.indexOf(this.currentAudio.id);
                } else if (this.autoPlayOnLoad) {
                    this.currentTrackIndex = 0;
                    this.setCurrentFromItem(playableItems[0]);
                } else {
                    this.currentTrackIndex = 0;
                    this.showNowPlayingPlaceholder();
                }
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
        
        let html = '';
        if (this.viewMode === 'grid') {
            html = `<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">${items.map(i => this.createGridCard(i)).join('')}</div>`;
        } else if (this.viewMode === 'wall') {
            html = `<div class="wall-grid">${items.map(i => this.createWallCard(i)).join('')}</div>`;
        } else {
            html = items.map(i => this.createContentCard(i)).join('');
        }
        this.contentGrid.innerHTML = html;
        this.decorateCards(items);

        // Make whole card clickable (except controls)
        this.contentGrid.querySelectorAll('[data-card]').forEach(card => {
            card.addEventListener('click', (e) => {
                if (this._suppressOpen) { e.preventDefault(); e.stopPropagation(); return; }
                // Ignore if click on a control, action, or filter chip
                if (e.target.closest('[data-control]') || e.target.closest('[data-action]') || e.target.closest('[data-filter-chip]')) return;
                if (this.viewMode === 'wall') {
                    const id = card.getAttribute('data-report-id');
                    if (id) { e.preventDefault(); e.stopPropagation(); this.handleWallRead(id, card); return; }
                }
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

        // Ensure global image mode is applied to all cards and error fallbacks are wired
        try {
            this.applyImageModeToAllCards();
            this.contentGrid.querySelectorAll('[data-card]').forEach(card => this.wireImageErrorHandlers(card));
        } catch (_) { /* no-op */ }

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

    decorateCards(items) {
        const cards = this.contentGrid.querySelectorAll('[data-card]');
        cards.forEach((card, index) => {
            if (card.dataset.decorated === 'true') return;
            const rawItem = items[index];
            if (!rawItem) return;

            const normalizedItem = this.normalizeCardItem(rawItem);
            const buttonDurations = this.getButtonDurations(normalizedItem);
            const hasAudio = this.itemHasAudio(normalizedItem);
            const actionContainer = card.querySelector('[data-action="read"]')?.parentElement;
            if (!actionContainer) return;

            const { categories, subcatPairs } = this.extractCatsAndSubcats(normalizedItem);

            // Remove legacy category/subcategory containers before injecting new layout
            const legacyContainers = new Set(
                Array.from(card.querySelectorAll('button[data-filter-chip="category"], button[data-filter-chip="subcategory"]'))
                    .map(btn => btn.parentElement)
            );
            legacyContainers.forEach(container => {
                if (container && container.parentElement) container.remove();
            });

            const categoryMarkup = this.renderCategorySection(normalizedItem.file_stem, categories, subcatPairs);
            if (categoryMarkup && categoryMarkup.trim()) {
                actionContainer.insertAdjacentHTML('beforebegin', categoryMarkup);
            }

            const actionMarkup = this.renderActionBar(normalizedItem, buttonDurations, hasAudio);
            actionContainer.insertAdjacentHTML('beforebegin', actionMarkup);
            actionContainer.style.display = 'none';

            card.querySelectorAll('[data-category-toggle]').forEach(btn => {
                if (!btn.dataset.moreLabel) btn.dataset.moreLabel = btn.textContent;
                btn.addEventListener('click', (event) => {
                    event.stopPropagation();
                    const targetId = btn.dataset.categoryToggle;
                    const extra = card.querySelector(`[data-category-extra="${targetId}"]`);
                    if (!extra) return;
                    const expanded = btn.getAttribute('aria-expanded') === 'true';
                    if (expanded) {
                        extra.classList.add('hidden');
                        btn.setAttribute('aria-expanded', 'false');
                        btn.textContent = btn.dataset.moreLabel || '+ more';
                    } else {
                        extra.classList.remove('hidden');
                        btn.setAttribute('aria-expanded', 'true');
                        btn.textContent = 'Show less';
                    }
                });
            });

            // Apply global image mode and wire error handlers
            this.applyImageModeToCard(card, index);
            this.wireImageErrorHandlers(card);
            card.dataset.decorated = 'true';
        });
    }

    onClickCardAction(e) {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const card = btn.closest('[data-report-id]');
        if (!card) return;
        e.stopPropagation();
        if (btn.hasAttribute('disabled') || btn.dataset.disabled !== undefined) return;
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
        if (action === 'image-new') { this.handleCreateImagePrompt(id); }
        if (action === 'watch') {
            const source = card.dataset.source || 'youtube';
            const videoId = card.dataset.videoId || '';
            const canonicalUrl = card.dataset.canonicalUrl || '';
            this.openSourceLink(source, videoId, canonicalUrl);
            this.sendTelemetry('cta_watch', { id, source, video_id: videoId || null });
        }
        if (action === 'toggle-image') {
            const media = card.querySelector('.summary-card__media');
            if (!media) return;
            const a = media.querySelector('[data-role="thumb-default"]');
            const b = media.querySelector('[data-role="thumb-summary"]');
            if (!a || !b) return;
            const aHidden = a.classList.contains('hidden');
            if (aHidden) {
                a.classList.remove('hidden');
                b.classList.add('hidden');
                btn.setAttribute('aria-pressed', 'false');
            } else {
                a.classList.add('hidden');
                b.classList.remove('hidden');
                btn.setAttribute('aria-pressed', 'true');
            }
            this.sendTelemetry('cta_toggle_image', { id });
        }
        if (action === 'delete') { this._lastDeleteTrigger = btn; this.toggleDeletePopover(card, true); }
        if (action === 'menu') { this.toggleKebabMenu(card, true, btn); }
        if (action === 'menu-close') { this.toggleKebabMenu(card, false); }
        if (action === 'copy-link') { this.copyLink(card, id); this.toggleKebabMenu(card, false); }
        if (action === 'toggle-image') {
            const media = card.querySelector('.summary-card__media, .stream-card__media, .relative.w-full.h-40');
            if (!media) return;
            const a = media.querySelector('[data-role="thumb-default"]');
            const b = media.querySelector('[data-role="thumb-summary"]');
            if (!a || !b) return;
            const aHidden = a.classList.contains('hidden');
            if (aHidden) { a.classList.remove('hidden'); b.classList.add('hidden'); }
            else { a.classList.add('hidden'); b.classList.remove('hidden'); }
            btn.setAttribute('aria-pressed', String(!aHidden));
            this.sendTelemetry('cta_toggle_image', { id });
        }
        if (action === 'reprocess') {
            this.toggleKebabMenu(card, false);
            this.openReprocessModal(id, card);
        }
        if (action === 'confirm-delete') { this.handleDelete(id, card); this.sendTelemetry('cta_delete', { id }); }
        if (action === 'cancel-delete') this.toggleDeletePopover(card, false);
        if (action === 'collapse') this.collapseCardInline(id);
    }

    handleRead(id) {
        if (this.viewMode === 'wall') {
            const card = this.contentGrid && this.contentGrid.querySelector(`[data-card][data-report-id="${CSS.escape(id)}"]`);
            return this.handleWallRead(id, card);
        }
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
        const win = window.open(url, '_blank', 'noopener');
        if (win) win.opener = null;
    }

    openSourceLink(source, videoId, canonicalUrl) {
        const slug = (source || 'youtube').toLowerCase();
        if (slug === 'youtube') {
            this.openYoutube(videoId);
            return;
        }
        if (!canonicalUrl) {
            this.showToast('No source link available', 'warn');
            return;
        }
        const win = window.open(canonicalUrl, '_blank', 'noopener');
        if (win) win.opener = null;
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
            const expandedContent = this.renderExpandedContent(data);
            region.innerHTML = expandedContent.html;
            this.bindExpandedVariantControls(region, expandedContent.variantInfo, expandedContent.defaultVariant);
            // Ensure normalized HTML only; reader display options are handled in wall reader header
            try { const bodyEl = region.querySelector('[data-summary-body]'); this.enhanceSummaryHtml(bodyEl); } catch(_) {}
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

        const fallbackSummary = this.computeFallbackSummaryHtml(data);
        const variantInfo = this.extractVariantInfo(data, fallbackSummary);

        let summaryHtml = fallbackSummary;
        let defaultVariant = variantInfo.defaultId;
        if (defaultVariant && variantInfo.map[defaultVariant]) {
            summaryHtml = variantInfo.map[defaultVariant].html;
        } else if (variantInfo.order.length) {
            const first = variantInfo.order[0];
            summaryHtml = variantInfo.map[first].html;
            defaultVariant = first;
        }

        if (!summaryHtml) {
            summaryHtml = '<p>No summary available.</p>';
        }

        const controlsHtml = variantInfo.order.length > 1
            ? `<div class="flex flex-wrap gap-2 text-xs" data-variant-controls>
                ${variantInfo.order.map((variantId) => {
                    const meta = variantInfo.map[variantId];
                    const icon = meta.icon ? `<span class="text-base">${meta.icon}</span>` : '';
                    return `<button type="button" data-variant="${variantId}" class="inline-flex items-center gap-2 px-3 py-1.5 rounded-md border transition variant-toggle">
                                ${icon}
                                <span class="font-medium">${meta.label}</span>
                            </button>`;
                }).join('')}
               </div>`
            : '';

        const html = `
          <div class="mt-3 mx-[-1rem] md:mx-[-1rem] sm:mx-0 rounded-xl bg-white/80 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 p-3 md:p-4 space-y-3 md:space-y-4" data-expanded data-default-variant="${defaultVariant || ''}">
            ${badges.length ? `<div class="flex items-center gap-2.5 text-slate-600 dark:text-slate-300 text-sm flex-wrap">${badges.join('')}</div>` : ''}
            ${controlsHtml}
            <h4 class="sr-only" data-expanded-title>Summary</h4>
            <div class="prose prose-sm sm:prose-base prose-slate dark:prose-invert max-w-none w-full break-words" data-summary-body>${summaryHtml}</div>
            <div class="flex items-center justify-end">
              <button class="ybtn ybtn-ghost px-3 py-1.5 rounded-md" data-action="collapse">Collapse</button>
            </div>
          </div>`;

        return {
            html,
            variantInfo,
            defaultVariant
        };
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
        if (id) {
            if (this.flags.cardExpandInline && this.viewMode !== 'wall') {
                const card = this.contentGrid.querySelector(`[data-report-id="${id}"]`);
                if (card) this.expandCardInline(id);
            }
            return;
        }
        const hash = String(window.location.hash || '');
        if (hash.startsWith('#read=')) {
            const rid = decodeURIComponent(hash.slice('#read='.length));
            if (rid) {
                const card = this.contentGrid && this.contentGrid.querySelector(`[data-report-id="${CSS.escape(rid)}"]`);
                this.handleRead(rid, card);
            }
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

        this.updateReprocessFootnote();

        this.initReprocessState(item);
        this.renderReprocessVariants();
        this.renderProficiencyControls();

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
        this.reprocessState = null;
        if (this.reprocessVariantGrid) this.reprocessVariantGrid.innerHTML = '';
        if (this.reprocessLanguageLevel) {
            this.reprocessLanguageLevel.innerHTML = '';
            this.reprocessLanguageLevel.classList.add('hidden');
        }
    }

    initReprocessState(item) {
        this.reprocessState = {
            selected: new Set(['comprehensive']),
            audioLevels: {
                'audio-fr': 'intermediate',
                'audio-es': 'intermediate'
            }
        };

        if (item?.media?.has_audio) {
            this.reprocessState.selected.add('audio');
        }
    }

    renderReprocessVariants() {
        if (!this.reprocessVariantGrid) return;
        const selected = (this.reprocessState && this.reprocessState.selected) || new Set();

        const html = REPROCESS_VARIANTS.map((variant) => {
            const isActive = selected.has(variant.id);
            const baseClasses = [
                'flex', 'items-center', 'gap-2', 'px-3', 'py-2', 'rounded-xl', 'text-sm', 'transition', 'duration-150', 'border'
            ];
            if (isActive) {
                baseClasses.push('bg-gradient-to-r', 'from-audio-500', 'to-indigo-500', 'text-white', 'border-transparent', 'shadow');
            } else {
                baseClasses.push('bg-white/85', 'dark:bg-slate-900/60', 'text-slate-600', 'dark:text-slate-200', 'border-white/60', 'dark:border-slate-700/60', 'hover:bg-white');
            }
            return `
                <button type="button" data-variant="${variant.id}" class="${baseClasses.join(' ')}">
                    <span class="text-lg">${variant.icon}</span>
                    <span class="font-medium">${variant.label}</span>
                </button>
            `;
        }).join('');

        this.reprocessVariantGrid.innerHTML = html;
        this.reprocessVariantGrid.querySelectorAll('[data-variant]').forEach((btn) => {
            btn.addEventListener('click', () => this.toggleVariantSelection(btn.dataset.variant));
        });
    }

    renderProficiencyControls() {
        if (!this.reprocessLanguageLevel) return;
        const selected = (this.reprocessState && this.reprocessState.selected) || new Set();
        const activeLanguages = REPROCESS_VARIANTS.filter((variant) => variant.proficiency && selected.has(variant.id));

        if (!activeLanguages.length) {
            this.reprocessLanguageLevel.innerHTML = '';
            this.reprocessLanguageLevel.classList.add('hidden');
            return;
        }

        const rows = activeLanguages.map((variant) => {
            const instruction = variant.language === 'fr'
                ? '🇫🇷 Choisissez votre niveau de français :'
                : variant.language === 'es'
                    ? '🇪🇸 Elige tu nivel de español:'
                    : 'Choose your proficiency:';
            const current = (this.reprocessState && this.reprocessState.audioLevels[variant.id]) || 'intermediate';

            const buttons = PROFICIENCY_LEVELS.map((opt) => {
                const label = opt.labels[variant.language] || opt.labels.default;
                const isActive = current === opt.level;
                const classes = [
                    'flex', 'items-center', 'gap-2', 'px-3', 'py-1.5', 'rounded-xl', 'text-xs', 'font-medium', 'transition'
                ];
                if (isActive) {
                    classes.push('bg-audio-500', 'text-white', 'shadow');
                } else {
                    classes.push('bg-white/80', 'dark:bg-slate-900/60', 'text-slate-600', 'dark:text-slate-200', 'border', 'border-white/40', 'dark:border-slate-700/50', 'hover:bg-white');
                }
                return `
                    <button type="button" data-proficiency-option data-variant="${variant.id}" data-level="${opt.level}" class="${classes.join(' ')}">
                        <span>${opt.icon}</span>
                        <span>${label}</span>
                    </button>
                `;
            }).join('');

            return `
                <div class="space-y-2" data-language-variant="${variant.id}">
                    <p class="text-xs text-slate-500">${instruction}</p>
                    <div class="flex flex-wrap gap-2">${buttons}</div>
                </div>
            `;
        }).join('');

        this.reprocessLanguageLevel.innerHTML = rows;
        this.reprocessLanguageLevel.classList.remove('hidden');
        this.reprocessLanguageLevel.querySelectorAll('[data-proficiency-option]').forEach((btn) => {
            btn.addEventListener('click', () => this.setAudioProficiency(btn.dataset.variant, btn.dataset.level));
        });
    }

    toggleVariantSelection(variantId) {
        if (!this.reprocessState || !variantId) return;
        const variant = REPROCESS_VARIANTS.find((v) => v.id === variantId);
        if (!variant) return;

        if (this.reprocessState.selected.has(variantId)) {
            this.reprocessState.selected.delete(variantId);
            if (variant.proficiency) {
                delete this.reprocessState.audioLevels[variantId];
            }
        } else {
            this.reprocessState.selected.add(variantId);
            if (variant.proficiency && !this.reprocessState.audioLevels[variantId]) {
                this.reprocessState.audioLevels[variantId] = 'intermediate';
            }
        }

        this.renderReprocessVariants();
        this.renderProficiencyControls();
    }

    setAudioProficiency(variantId, level) {
        if (!this.reprocessState || !variantId || !level) return;
        if (!this.reprocessState.selected.has(variantId)) return;
        this.reprocessState.audioLevels[variantId] = level;
        this.renderProficiencyControls();
    }

    getSelectedSummaryTypes() {
        if (!this.reprocessState) return [];
        const results = [];
        this.reprocessState.selected.forEach((id) => {
            const variant = REPROCESS_VARIANTS.find((v) => v.id === id);
            if (!variant) return;
            if (variant.proficiency) {
                const level = this.reprocessState.audioLevels[id] || 'intermediate';
                results.push(`${id}:${level}`);
            } else {
                results.push(id);
            }
        });
        return results;
    }

    computeFallbackSummaryHtml(data) {
        let summaryRaw = '';
        let summaryContent = data.summary;
        let summaryType = data.summary?.type;

        if (typeof summaryContent === 'string') {
            summaryRaw = summaryContent;
        } else if (summaryContent && typeof summaryContent === 'object') {
            if (summaryContent.content) {
                summaryRaw = this.normalizeSummaryContent(summaryContent.content, summaryType);
            } else {
                summaryRaw = this.normalizeSummaryContent(summaryContent, summaryType);
            }
        }

        if (!summaryRaw) summaryRaw = data.summary_text || data.analysis?.summary || data.analysis?.summary_text || data.summary_preview || '';

        if (!summaryRaw && Array.isArray(data.summary?.bullets)) {
            summaryRaw = data.summary.bullets.map((b) => (typeof b === 'string' ? `• ${b}` : '')).filter(Boolean).join('\n');
        }
        if (!summaryRaw && Array.isArray(data.analysis?.key_points)) {
            summaryRaw = data.analysis.key_points.map((b) => (typeof b === 'string' ? `• ${b}` : '')).filter(Boolean).join('\n');
        }

        summaryRaw = String(summaryRaw || '').replace(/\r\n?/g, '\n').trim();
        return summaryRaw ? this.formatKeyPoints(summaryRaw) : '';
    }

    extractVariantInfo(data, fallbackHtml) {
        const audioSrcForData = this.getAudioSourceForItem(data);
        const inferredReportId = data?.file_stem || data?.report_id || data?.id || data?.video_id || '';

        const result = {
            map: {},
            order: [],
            defaultId: null,
            audioSrc: audioSrcForData,
            reportId: inferredReportId,
            data
        };

        const addVariant = (id, payload = {}) => {
            if (!id) return;
            const normalized = String(id).toLowerCase();
            if (normalized === 'language') return;

            const meta = VARIANT_META_MAP[normalized];
            const isAudioVariant = meta && meta.kind === 'audio';

            let html = payload.html;
            if (!html && payload.text) {
                html = this.formatKeyPoints(payload.text);
            }
            if (!html && !isAudioVariant) return;

            if (!result.map[normalized]) {
                const label = meta?.label || this.prettyVariantLabel(normalized);
                const icon = meta?.icon || '';
                result.map[normalized] = {
                    id: normalized,
                    label,
                    icon,
                    html: html || '',
                    kind: meta?.kind || 'text',
                    audioSrc: payload.audioSrc || audioSrcForData || null,
                    raw: payload,
                    meta
                };
                result.order.push(normalized);
            }
        };

        const variantArrays = [];
        if (Array.isArray(data.summary_variants)) variantArrays.push(data.summary_variants);
        if (Array.isArray(data.summary?.variants)) variantArrays.push(data.summary.variants);

        variantArrays.forEach((arr) => {
            arr.forEach((item) => {
                if (!item || typeof item !== 'object') return;
                const variantId = item.variant || item.summary_type || item.type || item.id || item.name;
                const html = item.html || item.content?.html || '';
                const text = item.text || item.content || item.content?.text || '';
                addVariant(variantId, { html, text });
            });
        });

        if (data.summary && typeof data.summary === 'object' && !Array.isArray(data.summary)) {
            const aliasMap = {
                comprehensive: 'comprehensive',
                summary: 'comprehensive',
                bullet_points: 'bullet-points',
                bullets: 'bullet-points',
                key_points: 'bullet-points',
                key_insights: 'key-insights',
                insights: 'key-insights'
            };
            Object.entries(data.summary).forEach(([key, value]) => {
                if (typeof value !== 'string') return;
                const mapped = aliasMap[key];
                if (!mapped) return;
                addVariant(mapped, { text: value });
            });
        }

        if (!result.order.length && fallbackHtml) {
            addVariant('comprehensive', { html: fallbackHtml });
        }

        // Ordering preference
        const uniqueOrder = [...new Set(result.order)];
        const textFirst = TEXT_VARIANT_ORDER.filter((id) => uniqueOrder.includes(id));
        const remaining = uniqueOrder.filter((id) => !textFirst.includes(id));
        result.order = [...textFirst, ...remaining];

        const preferred = [data.summary_type, data.summary?.type, data.summary_type_latest, data.summary?.variant];
        for (const candidate of preferred) {
            const norm = candidate && String(candidate).toLowerCase();
            if (norm && result.map[norm]) {
                result.defaultId = norm;
                break;
            }
        }
        if (!result.defaultId && result.order.length) {
            result.defaultId = result.order[0];
        }

        return result;
    }

    bindExpandedVariantControls(region, variantInfo, defaultVariant) {
        if (!variantInfo || !variantInfo.order || variantInfo.order.length <= 1) return;
        const controls = region.querySelector('[data-variant-controls]');
        const body = region.querySelector('[data-summary-body]');
        if (!controls || !body) return;

        const setActive = (variantId) => {
            if (!variantId || !variantInfo.map[variantId]) return;
            const entry = variantInfo.map[variantId];
            controls.querySelectorAll('[data-variant]').forEach((btn) => {
                const isActive = btn.dataset.variant === variantId;
                btn.classList.toggle('bg-audio-500', isActive);
                btn.classList.toggle('text-white', isActive);
                btn.classList.toggle('border-transparent', isActive);
                btn.classList.toggle('shadow', isActive);
                btn.classList.toggle('bg-white/80', !isActive);
                btn.classList.toggle('dark:bg-slate-900/60', !isActive);
                btn.classList.toggle('text-slate-600', !isActive);
                btn.classList.toggle('dark:text-slate-200', !isActive);
                btn.classList.toggle('border-white/60', !isActive);
                btn.classList.toggle('dark:border-slate-700/60', !isActive);
            });

            if (entry.kind === 'audio') {
                const card = region.closest('[data-card]');
                const reportId = card?.dataset.reportId || variantInfo.reportId || '';
                let audioSrc = entry.audioSrc || variantInfo.audioSrc || null;
                if (!audioSrc && card) {
                    const videoId = card.dataset.videoId;
                    if (videoId) audioSrc = `/exports/by_video/${videoId}.mp3`;
                    else if (reportId) audioSrc = `/exports/${reportId}.mp3`;
                }
                body.innerHTML = this.renderInlineAudioVariant(reportId, entry, audioSrc);
                this.attachInlineAudioVariantHandlers(body, reportId, audioSrc);
            } else {
                body.innerHTML = entry.html || '<p class="text-sm text-slate-500">No summary available for this variant.</p>';
            }
            controls.dataset.currentVariant = variantId;
            this.refreshAudioVariantBlocks();
        };

        controls.querySelectorAll('[data-variant]').forEach((btn) => {
            btn.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                setActive(btn.dataset.variant);
            });
        });

        setActive(defaultVariant || variantInfo.order[0]);
    }

    prettyVariantLabel(id) {
        const spaced = id.replace(/[-_]+/g, ' ');
        return spaced.charAt(0).toUpperCase() + spaced.slice(1);
    }

    // === Reader Display Options (MVP) ===
    readerPrefsKey() {
        try { return (window.innerWidth || 0) >= 1024 ? 'readerDisplayPrefsDesktop' : 'readerDisplayPrefsMobile'; } catch(_) { return 'readerDisplayPrefs'; }
    }
    getReaderDisplayPrefs() {
        try {
            const raw = localStorage.getItem(this.readerPrefsKey()) || localStorage.getItem('readerDisplayPrefs');
            if (!raw) return { size: 'm', line: 'normal', family: 'sans', theme: 'light', paraStyle: 'spaced', justify: 'left', measure: 'narrow' };
            const obj = JSON.parse(raw);
            // Back-compat: remap older measures to new scale
            let storedMeasure = obj.measure;
            if (storedMeasure === 'medium') storedMeasure = 'narrow';
            else if (storedMeasure === 'wide') storedMeasure = 'medium';
            return {
                size: obj.size && READER_SIZE_MAP[obj.size] ? obj.size : 'm',
                line: obj.line && READER_LINE_MAP[obj.line] ? obj.line : 'normal',
                family: obj.family && READER_FAMILY_MAP[obj.family] ? obj.family : 'sans',
                theme: READER_THEMES.includes(obj.theme) ? obj.theme : 'light',
                paraStyle: READER_PARA_STYLES.includes(obj.paraStyle) ? obj.paraStyle : 'spaced',
                justify: READER_JUSTIFY.includes(obj.justify) ? obj.justify : 'left',
                measure: (storedMeasure && READER_MEASURE_MAP[storedMeasure]) ? storedMeasure : 'narrow'
            };
        } catch(_) {
            return { size: 'm', line: 'normal', family: 'sans', theme: 'light', paraStyle: 'spaced', justify: 'left', measure: 'narrow' };
        }
    }
    setReaderDisplayPrefs(next) {
        try {
            const cur = this.getReaderDisplayPrefs();
            const merged = { ...cur, ...next };
            localStorage.setItem(this.readerPrefsKey(), JSON.stringify(merged));
            return merged;
        } catch(_) { return this.getReaderDisplayPrefs(); }
    }
    applyReaderDisplayPrefs(container, bodyEl) {
        const prefs = this.getReaderDisplayPrefs();
        if (bodyEl) {
            const fs = READER_SIZE_MAP[prefs.size] || 1.0;
            const lh = READER_LINE_MAP[prefs.line] || 1.6;
            const ff = READER_FAMILY_MAP[prefs.family] || 'inherit';
            try { bodyEl.style.setProperty('--reader-font-size', fs + 'rem'); } catch(_) {}
            try { bodyEl.style.setProperty('--reader-line', String(lh)); } catch(_) {}
            try { bodyEl.style.setProperty('--reader-font-family', ff); } catch(_) {}
        }
        if (container) {
            try { container.classList.remove('reader-theme--light','reader-theme--sepia','reader-theme--dark'); } catch(_) {}
            const theme = this.getReaderDisplayPrefs().theme || 'light';
            try { container.classList.add('reader-theme--' + theme); } catch(_) {}
            // Paragraph style
            const para = this.getReaderDisplayPrefs().paraStyle || 'spaced';
            try { container.classList.toggle('reader-para--indented', para === 'indented'); } catch(_) {}
            // Justification (CSS applies only on desktop)
            const just = this.getReaderDisplayPrefs().justify || 'left';
            try { container.classList.toggle('reader-justify--on', just === 'justify'); } catch(_) {}
            // Measure (desktop-only cap; stored as variable used by CSS)
            const measureKey = this.getReaderDisplayPrefs().measure || 'medium';
            const mw = READER_MEASURE_MAP[measureKey] || '70ch';
            try { container.style.setProperty('--reader-measure', mw); } catch(_) {}
        }
    }
    openReaderDisplayPopover(container, bodyEl, anchorBtn) {
        // Close any existing
        try { document.querySelectorAll('.reader-display-popover').forEach(el => el.remove()); } catch(_) {}
        const prefs = this.getReaderDisplayPrefs();
        const pop = document.createElement('div');
        pop.className = 'reader-display-popover';
        pop.setAttribute('role', 'dialog');
        const segBtn = (attrs, label, pressed) => `<span role="button" ${attrs} aria-pressed="${pressed?'true':'false'}">${label}</span>`;
        const sizeSeg = `
          <div class="reader-segment" role="radiogroup" aria-label="Text size">
            ${segBtn('data-reader-size="s"', 'A', prefs.size==='s')}
            ${segBtn('data-reader-size="m"', 'A', prefs.size==='m')}
            ${segBtn('data-reader-size="l"', 'A', prefs.size==='l')}
            ${segBtn('data-reader-size="xl"', 'A', prefs.size==='xl')}
            ${segBtn('data-reader-size="xxl"', 'A', prefs.size==='xxl')}
          </div>`;
        const lineSeg = `
          <div class="reader-segment" role="radiogroup" aria-label="Line height">
            ${segBtn('data-reader-line="tight"', 'Tight', prefs.line==='tight')}
            ${segBtn('data-reader-line="normal"', 'Normal', prefs.line==='normal')}
            ${segBtn('data-reader-line="loose"', 'Loose', prefs.line==='loose')}
          </div>`;
        const familySeg = `
          <div class="reader-segment" role="radiogroup" aria-label="Font family">
            ${segBtn('data-reader-family="sans"', 'Sans', prefs.family==='sans')}
            ${segBtn('data-reader-family="serif"', 'Serif', prefs.family==='serif')}
          </div>`;
        const justifySeg = `
          <div class="reader-segment" role="radiogroup" aria-label="Justification">
            ${segBtn('data-reader-justify="left"', 'Left', prefs.justify==='left')}
            ${segBtn('data-reader-justify="justify"', 'Justified', prefs.justify==='justify')}
          </div>`;
        const paraTile = (id, label) => `
          <div class="reader-tile" data-reader-para="${id}" aria-pressed="${prefs.paraStyle===id?'true':'false'}" role="button" aria-label="${label}">
            <div class="tile-preview"><div class="tile-preview-inner">${'<div class=\\"strip\\"></div>'.repeat(3)}</div></div>
            <div class="tile-label">${label}</div>
          </div>`;
        const themeTile = (id, label) => `
          <div class="reader-tile" data-reader-theme="${id}" aria-pressed="${prefs.theme===id?'true':'false'}" role="button" aria-label="${label}">
            <div class="tile-preview"><div class="tile-preview-inner">${'<div class=\\"strip\\"></div>'.repeat(3)}</div></div>
            <div class="tile-label">${label}</div>
          </div>`;
        const measureTile = (id, label) => `
          <div class="reader-tile" data-reader-measure="${id}" aria-pressed="${prefs.measure===id?'true':'false'}" role="button" aria-label="${label}">
            <div class="tile-preview"><div class="tile-preview-inner">${'<div class=\\"strip\\"></div>'.repeat(3)}</div></div>
            <div class="tile-label">${label}</div>
          </div>`;
        const justifyMini = `
          <div class="justify-mini"><span class="jline"></span><span class="jline"></span><span class="jline"></span></div>`;
        pop.innerHTML = `
          <div class="reader-popover-header">
            <span class="title">Display Options</span>
            <div class="actions">
              <button type="button" class="reader-reset" data-reader-reset>Reset to Defaults</button>
              <button type="button" class="reader-close" aria-label="Close" data-reader-close>×</button>
            </div>
          </div>
          <div class="reader-panel reader-grid">
            <div class="reader-col">
              <div class="reader-group">
                <h5>Typography</h5>
                <div class="reader-field">
                  <div class="reader-field-label">Font Size</div>
                  <div class="reader-display-row" data-row="size">${sizeSeg}</div>
                </div>
                <div class="reader-field">
                  <div class="reader-field-label">Font Family</div>
                  <div class="reader-display-row" data-row="family">${familySeg}</div>
                </div>
                <div class="reader-field">
                  <div class="reader-field-label">Line Spacing</div>
                  <div class="reader-display-row" data-row="line">${lineSeg}</div>
                </div>
                <div class="reader-field">
                  <div class="reader-live-preview" id="readerPreview">The quick brown fox jumps over the lazy dog.</div>
                </div>
              </div>
              <div class="reader-group">
                <h5>Theme</h5>
                <div class="reader-tiles" data-row="theme">${[
                    themeTile('light','Light'),
                    themeTile('sepia','Sepia'),
                    themeTile('dark','Dark')
                ].join('')}</div>
              </div>
            </div>
            <div class="reader-col">
              <div class="reader-group">
                <h5>Layout</h5>
                <div class="reader-tiles" data-row="para">${[paraTile('spaced','Spaced'), paraTile('indented','Indented')].join('')}</div>
                <div class="reader-caption">paragraph style</div>
                <div class="reader-tiles" data-row="justify">${[
                    `<div class=\"reader-tile\" data-reader-justify=\"left\" aria-pressed=\"${prefs.justify==='left'?'true':'false'}\" role=\"button\" title=\"Ragged-right paragraphs\"><div class=\"tile-preview\"><div class=\"tile-preview-inner justify-mini\"><span class=\"jline\"></span><span class=\"jline\"></span><span class=\"jline\"></span></div></div><div class=\"tile-label\">Left</div></div>`,
                    `<div class=\"reader-tile\" data-reader-justify=\"justify\" aria-pressed=\"${prefs.justify==='justify'?'true':'false'}\" role=\"button\" title=\"Fully justified paragraphs\"><div class=\"tile-preview\"><div class=\"tile-preview-inner justify-mini\"><span class=\"jline\"></span><span class=\"jline\"></span><span class=\"jline\"></span></div></div><div class=\"tile-label\">Justified</div></div>`
                ].join('')}</div>
                <div class="reader-tiles" data-row="measure">${[
                    measureTile('narrow','Narrow'),
                    measureTile('medium','Medium'),
                    measureTile('wide','Wide'),
                    measureTile('full','Full')
                ].join('')}</div>
                <div class="reader-caption">reading width</div>
              </div>
            </div>
          </div>`;
        // Position relative to anchor (desktop) or as bottom sheet (mobile)
        const isMobile = (window.innerWidth || 0) <= 640;
        let scrim = null;
        if (isMobile) {
            try {
                scrim = document.createElement('div');
                scrim.className = 'reader-sheet-scrim';
                document.body.appendChild(scrim);
                pop.classList.add('reader-sheet');
                pop.style.position = 'fixed';
                pop.style.left = '0';
                pop.style.right = '0';
                pop.style.top = 'auto';
                pop.style.bottom = '0';
            } catch(_) {}
        } else {
            const anchorRect = anchorBtn.getBoundingClientRect();
            pop.style.position = 'fixed';
            pop.style.top = Math.round(anchorRect.bottom + 8) + 'px';
            pop.style.right = Math.round(Math.max(12, window.innerWidth - anchorRect.right)) + 'px';
        }
        document.body.appendChild(pop);
        // no preview block
        const closeAll = () => { try { pop.remove(); } catch(_) {} if (scrim) { try { scrim.remove(); } catch(_) {} scrim = null; } window.removeEventListener('resize', onAway, true); document.removeEventListener('click', onAway, true); };
        if (scrim) scrim.addEventListener('click', closeAll);
        const onAway = (e) => { if (!pop.contains(e.target) && e.target !== anchorBtn) closeAll(); };
        setTimeout(() => { document.addEventListener('click', onAway, true); window.addEventListener('resize', onAway, true); }, 0);
        // Handlers
        pop.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-reader-size], [data-reader-line], [data-reader-family], [data-reader-theme], [data-reader-para], [data-reader-justify], [data-reader-measure]');
            if (!btn) return;
            const size = btn.getAttribute('data-reader-size');
            const line = btn.getAttribute('data-reader-line');
            const family = btn.getAttribute('data-reader-family');
            const theme = btn.getAttribute('data-reader-theme');
            const para = btn.getAttribute('data-reader-para');
            const justify = btn.getAttribute('data-reader-justify');
            const measure = btn.getAttribute('data-reader-measure');
            let next = {};
            if (size && READER_SIZE_MAP[size]) next.size = size;
            if (line && READER_LINE_MAP[line]) next.line = line;
            if (family && READER_FAMILY_MAP[family]) next.family = family;
            if (theme && READER_THEMES.includes(theme)) next.theme = theme;
            if (para && READER_PARA_STYLES.includes(para)) next.paraStyle = para;
            if (justify && READER_JUSTIFY.includes(justify)) next.justify = justify;
            if (measure && READER_MEASURE_MAP[measure]) next.measure = measure;
            const merged = this.setReaderDisplayPrefs(next);
            this.applyReaderDisplayPrefs(container, bodyEl);
            // Update live preview
            try {
              const prev = pop.querySelector('#readerPreview');
              if (prev) {
                const fs = READER_SIZE_MAP[merged.size] || 1.0;
                const lh = READER_LINE_MAP[merged.line] || 1.6;
                const ff = READER_FAMILY_MAP[merged.family] || 'inherit';
                prev.style.fontSize = fs + 'rem';
                prev.style.lineHeight = String(lh);
                prev.style.fontFamily = ff;
              }
            } catch(_) {}
            // Update pressed states
            pop.querySelectorAll('[data-reader-size]').forEach(b => b.setAttribute('aria-pressed', b.getAttribute('data-reader-size')===merged.size ? 'true' : 'false'));
            pop.querySelectorAll('[data-reader-line]').forEach(b => b.setAttribute('aria-pressed', b.getAttribute('data-reader-line')===merged.line ? 'true' : 'false'));
            pop.querySelectorAll('[data-reader-family]').forEach(b => b.setAttribute('aria-pressed', b.getAttribute('data-reader-family')===merged.family ? 'true' : 'false'));
            pop.querySelectorAll('[data-reader-theme]').forEach(b => b.setAttribute('aria-pressed', b.getAttribute('data-reader-theme')===merged.theme ? 'true' : 'false'));
            pop.querySelectorAll('[data-reader-para]').forEach(b => b.setAttribute('aria-pressed', b.getAttribute('data-reader-para')===merged.paraStyle ? 'true' : 'false'));
            pop.querySelectorAll('[data-reader-justify]').forEach(b => b.setAttribute('aria-pressed', b.getAttribute('data-reader-justify')===merged.justify ? 'true' : 'false'));
            pop.querySelectorAll('[data-reader-measure]').forEach(b => b.setAttribute('aria-pressed', b.getAttribute('data-reader-measure')===merged.measure ? 'true' : 'false'));
            // Update micro preview for justification
            const jr = pop.querySelector('[data-row="justify"]');
            if (jr) jr.setAttribute('data-justify-state', merged.justify === 'justify' ? 'justify' : 'left');
            // Light telemetry on change
            try { this.sendTelemetry && this.sendTelemetry('reader_display_change', merged); } catch(_) {}
        });
        // Reset handler
        const resetBtn = pop.querySelector('[data-reader-reset]');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                // Derive default theme from current container
                let baseTheme = 'light';
                try {
                    if (container.classList.contains('reader-theme--dark')) baseTheme = 'dark';
                    else if (container.classList.contains('reader-theme--sepia')) baseTheme = 'sepia';
                } catch(_) {}
                const defaults = { size: 'm', line: 'normal', family: 'sans', theme: baseTheme, paraStyle: 'spaced', justify: 'left', measure: 'narrow' };
                const merged = this.setReaderDisplayPrefs(defaults);
                this.applyReaderDisplayPrefs(container, bodyEl);
                // Update UI state
                ['size','line','family','theme','para','justify','measure'].forEach(key => {
                  pop.querySelectorAll('[data-reader-' + key + ']').forEach(el => {
                    const val = el.getAttribute('data-reader-' + key);
                    const want = String(merged[key === 'para' ? 'paraStyle' : key]);
                    el.setAttribute('aria-pressed', val === want ? 'true' : 'false');
                  });
                });
                const jr = pop.querySelector('[data-row="justify"]');
                if (jr) jr.setAttribute('data-justify-state', 'left');
            });
        }
        const closeBtn = pop.querySelector('[data-reader-close]');
        if (closeBtn) closeBtn.addEventListener('click', () => { closeAll(); });
    }

    async submitReprocess() {
        if (!this.pendingReprocess) return;
        const videoId = this.pendingReprocess.videoId;
        if (!videoId) {
            this.showToast('Missing video id for reprocess', 'error');
            return;
        }
        const summaryTypes = this.getSelectedSummaryTypes();
        if (!summaryTypes.length) {
            this.showToast('Select at least one summary type', 'warn');
            if (this.confirmReprocessBtn) {
                this.confirmReprocessBtn.disabled = false;
            }
            return;
        }
        const regenerateAudio = summaryTypes.some((type) => type.startsWith('audio'));
        const token = this.getReprocessToken();
        if (!token) {
            this.showToast('Reprocess token required', 'warn');
            if (this.confirmReprocessBtn) {
                this.confirmReprocessBtn.disabled = false;
            }
            return;
        }

        if (this.confirmReprocessBtn) {
            this.confirmReprocessBtn.disabled = true;
        }

        try {
            const payload = {
                video_id: videoId,
                regenerate_audio: regenerateAudio
            };
            if (summaryTypes.length) {
                payload.summary_types = summaryTypes;
            }
            const response = await this.nasFetch('/api/reprocess', {
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
        const normalizedItem = this.normalizeCardItem(item);
        // Experimental Tailwind-first card revamp (v5)
        if (this.flags && this.flags.twRevamp) {
            return this.renderStreamCardTW(normalizedItem);
        }
        if (this.flags && this.flags.cardV4) {
            return this.renderStreamCardV4(normalizedItem);
        }
        return this.renderSummaryCard(normalizedItem, { view: 'list' });
    }

    createGridCard(item) {
        const normalizedItem = this.normalizeCardItem(item);
        // Experimental Tailwind-first card revamp (v5)
        if (this.flags && this.flags.twRevamp) {
            return this.renderGridCardTW(normalizedItem);
        }
        if (this.flags && this.flags.cardV4) {
            return this.renderGridCardV4(normalizedItem);
        }
        return this.renderSummaryCard(normalizedItem, { view: 'grid' });
    }

    createWallCard(item) {
        const normalizedItem = this.normalizeCardItem(item);
        if (this.flags && this.flags.twRevamp) {
            return this.renderWallCardTW(normalizedItem);
        }
        return this.renderGridCardTW(normalizedItem);
    }

    // V4 List card: audio-first stream card (no autoplay)
    renderStreamCardV4(item) {
        const hasAudio = this.itemHasAudio(item);
        const rawSource = item.content_source || 'youtube';
        const source = rawSource.toLowerCase();
        const hasWatchLink = source === 'youtube' ? Boolean(item.video_id) : Boolean(item.canonical_url);
        const href = `/${item.file_stem}.json?v=2`;
        const buttonDurations = this.getButtonDurations(item);
        const { categories, subcatPairs } = this.extractCatsAndSubcats(item);
        const totalSecs = (item.media_metadata && item.media_metadata.mp3_duration_seconds)
            ? item.media_metadata.mp3_duration_seconds
            : (item.duration_seconds || 0);
        const isPlaying = this.currentAudio && this.currentAudio.id === item.file_stem && this.isPlaying;

        const channelName = item.channel || 'Unknown Channel';
        const safeChannel = this.escapeHtml(channelName);
        const channelInitial = this.escapeHtml((channelName.trim().charAt(0) || '?').toUpperCase());

        const sourceBadge = this.renderSourceBadge(source, item.source_label || null);
        const pendingChip = this.renderPendingImageOverrideChip(item);
        const languageChip = this.renderLanguageChip(item.analysis?.language);
        const summaryTypeChip = this.renderSummaryTypeChip(item.summary_type);
        const nowPlayingPill = isPlaying ? '<div class="summary-card__badge"><span class="summary-pill summary-pill--playing">Now playing</span></div>' : '';
        const pendingChip = this.renderPendingImageOverrideChip(normalizedItem);
        const identityMetaParts = [sourceBadge, languageChip, summaryTypeChip, pendingChip, nowPlayingPill].filter(Boolean);
        const identityMetaClassic = identityMetaParts.length ? `<div class="flex flex-wrap gap-1">${identityMetaParts.join('')}</div>` : '';
        const identityMetaMinimal = (() => {
            const bits = [];
            if (item.source_label || source) bits.push(this.escapeHtml(item.source_label || source));
            if (item.analysis?.language) bits.push(this.escapeHtml(item.analysis.language));
            if (item.summary_type) bits.push(this.escapeHtml(String(item.summary_type).replace(/[-_]/g, ' ')));
            if (!bits.length) return '';
            return `<div class="text-xs text-slate-400">${bits.map((b, i) => i ? `· ${b}` : b).join(' ')}</div>`;
        })();
        const useMinimalMeta = this.flags && this.flags.twMetaMinimal;
        const identityMeta = useMinimalMeta ? identityMetaMinimal : identityMetaClassic;

        const taxonomyMarkup = this.renderCategorySection(item.file_stem, categories, subcatPairs);
        const actionMarkup = this.renderActionBar(item, buttonDurations, hasAudio);
        const totalSecondsAttr = Number.isFinite(totalSecs) ? totalSecs : 0;

        const thumb = item.thumbnail_url
            ? `<img src="${item.thumbnail_url}" alt="" loading="lazy" class="w-40 h-24 rounded-lg object-cover">`
            : `<div class="w-40 h-24 rounded-lg bg-slate-200 dark:bg-slate-700"></div>`;

        return `
            <article data-card data-decorated="true" data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-source="${this.escapeHtml(source)}" data-canonical-url="${this.escapeHtml(item.canonical_url || '')}" data-has-audio="${hasAudio ? 'true' : 'false'}" data-href="${href}" tabindex="0" class="stream-card">
                <div class="stream-card__media">
                    ${nowPlayingPill}
                    ${thumb.replace('w-40 h-24 rounded-lg object-cover', 'stream-card__thumb')}
                    <div class="stream-card__progress" data-card-progress-container data-total-seconds="${totalSecondsAttr}">
                        <div class="stream-card__progress-bar" data-card-progress role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
                    </div>
                    <div class="stream-card__eq hidden" data-card-eq>
                        <div class="summary-card__eq-bars">
                            <span class="waveform-bar" style="--delay:0"></span>
                            <span class="waveform-bar" style="--delay:1"></span>
                            <span class="waveform-bar" style="--delay:2"></span>
                            <span class="waveform-bar" style="--delay:3"></span>
                            <span class="waveform-bar" style="--delay:4"></span>
                        </div>
                    </div>
                </div>
                <div class="stream-card__body">
                    <div class="flex items-start gap-3">
                        <span class="stream-card__avatar">${channelInitial}</span>
                        <div class="min-w-0 flex-1">
                            <button class="text-xs font-medium text-slate-600 dark:text-slate-300 hover:text-audio-600" data-filter-chip="channel" data-filter-value="${safeChannel}" title="Filter by ${safeChannel}">${safeChannel}</button>
                            <div class="stream-card__meta">${identityMeta}</div>
                            <h3 class="stream-card__title line-clamp-2">${this.escapeHtml(item.title)}</h3>
                        </div>
                    </div>
                    <div class="mt-3 space-y-2">
                        ${taxonomyMarkup}
                        ${mediaActions}
                    </div>
                    <section role="region" aria-live="polite" hidden data-expand-region></section>
                </div>
            </article>`;
    }

    // V4 Grid card: mosaic tile
    renderGridCardV4(item) {
        const hasAudio = this.itemHasAudio(item);
        const rawSource = item.content_source || 'youtube';
        const source = rawSource.toLowerCase();
        const href = `/${item.file_stem}.json?v=2`;
        const buttonDurations = this.getButtonDurations(item);
        const { categories, subcatPairs } = this.extractCatsAndSubcats(item);
        const totalSecs = (item.media_metadata && item.media_metadata.mp3_duration_seconds)
            ? item.media_metadata.mp3_duration_seconds
            : (item.duration_seconds || 0);
        const totalSecondsAttr = Number.isFinite(totalSecs) ? totalSecs : 0;

        const title = this.escapeHtml(item.title);
        const thumb = item.thumbnail_url
            ? `<img src="${item.thumbnail_url}" alt="" loading="lazy" class="mosaic-card__thumb">`
            : `<div class="mosaic-card__thumb" style="background: rgba(226,232,240,0.6)"></div>`;

        const actions = this.renderActionBar(item, buttonDurations, hasAudio);
        return `
            <article data-card data-decorated="true" data-report-id="${item.file_stem}" data-source="${this.escapeHtml(source)}" data-has-audio="${hasAudio ? 'true' : 'false'}" data-href="${href}" tabindex="0" class="mosaic-card">
                <div class="mosaic-card__media">
                    ${thumb}
                    <div class="mosaic-card__progress" data-card-progress-container data-total-seconds="${totalSecondsAttr}">
                        <div class="mosaic-card__progress-bar" data-card-progress></div>
                    </div>
                </div>
                <div class="mosaic-card__body space-y-2">
                    <h3 class="mosaic-card__title line-clamp-2">${title}</h3>
                    ${actions}
                </div>
                <section role="region" aria-live="polite" hidden data-expand-region></section>
            </article>`;
    }

    // ---------------------------------------------------------------------
    // V5 (Experimental): Tailwind-first Stream/Mosaic cards
    // These variants keep the same data-* hooks and reuse helpers so behavior
    // matches existing cards while letting us iterate on layout/visuals.
    // Guarded behind UI_FLAGS.twRevamp.
    // ---------------------------------------------------------------------

    // Utility: contiguous rectangular chip bar for V5
    renderChipBarV5(itemId, categories = [], subcatPairs = [], limit = 6) {
        const uniqueCategories = Array.isArray(categories) ? categories.filter(Boolean) : [];
        const structuredPairs = Array.isArray(subcatPairs) ? subcatPairs.filter(([p, s]) => p && s) : [];
        const chips = [];
        // Fill with categories first, then subcategories
        uniqueCategories.forEach((cat) => chips.push({ type: 'category', value: cat }));
        structuredPairs.forEach(([parent, subcat]) => chips.push({ type: 'subcategory', value: subcat, parent }));
        const visible = chips.slice(0, limit);
        const hiddenCount = Math.max(0, chips.length - visible.length);
        const mode = (this.flags && this.flags.twChipsMode) || 'chips';
        if (mode === 'textlist') {
            const textButtons = visible.map(({ type, value, parent }, idx) => {
                const safeValue = this.escapeHtml(value);
                const parentAttr = parent ? ` data-parent-category="${this.escapeHtml(parent)}"` : '';
                const sep = idx > 0 ? '<span class="mx-1 text-slate-500">·</span>' : '';
                return `${sep}<button class="text-xs text-slate-400 hover:text-slate-300 underline-offset-2 hover:underline" data-filter-chip="${type}" data-filter-value="${safeValue}"${parentAttr} title="Filter by ${safeValue}">${safeValue}</button>`;
            }).join('');
            const more = hiddenCount > 0 ? `<span class="mx-1 text-xs text-slate-500">·</span><span class="text-xs text-slate-500">+${hiddenCount} more</span>` : '';
            return `<div class="chip-list-inline flex flex-wrap items-center">${textButtons}${more}</div>`;
        }
        const chipHtml = visible.map(({ type, value, parent }) => {
            const safeValue = this.escapeHtml(value);
            const parentAttr = parent ? ` data-parent-category="${this.escapeHtml(parent)}"` : '';
            return `<button class="px-2 py-1 text-[11px] font-medium border border-slate-300/60 dark:border-slate-700/60 bg-white/70 dark:bg-slate-800/60 text-slate-700 dark:text-slate-200 -ml-px first:ml-0 first:rounded-l-md last:rounded-r-md rounded-none"
                            data-filter-chip="${type}" data-filter-value="${safeValue}"${parentAttr} title="Filter by ${safeValue}">${safeValue}</button>`;
        }).join('');
        const moreHtml = hiddenCount > 0
            ? `<span class="px-2 py-1 text-[11px] font-medium border border-slate-300/60 dark:border-slate-700/60 bg-white/60 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 -ml-px rounded-r-md">+${hiddenCount} more</span>`
            : '';
        return `<div class="inline-flex flex-wrap gap-y-1">${chipHtml}${moreHtml}</div>`;
    }

    // Inline text list for categories/subcategories (no pills), used in header row
    renderCategoryInlineListV5(itemId, categories = [], subcatPairs = [], limit = 6) {
        const uniqueCategories = Array.isArray(categories) ? categories.filter(Boolean) : [];
        const structuredPairs = Array.isArray(subcatPairs) ? subcatPairs.filter(([p, s]) => p && s) : [];
        const chips = [];
        uniqueCategories.forEach((cat) => chips.push({ type: 'category', value: cat }));
        structuredPairs.forEach(([parent, subcat]) => chips.push({ type: 'subcategory', value: subcat, parent }));
        const visible = chips.slice(0, limit);
        const hiddenCount = Math.max(0, chips.length - visible.length);
        const textButtons = visible.map(({ type, value, parent }, idx) => {
            const safeValue = this.escapeHtml(value);
            const parentAttr = parent ? ` data-parent-category=\"${this.escapeHtml(parent)}\"` : '';
            const sep = idx > 0 ? '<span class=\"mx-1 text-slate-500\">·</span>' : '';
            return `${sep}<button class=\"text-xs text-slate-400 hover:text-slate-300 underline-offset-2 hover:underline\" data-filter-chip=\"${type}\" data-filter-value=\"${safeValue}\"${parentAttr} title=\"Filter by ${safeValue}\">${safeValue}</button>`;
        }).join('');
        const more = hiddenCount > 0 ? `<span class=\"mx-1 text-xs text-slate-500\">·</span><span class=\"text-xs text-slate-500\">+${hiddenCount} more</span>` : '';
        return `<span class=\"chip-list-inline flex flex-wrap items-center\">${textButtons}${more}</span>`;
    }

    // Utility: plain-text snippet of summary (for preview)
    getSummarySnippet(item, maxChars = 280) {
        try {
            const html = this.computeFallbackSummaryHtml(item) || '';
            let text = this.stripHtml(html).replace(/\s+/g, ' ').trim();
            text = text.replace(/•/g, '·');
            text = text.replace(/^[\-–•·]\s*/, '');
            if (!text) return '';
            if (text.length <= maxChars) return text;
            return text.slice(0, maxChars).replace(/[,;:\-\s]+\S*$/, '') + '…';
        } catch (_) {
            return '';
        }
    }

    // Utility: strip HTML tags while preserving basic bullets/newlines
    stripHtml(html) {
        let s = String(html || '');
        s = s.replace(/<\s*br\s*\/?>/gi, '\n');
        s = s.replace(/<\s*li[^>]*>/gi, '• ');
        s = s.replace(/<\s*\/li\s*>/gi, '\n');
        s = s.replace(/<[^>]+>/g, ' ');
        return s;
    }

    // V5 List card (Stream): Tailwind-first layout
    renderStreamCardTW(item) {
        const hasAudio = this.itemHasAudio(item);
        const rawSource = item.content_source || 'youtube';
        const source = rawSource.toLowerCase();
        const href = `/${item.file_stem}.json?v=2`;
        const buttonDurations = this.getButtonDurations(item);
        const { categories, subcatPairs } = this.extractCatsAndSubcats(item);
        const totalSecs = (item.media_metadata && item.media_metadata.mp3_duration_seconds)
            ? item.media_metadata.mp3_duration_seconds
            : (item.duration_seconds || 0);
        const totalSecondsAttr = Number.isFinite(totalSecs) ? totalSecs : 0;
        const isPlaying = this.currentAudio && this.currentAudio.id === item.file_stem && this.isPlaying;

        const channelName = item.channel || 'Unknown Channel';
        const safeChannel = this.escapeHtml(channelName);
        const channelInitial = this.escapeHtml((channelName.trim().charAt(0) || '?').toUpperCase());

        const sourceBadge = this.renderSourceBadge(source, item.source_label || null);
        const visibleLimit = (this.flags && this.flags.twChipsVisible) || 6;
        const categoriesInline = this.renderCategoryInlineListV5(item.file_stem, categories, subcatPairs, visibleLimit);
        const watchLinkAvailable = source === 'youtube' ? Boolean(item.video_id) : Boolean(item.canonical_url);
        const mediaActions = this.renderMediaActionsV5(item, buttonDurations, hasAudio, watchLinkAvailable, source);
        const snippet = this.getSummarySnippet(item, 260);
        const nowPlayingBadge = '<span class="summary-pill summary-pill--playing">Now playing</span>';
        const nowPlayingOverlay = isPlaying ? `<div class="summary-card__badge summary-card__badge--media">${nowPlayingBadge}</div>` : '';
        const nowPlayingInline = isPlaying ? `<span class="stream-card__nowplaying-badge">${nowPlayingBadge}</span>` : '';
        const menuMarkup = `
            <button class="summary-card__menu-btn" data-action="menu" aria-label="More options" aria-haspopup="menu" aria-expanded="false">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <circle cx="5" cy="12" r="1.5"></circle>
                    <circle cx="12" cy="12" r="1.5"></circle>
                    <circle cx="19" cy="12" r="1.5"></circle>
                </svg>
            </button>
            <div class="summary-card__menu hidden" data-kebab-menu role="menu" data-report-id="${item.file_stem}">
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="copy-link">Copy link</button>
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="image-new">Create image…</button>
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="reprocess">Reprocess…</button>
                <button type="button" class="summary-card__menu-item summary-card__menu-item--danger" role="menuitem" data-action="delete">Delete…</button>
            </div>
            <div class="summary-card__popover hidden" data-delete-popover>
                <div class="summary-card__popover-panel">
                    <p>Delete this summary?</p>
                    <div class="summary-card__popover-actions">
                        <button type="button" data-action="cancel-delete">Cancel</button>
                        <button type="button" data-action="confirm-delete">Delete</button>
                    </div>
                </div>
            </div>`;

        const hasThumb = Boolean(item.thumbnail_url);
        const summaryImageUrl = item.summary_image_url ? this.normalizeAssetUrl(item.summary_image_url) : '';
        const hasSummaryArt = Boolean(summaryImageUrl);
        let mediaImgs = '';
        let toggleBtn = '';
        if (hasThumb && hasSummaryArt) {
            const thumb = `<img data-role="thumb-default" src="${item.thumbnail_url}" alt="" loading="lazy" class="stream-card__thumb">`;
            const summaryEl = `<img data-role="thumb-summary" src="${summaryImageUrl}" alt="" loading="lazy" class="stream-card__thumb hidden">`;
            mediaImgs = thumb + summaryEl;
            toggleBtn = `<button class="summary-card__toggle" data-action="toggle-image" title="Toggle image" aria-pressed="false" aria-label="Toggle image">🖼️</button>`;
        } else if (!hasThumb && hasSummaryArt) {
            mediaImgs = `<img data-role="thumb-summary" src="${summaryImageUrl}" alt="" loading="lazy" class="stream-card__thumb">`;
        } else if (hasThumb && !hasSummaryArt) {
            mediaImgs = `<img data-role="thumb-default" src="${item.thumbnail_url}" alt="" loading="lazy" class="stream-card__thumb">`;
        } else {
            mediaImgs = `<div class="stream-card__thumb stream-card__thumb--fallback"></div>`;
        }

        const categoriesMarkup = categoriesInline ? `<div class="stream-card__categories">${categoriesInline}</div>` : '';

        return `
            <article data-card data-decorated="true" data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-source="${this.escapeHtml(source)}" data-canonical-url="${this.escapeHtml(item.canonical_url || '')}" data-has-audio="${hasAudio ? 'true' : 'false'}" data-href="${href}" tabindex="0"
                     class="stream-card group">
                <div class="stream-card__media-block">
                    <div class="stream-card__media">
                        ${nowPlayingOverlay}
                        ${toggleBtn}
                        ${mediaImgs}
                        <div class="stream-card__progress" data-card-progress-container data-total-seconds="${totalSecondsAttr}">
                            <div class="stream-card__progress-bar" data-card-progress role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
                        </div>
                    </div>
                    ${mediaActions}
                </div>
                <div class="stream-card__body">
                    <div class="stream-card__header">
                        <div class="stream-card__channel-block">
                            <span class="stream-card__avatar">${channelInitial}</span>
                            <div class="stream-card__channel-stack">
                                <div class="stream-card__channel-line">
                                    <button class="stream-card__channel-name" data-filter-chip="channel" data-filter-value="${safeChannel}" title="Filter by ${safeChannel}">${safeChannel}</button>
                                    ${sourceBadge || ''}
                                    ${pendingChip || ''}
                                    ${nowPlayingInline}
                                </div>
                            </div>
                        </div>
                        <div class="stream-card__header-meta">
                            ${categoriesMarkup}
                            <div class="stream-card__menu">${menuMarkup}</div>
                        </div>
                    </div>
                    <h3 class="stream-card__title line-clamp-2">${this.escapeHtml(item.title)}</h3>
                    ${snippet ? `<p class="stream-card__snippet line-clamp-3" data-summary-snippet>${this.escapeHtml(snippet)}</p>
                    <button type="button" class="stream-card__readmore" data-action="read">Read more</button>` : ''}
                    <section role="region" aria-live="polite" hidden data-expand-region></section>
                </div>
            </article>`;
    }
// V5 Grid card (Mosaic): Tailwind-first tile
    renderGridCardTW(item) {
        const hasAudio = this.itemHasAudio(item);
        const rawSource = item.content_source || 'youtube';
        const source = rawSource.toLowerCase();
        const href = `/${item.file_stem}.json?v=2`;
        const buttonDurations = this.getButtonDurations(item);
        const { categories, subcatPairs } = this.extractCatsAndSubcats(item);
        const totalSecs = (item.media_metadata && item.media_metadata.mp3_duration_seconds)
            ? item.media_metadata.mp3_duration_seconds
            : (item.duration_seconds || 0);
        const totalSecondsAttr = Number.isFinite(totalSecs) ? totalSecs : 0;
        const watchLinkAvailable = source === 'youtube' ? Boolean(item.video_id) : Boolean(item.canonical_url);
        const mediaActions = this.renderMediaActionsV5(item, buttonDurations, hasAudio, watchLinkAvailable, source);

        const title = this.escapeHtml(item.title);
        const hasThumb = Boolean(item.thumbnail_url);
        const summaryImageUrl = item.summary_image_url ? this.normalizeAssetUrl(item.summary_image_url) : '';
        const hasSummaryArt = Boolean(summaryImageUrl);
        let mediaImgs = '';
        let toggleBtn = '';
        if (hasThumb && hasSummaryArt) {
            const thumb = `<img data-role="thumb-default" src="${item.thumbnail_url}" alt="" loading="lazy" class="w-full h-full object-cover rounded-xl">`;
            const summaryEl = `<img data-role="thumb-summary" src="${summaryImageUrl}" alt="" loading="lazy" class="w-full h-full object-cover rounded-xl hidden">`;
            mediaImgs = thumb + summaryEl;
            toggleBtn = `<button class="summary-card__toggle" data-action="toggle-image" title="Toggle image" aria-pressed="false" aria-label="Toggle image">🖼️</button>`;
        } else if (!hasThumb && hasSummaryArt) {
            mediaImgs = `<img data-role="thumb-summary" src="${summaryImageUrl}" alt="" loading="lazy" class="w-full h-full object-cover rounded-xl">`;
        } else if (hasThumb && !hasSummaryArt) {
            mediaImgs = `<img data-role="thumb-default" src="${item.thumbnail_url}" alt="" loading="lazy" class="w-full h-full object-cover rounded-xl">`;
        } else {
            mediaImgs = `<div class="w-full h-full rounded-xl" style="background: rgba(226,232,240,0.6)"></div>`;
        }

        const visibleLimitG = (this.flags && this.flags.twChipsVisible) || 4;
        const chipBar = this.renderChipBarV5(item.file_stem, categories, subcatPairs, visibleLimitG);
        const pendingChip = this.renderPendingImageOverrideChip(item);
        const snippet = this.getSummarySnippet(item, 180);
        return `
            <article data-card data-decorated="true" data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-canonical-url="${this.escapeHtml(item.canonical_url || '')}" data-source="${this.escapeHtml(source)}" data-has-audio="${hasAudio ? 'true' : 'false'}" data-href="${href}" tabindex="0"
                     class="mosaic-card group rounded-2xl border border-slate-200/70 dark:border-slate-800/60 bg-white/80 dark:bg-slate-900/70 backdrop-blur hover:shadow-xl transition-all overflow-hidden">
                <div class="relative w-full h-40">
                    ${toggleBtn}
                    ${mediaImgs}
                    <div class="mosaic-card__progress absolute inset-x-0 bottom-0 h-1.5 bg-white/40 dark:bg-slate-900/40" data-card-progress-container data-total-seconds="${totalSecondsAttr}">
                        <div class="mosaic-card__progress-bar h-full bg-sky-500/90 dark:bg-sky-400/90" data-card-progress></div>
                    </div>
                </div>
                <div class="mosaic-card__content">
                    <div class="mosaic-card__main">
                        ${pendingChip ? `<div class="mb-1">${pendingChip}</div>` : ''}
                        ${chipBar}
                        <h3 class="mosaic-card__title line-clamp-2 text-slate-900 dark:text-slate-100">${title}</h3>
                        <div class="mosaic-card__divider" role="presentation"></div>
                        ${snippet ? `<p class="mosaic-card__snippet text-[13px] text-slate-700 dark:text-slate-300 line-clamp-3">${this.escapeHtml(snippet)}</p>` : '<div class="mosaic-card__snippet mosaic-card__snippet--empty"></div>'}
                        <button type="button" class="mosaic-card__readmore text-[13px] font-semibold text-audio-600 hover:text-audio-700" data-action="read">Read more</button>
                    </div>
                    ${mediaActions ? `<div class="mosaic-card__actions">${mediaActions}</div>` : ''}
                </div>
            </article>`;
    }

    renderWallCardTW(item) {
        const hasAudio = this.itemHasAudio(item);
        const rawSource = item.content_source || 'youtube';
        const source = rawSource.toLowerCase();
        const href = `/${item.file_stem}.json?v=2`;
        const buttonDurations = this.getButtonDurations(item);
        const { categories, subcatPairs } = this.extractCatsAndSubcats(item);
        const watchLinkAvailable = source === 'youtube' ? Boolean(item.video_id) : Boolean(item.canonical_url);
        let mediaActions = this.renderMediaActionsV5(item, buttonDurations, hasAudio, watchLinkAvailable, source);
        // Remove inline reader button in wall mode; clicking the card opens reader
        mediaActions = `<div class="stream-card__media-actions">${mediaActions || ''}</div>`;
        const chipRail = this.renderChipBarV5(item.file_stem, categories, subcatPairs, 3);
        const pendingChip = this.renderPendingImageOverrideChip(item);
        const menuMarkup = `
            <button class="summary-card__menu-btn" data-action="menu" aria-label="More options" aria-haspopup="menu" aria-expanded="false">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <circle cx="5" cy="12" r="1.5"></circle>
                    <circle cx="12" cy="12" r="1.5"></circle>
                    <circle cx="19" cy="12" r="1.5"></circle>
                </svg>
            </button>
            <div class="summary-card__menu hidden" data-kebab-menu role="menu" data-report-id="${item.file_stem}">
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="copy-link">Copy link</button>
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="image-new">Create image…</button>
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="reprocess">Reprocess…</button>
                <button type="button" class="summary-card__menu-item summary-card__menu-item--danger" role="menuitem" data-action="delete">Delete…</button>
            </div>`;
        const title = this.escapeHtml(item.title);
        const hasThumb = Boolean(item.thumbnail_url);
        const summaryImageUrl = item.summary_image_url ? this.normalizeAssetUrl(item.summary_image_url) : '';
        const hasSummaryArt = Boolean(summaryImageUrl);
        let mediaImgs = '';
        let toggleBtn = '';
        if (hasThumb && hasSummaryArt) {
            const thumb = `<img data-role="thumb-default" src="${item.thumbnail_url}" alt="" loading="lazy" class="wall-card__thumb">`;
            const summaryEl = `<img data-role="thumb-summary" src="${summaryImageUrl}" alt="" loading="lazy" class="wall-card__thumb hidden">`;
            mediaImgs = thumb + summaryEl;
            toggleBtn = `<button class="summary-card__toggle" data-action="toggle-image" title="Toggle image" aria-pressed="false" aria-label="Toggle image">🖼️</button>`;
        } else if (!hasThumb && hasSummaryArt) {
            mediaImgs = `<img data-role="thumb-summary" src="${summaryImageUrl}" alt="" loading="lazy" class="wall-card__thumb">`;
        } else if (hasThumb && !hasSummaryArt) {
            mediaImgs = `<img data-role="thumb-default" src="${item.thumbnail_url}" alt="" loading="lazy" class="wall-card__thumb">`;
        } else {
            mediaImgs = `<div class="wall-card__thumb wall-card__thumb--fallback"></div>`;
        }
        return `
            <article data-card data-decorated="true" data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-canonical-url="${this.escapeHtml(item.canonical_url || '')}" data-source="${this.escapeHtml(source)}" data-has-audio="${hasAudio ? 'true' : 'false'}" data-href="${href}" tabindex="0" class="wall-card">
                ${menuMarkup}
                <div class="wall-card__media">${toggleBtn}${mediaImgs}</div>
                <div class="wall-card__overlay">
                    <div class="wall-card__meta">${chipRail || ''}${pendingChip ? `<div class=\"inline-block ml-2\">${pendingChip}</div>` : ''}</div>
                    <h3 class="wall-card__title">${title}</h3>
                    <div class="wall-card__actions">${mediaActions || ''}</div>
                </div>
            </article>`;
    }

    // --- Wall reader handlers ---
    handleWallRead(id, cardEl) {
        const useInline = (this.flags && Object.prototype.hasOwnProperty.call(this.flags, 'wallReadInline')) ? !!this.flags.wallReadInline : true;
        const isDesktop = window.innerWidth >= 1024;
        if (useInline && isDesktop) {
            return this.openWallRowReader(id, cardEl);
        }
        return this.openWallModalReader(id);
    }

    openWallModalReader(id) {
        const modal = document.getElementById('wallReaderModal');
        const body = document.getElementById('wallReaderBody');
        const titleEl = document.getElementById('wallReaderTitle');
        const closeBtn = document.getElementById('wallReaderClose');
        const item = (this.currentItems || []).find(x => x.file_stem === id);
        if (!modal || !body || !item) return;
        titleEl.textContent = item.title || 'Summary';
        body.innerHTML = this.renderWallReaderSection(item);
        // Apply saved reader display preferences
        try { this.applyReaderDisplayPrefs(modal, body); } catch(_) {}
        // Normalize NAS HTML for headings/lists on mobile modal
        try { this.enhanceSummaryHtml(body); } catch (_) {}
        // Inject Display Options (Aa) control
        try {
            const headerRight = modal.querySelector('.mobile-reader-header .flex.items-center.gap-2');
            if (headerRight) {
                const aaBtn = document.createElement('button');
                aaBtn.type = 'button';
                aaBtn.className = 'ybtn ybtn-ghost px-2 py-1.5 rounded-md';
                aaBtn.setAttribute('aria-haspopup', 'dialog');
                aaBtn.setAttribute('aria-expanded', 'false');
                aaBtn.title = 'Display options';
                aaBtn.dataset.action = 'reader-display';
                aaBtn.textContent = 'Aa';
                aaBtn.addEventListener('click', (e) => {
                    e.preventDefault(); e.stopPropagation();
                    this.openReaderDisplayPopover(modal, body, aaBtn);
                });
                headerRight.prepend(aaBtn);
            }
        } catch(_) {}
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        const onClose = () => {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
            closeBtn.removeEventListener('click', onClose);
            modal.removeEventListener('click', onOutside);
            document.removeEventListener('keydown', onEsc);
            this.sendTelemetry('read_close', { id, view: 'wall' });
        };
        const onOutside = (e) => { if (e.target === modal) onClose(); };
        const onEsc = (e) => { if (e.key === 'Escape') onClose(); };
        const onArrowRowInline = (e) => {
            if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
            e.preventDefault();
            const cardsAll = Array.from(grid.querySelectorAll('.wall-card'));
            const i = cardsAll.indexOf(cardEl);
            if (i === -1) return;
            const j = e.key === 'ArrowLeft' ? Math.max(0, i - 1) : Math.min(cardsAll.length - 1, i + 1);
            if (j === i) return;
            const nextCard = cardsAll[j];
            const nextId = nextCard?.getAttribute('data-report-id');
            if (nextId) this.openWallRowReader(nextId, nextCard);
        };
        const onArrow = (e) => {
            if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
            e.preventDefault();
            const grid = this.contentGrid && this.contentGrid.querySelector('.wall-grid');
            const cardsAll = grid ? Array.from(grid.querySelectorAll('.wall-card')) : [];
            const current = this.contentGrid && this.contentGrid.querySelector(`[data-card][data-report-id="${CSS.escape(id)}"]`);
            const i = current ? cardsAll.indexOf(current) : -1;
            if (i === -1) return;
            const j = e.key === 'ArrowLeft' ? Math.max(0, i - 1) : Math.min(cardsAll.length - 1, i + 1);
            const nextCard = cardsAll[j];
            const nextId = nextCard?.getAttribute('data-report-id');
            if (nextId) {
                onClose();
                this.openWallModalReader(nextId);
            }
        };
        closeBtn.addEventListener('click', onClose);
        modal.addEventListener('click', onOutside);
        document.addEventListener('keydown', onEsc);
        document.addEventListener('keydown', onArrow);
        document.addEventListener('keydown', onArrow);
        // Actions: Open, kebab menu
        try {
            const openBtn = modal.querySelector('[data-action="wall-reader-open-page"]');
            const menuBtn = modal.querySelector('[data-action="menu"]');
            const cardEl = this.contentGrid && this.contentGrid.querySelector(`[data-card][data-report-id="${CSS.escape(id)}"]`);
            if (openBtn) {
                openBtn.addEventListener('click', () => {
                    window.location.href = `/${encodeURIComponent(id)}.json?v=2`;
                });
            }
            // Add refresh control for mobile modal
            try {
                const headerRight = modal.querySelector('.mobile-reader-header .flex.items-center.gap-2');
                if (headerRight) {
                    const rbtn = document.createElement('button');
                    rbtn.className = 'ybtn ybtn-ghost px-2 py-1.5 rounded-md';
                    rbtn.setAttribute('title', 'Refresh');
                    rbtn.setAttribute('aria-label', 'Refresh');
                    rbtn.textContent = '↻';
                    rbtn.addEventListener('click', (e) => {
                        e.preventDefault(); e.stopPropagation();
                        // Reload the page in mobile web-app context
                        try { location.reload(); } catch(_) { window.location.href = window.location.href; }
                    });
                    headerRight.insertBefore(rbtn, headerRight.firstChild);
                }
            } catch(_) {}
            if (menuBtn) {
                menuBtn.addEventListener('click', () => this.toggleKebabMenu(modal, true, menuBtn));
                const menu = modal.querySelector('[data-kebab-menu]');
                if (menu) {
                    const onMenuClick = (e) => {
                        const a = e.target.closest('[data-action]');
                        if (!a) return;
                        const act = a.getAttribute('data-action');
                        if (act === 'copy-link') { this.copyLink(cardEl || modal, id); this.toggleKebabMenu(modal, false); }
                        if (act === 'reprocess') { this.openReprocessModal(id, cardEl || modal); this.toggleKebabMenu(modal, false); }
                        if (act === 'delete') { if (cardEl) this.handleDelete(id, cardEl); this.toggleKebabMenu(modal, false); }
                    };
                    menu.addEventListener('click', onMenuClick);
                }
            }
        } catch (_) {}
        this.sendTelemetry('read_open', { id, view: 'wall' });
    }

    openWallRowReader(id, cardEl) {
        const grid = this.contentGrid && this.contentGrid.querySelector('.wall-grid');
        if (!grid || !cardEl) return;
        // Remove any existing expander
        const prev = grid.querySelector('[data-wall-reader]');
        if (prev && prev.getAttribute('data-wall-reader-id') === id) {
            // Toggle: clicking again on same item collapses
            prev.parentElement.removeChild(prev);
            try { cardEl.classList.remove('wall-card--selected'); } catch(_) {}
            // When the inline reader is fully closed, drop the global flag
            try { document.body.classList.remove('wall-reader-open'); } catch(_) {}
            this.sendTelemetry('read_close', { id, view: 'wall', toggled: true });
            return;
        }
        if (prev && prev.parentElement) prev.parentElement.removeChild(prev);
        // Clear previous selection highlight and connector overlay
        grid.querySelectorAll('.wall-card--selected').forEach(el => el.classList.remove('wall-card--selected'));
        try { this.removeWallConnectorOverlay(); } catch(_) {}
        const item = (this.currentItems || []).find(x => x.file_stem === id);
        if (!item) return;
        // Find last card in the clicked row by similar offsetTop
        const cards = Array.from(grid.querySelectorAll('.wall-card'));
        const top = cardEl.offsetTop;
        const rowCards = cards.filter(c => Math.abs(c.offsetTop - top) < 4);
        const anchor = rowCards[rowCards.length - 1] || cardEl;

        const section = document.createElement('section');
        section.className = 'wall-expander';
        section.setAttribute('data-wall-reader', '');
        section.setAttribute('role', 'region');
        section.setAttribute('aria-label', 'Summary');
        section.setAttribute('data-wall-reader-id', id);
        // Prefer AI summary image for the reader header when available
        let imgSrc = '';
        try {
            const preferred = item.summary_image_url ? this.normalizeAssetUrl(item.summary_image_url) : '';
            if (preferred) imgSrc = preferred;
            else if (item.thumbnail_url) imgSrc = item.thumbnail_url;
            else {
                const cardImg = cardEl.querySelector('img');
                imgSrc = (cardImg && cardImg.src) ? cardImg.src : '';
            }
        } catch (_) {
            const cardImg = cardEl.querySelector('img');
            imgSrc = (cardImg && cardImg.src) ? cardImg.src : '';
        }
        section.style.overflow = 'hidden';
        section.style.height = '0px';
        section.innerHTML = `
            <div class="wall-expander__header">
                <div class="flex items-center gap-3">
                    ${imgSrc ? `<img class="wall-expander__thumb" alt="" src="${imgSrc}">` : ''}
                    <h4 class="wall-expander__title">${this.escapeHtml(item.title || 'Summary')}</h4>
                </div>
                <div class="flex items-center gap-2">
                    <button class="ybtn ybtn-ghost px-2 py-1.5 rounded-md" data-action="reader-display" title="Display options" aria-haspopup="dialog" aria-expanded="false">Aa</button>
                    <button class="ybtn ybtn-ghost px-2 py-1.5 rounded-md" data-action="wall-reader-open-page" title="Open page">Open</button>
                    <button class="summary-card__menu-btn" data-action="menu" aria-label="More options" aria-haspopup="menu" aria-expanded="false">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                            <circle cx="5" cy="12" r="1.5"></circle>
                            <circle cx="12" cy="12" r="1.5"></circle>
                            <circle cx="19" cy="12" r="1.5"></circle>
                        </svg>
                    </button>
            <div class="summary-card__menu hidden" data-kebab-menu role="menu" data-report-id="${item.file_stem}">
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="copy-link">Copy link</button>
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="image-new">Create image…</button>
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="reprocess">Reprocess…</button>
                <button type="button" class="summary-card__menu-item summary-card__menu-item--danger" role="menuitem" data-action="delete">Delete…</button>
            </div>
                    <button class="wall-expander__close" aria-label="Close" data-action="wall-reader-close">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                </div>
            </div>
            <div class="prose prose-sm dark:prose-invert max-w-none" data-summary-body>${this.renderWallReaderSection(item)}</div>
        `;
        anchor.insertAdjacentElement('afterend', section);
        // Animate open height
        requestAnimationFrame(() => {
            const full = section.scrollHeight;
            section.style.transition = 'height 200ms ease';
            section.style.height = full + 'px';
            const onEnd = () => {
                section.style.height = 'auto';
                section.style.overflow = '';
                section.removeEventListener('transitionend', onEnd);
            };
            section.addEventListener('transitionend', onEnd);
        });
        // Enhance injected HTML formatting for headings/lists
        try {
            const body = section.querySelector('[data-summary-body]');
            this.enhanceSummaryHtml(body);
            // Apply saved reader display preferences to inline reader
            this.applyReaderDisplayPrefs(section, body);
        } catch (_) {}
        // Highlight the source card and set caret position (relative to expander)
        try {
            cardEl.classList.add('wall-card--selected');
            // Signal that a wall reader is open to adjust hover styling
            document.body.classList.add('wall-reader-open');
            // Compute after insertion so positions are accurate
            const cardRect = cardEl.getBoundingClientRect();
            const secRect = section.getBoundingClientRect();
            let caretLeft = (cardRect.left - secRect.left) + (cardRect.width / 2);
            // Clamp caret within expander width
            caretLeft = Math.max(16, Math.min(caretLeft, secRect.width - 16));
            section.style.setProperty('--caret-left', caretLeft + 'px');
            const caretPct = Math.max(0, Math.min(100, (caretLeft / Math.max(1, secRect.width)) * 100));
            section.style.setProperty('--caret-left-pct', caretPct + '%');
            // Card-side connector X (percentage of card width). Currently centered.
            cardEl.style.setProperty('--connector-x-pct', '50%');
            // Draw/update connector overlay (curved link + subtle glow)
            this.updateWallConnectorOverlay(cardEl, section, caretLeft);
            // Recompute once after layout settles (fonts/images)
            try { setTimeout(() => this.updateWallConnectorOverlay(cardEl, section, caretLeft), 150); } catch(_) {}
            // Keep overlay aligned on scroll/resize until closed
            const boundUpdate = () => this.updateWallConnectorOverlay(cardEl, section);
            this._wallConnectorHandlers = this._wallConnectorHandlers || [];
            this._wallConnectorHandlers.forEach(h => window.removeEventListener(h.type, h.fn, h.opts));
            this._wallConnectorHandlers = [
                { type: 'resize', fn: boundUpdate, opts: { passive: true } },
                { type: 'scroll', fn: boundUpdate, opts: { passive: true } }
            ];
            this._wallConnectorHandlers.forEach(h => window.addEventListener(h.type, h.fn, h.opts));
        } catch(_) {}
        const closeBtn = section.querySelector('[data-action="wall-reader-close"]');
        const displayBtn = section.querySelector('[data-action="reader-display"]');
        const openBtn = section.querySelector('[data-action="wall-reader-open-page"]');
        const menuBtn = section.querySelector('[data-action="menu"]');
        // Inject a refresh button into header actions
        try {
            const actions = section.querySelector('.wall-expander__header .flex.items-center.gap-2');
            if (actions) {
                const rbtn = document.createElement('button');
                rbtn.className = 'ybtn ybtn-ghost px-2 py-1.5 rounded-md';
                rbtn.setAttribute('title', 'Refresh');
                rbtn.setAttribute('aria-label', 'Refresh');
                rbtn.textContent = '↻';
                rbtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); this.openWallRowReader(id, cardEl); });
                actions.insertBefore(rbtn, actions.firstChild);
            }
        } catch(_) {}
        const onClose = () => {
            if (!section || !section.parentElement) return;
            // Animate collapse
            section.style.overflow = 'hidden';
            const full = section.scrollHeight;
            section.style.height = full + 'px';
            requestAnimationFrame(() => {
                section.style.transition = 'height 160ms ease';
                section.style.height = '0px';
            });
            const finalize = () => {
                if (section && section.parentElement) section.parentElement.removeChild(section);
                section.removeEventListener('transitionend', finalize);
                try { document.body.classList.remove('wall-reader-open'); } catch(_) {}
                try { this.removeWallConnectorOverlay(); } catch(_) {}
                if (this._wallConnectorHandlers) {
                    this._wallConnectorHandlers.forEach(h => window.removeEventListener(h.type, h.fn, h.opts));
                    this._wallConnectorHandlers = [];
                }
            };
            section.addEventListener('transitionend', finalize);
            document.removeEventListener('keydown', onEsc);
            document.removeEventListener('keydown', onArrow);
            this.sendTelemetry('read_close', { id, view: 'wall' });
            try { cardEl.classList.remove('wall-card--selected'); } catch(_) {}
        };
        const onEsc = (e) => { if (e.key === 'Escape') onClose(); };
        const onArrow = (e) => {
            if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
            e.preventDefault();
            const cardsAll = Array.from(grid.querySelectorAll('.wall-card'));
            const i = cardsAll.indexOf(cardEl);
            if (i === -1) return;
            const j = e.key === 'ArrowLeft' ? Math.max(0, i - 1) : Math.min(cardsAll.length - 1, i + 1);
            if (j === i) return;
            const nextCard = cardsAll[j];
            const nextId = nextCard?.getAttribute('data-report-id');
            if (nextId) { onClose(); this.openWallRowReader(nextId, nextCard); }
        };
        if (closeBtn) closeBtn.addEventListener('click', onClose);
        if (displayBtn) {
            const bodyEl = section.querySelector('[data-summary-body]');
            displayBtn.addEventListener('click', (e) => {
                e.preventDefault(); e.stopPropagation();
                this.openReaderDisplayPopover(section, bodyEl, displayBtn);
            });
        }
        if (openBtn) openBtn.addEventListener('click', () => {
            window.location.href = `/${encodeURIComponent(id)}.json?v=2`;
        });
        // Copy link is available via kebab menu only
        if (menuBtn) {
            menuBtn.addEventListener('click', () => this.toggleKebabMenu(section, true, menuBtn));
            const menu = section.querySelector('[data-kebab-menu]');
            if (menu) {
                const onMenuClick = (e) => {
                    const a = e.target.closest('[data-action]');
                    if (!a) return;
                    const act = a.getAttribute('data-action');
                    if (act === 'copy-link') { this.copyLink(cardEl, id); this.toggleKebabMenu(section, false); }
                    if (act === 'reprocess') { this.openReprocessModal(id, cardEl); this.toggleKebabMenu(section, false); }
                    if (act === 'delete') { this.handleDelete(id, cardEl); this.toggleKebabMenu(section, false); }
                };
                menu.addEventListener('click', onMenuClick);
            }
        }
        document.addEventListener('keydown', onEsc);
        document.addEventListener('keydown', onArrow);
        document.addEventListener('keydown', onArrow);
        // Scroll with header offset so the source card stays in view (row context retained)
        const header = document.querySelector('header');
        const headerH = header ? header.getBoundingClientRect().height : 64;
        const targetTop = cardEl.getBoundingClientRect().top + window.pageYOffset - headerH - 16;
        window.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' });
        this.sendTelemetry('read_open', { id, view: 'wall' });
    }

    // --- Connector overlay helpers (wall mode) ---
    ensureWallConnectorOverlay() {
        if (this._wallConnector) return this._wallConnector;
        const el = document.createElement('div');
        el.className = 'wall-connector-overlay';
        el.setAttribute('data-wall-connector', '');
        el.innerHTML = `<svg class="wall-connector-svg" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" aria-hidden="true" focusable="false"><path class="wall-connector-path" d=""/></svg>`;
        document.body.appendChild(el);
        this._wallConnector = el;
        return el;
    }
    removeWallConnectorOverlay() {
        if (this._wallConnector && this._wallConnector.parentElement) {
            this._wallConnector.parentElement.removeChild(this._wallConnector);
        }
        this._wallConnector = null;
    }
    updateWallConnectorOverlay(cardEl, sectionEl, caretLeftPx) {
        try {
            const overlay = this.ensureWallConnectorOverlay();
            const svg = overlay.querySelector('svg');
            const path = overlay.querySelector('path');
            if (!svg || !path) return;

            const cardRect = cardEl.getBoundingClientRect();
            const secRect = sectionEl.getBoundingClientRect();
            const caretLeft = (typeof caretLeftPx === 'number' && !Number.isNaN(caretLeftPx))
                ? caretLeftPx
                : (Math.max(16, Math.min((cardRect.left - secRect.left) + (cardRect.width / 2), secRect.width - 16)));

            const startX = Math.round(cardRect.left + (cardRect.width / 2));
            const startY = Math.round(cardRect.bottom - 2);
            const endX = Math.round(secRect.left + caretLeft);
            const endY = Math.round(secRect.top + 2);

            // Smooth cubic curve; control points halfway vertically with slight horizontal bias
            const midY = Math.round((startY + endY) / 2);
            const c1x = startX, c1y = midY;
            const c2x = endX,   c2y = midY;

            const d = `M ${startX} ${startY} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${endX} ${endY}`;
            path.setAttribute('d', d);
        } catch (_) { /* no-op */ }
    }

    // Normalize NAS HTML variants at render time to ensure headings/lists styles apply
    enhanceSummaryHtml(root) {
        if (!root) return;
        try {
            const paras = Array.from(root.querySelectorAll('p'));
            paras.forEach((p) => {
                const text = (p.textContent || '').trim();
                const next = p.nextElementSibling;
                // Promote a standalone line followed by a bullet list to a heading
                if (next && next.tagName === 'UL' && next.classList.contains('kp-list') && text && text.length <= 120) {
                    const h = document.createElement('h3');
                    h.className = 'kp-heading';
                    h.textContent = text;
                    p.replaceWith(h);
                    return;
                }
                // Emphasize Bottom line: ...
                const m = text.match(/^\s*(Bottom\s*-?\s*line)\s*:\s*(.*)$/i);
                if (m) {
                    const strong = document.createElement('strong');
                    strong.textContent = `${m[1]}:`;
                    p.classList.add('kp-takeaway');
                    p.innerHTML = '';
                    p.appendChild(strong);
                    if (m[2]) {
                        p.appendChild(document.createTextNode(' ' + m[2]));
                    }
                }
            });
            // Ensure list class is present
            Array.from(root.querySelectorAll('ul')).forEach((ul) => {
                if (!ul.classList.contains('kp-list')) {
                    // If it looks like a bullet list, add class for consistent styling
                    const firstLi = ul.querySelector('li');
                    if (firstLi) ul.classList.add('kp-list');
                }
            });
        } catch (_) { /* no-op */ }
    }

    renderWallReaderSection(item) {
        // Prefer summary_html; fallback to formatted key-points or plain text
        const html = item.summary_html || this.computeFallbackSummaryHtml(item) || '';
        return html;
    }

    renderSummaryCard(normalizedItem, { view = 'list' } = {}) {
        const hasAudio = this.itemHasAudio(normalizedItem);
        const rawSource = normalizedItem.content_source || 'youtube';
        const source = rawSource.toLowerCase();
        const hasWatchLink = source === 'youtube' ? Boolean(normalizedItem.video_id) : Boolean(normalizedItem.canonical_url);
        const href = `/${normalizedItem.file_stem}.json?v=2`;
        const buttonDurations = this.getButtonDurations(normalizedItem);
        const { categories, subcatPairs } = this.extractCatsAndSubcats(normalizedItem);
        const totalSecs = (normalizedItem.media_metadata && normalizedItem.media_metadata.mp3_duration_seconds)
            ? normalizedItem.media_metadata.mp3_duration_seconds
            : (normalizedItem.duration_seconds || 0);
        const isPlaying = this.currentAudio && this.currentAudio.id === normalizedItem.file_stem && this.isPlaying;

        const channelName = normalizedItem.channel || 'Unknown Channel';
        const safeChannel = this.escapeHtml(channelName);
        const channelInitial = this.escapeHtml((channelName.trim().charAt(0) || '?').toUpperCase());

        const cardClasses = ['summary-card', view === 'grid' ? 'summary-card--grid' : 'summary-card--list', 'cursor-pointer'];
        if (view !== 'grid') cardClasses.push('list-layout');
        if (isPlaying) cardClasses.push('is-playing');

        const styleAttr = view === 'grid' ? '' : ' style="--thumbW: 240px;"';
        const sourceBadge = this.renderSourceBadge(normalizedItem.content_source || 'youtube', normalizedItem.source_label || null);
        const languageChip = this.renderLanguageChip(normalizedItem.analysis?.language);
        // Show 'Audio (missing)' chip when type says audio but file is absent
        const summaryTypeValue = (normalizedItem.summary_type === 'audio' && !hasAudio) ? 'audio-missing' : normalizedItem.summary_type;
        const summaryTypeChip = this.renderSummaryTypeChip(summaryTypeValue);
        const nowPlayingPill = isPlaying ? '<div class="summary-card__badge"><span class="summary-pill summary-pill--playing">Now playing</span></div>' : '';
        const identityMetaParts = [sourceBadge, languageChip, summaryTypeChip, nowPlayingPill].filter(Boolean);
        const identityMeta = identityMetaParts.length ? `<div class="summary-card__meta">${identityMetaParts.join('')}</div>` : '';

        const taxonomyMarkup = this.renderCategorySection(normalizedItem.file_stem, categories, subcatPairs);
        const consumptionMarkup = this.renderConsumptionSummary(buttonDurations, hasAudio, source, hasWatchLink);
        // Media: default thumbnail plus optional AI summary image
        const summaryImageUrl = normalizedItem.summary_image_url ? this.normalizeAssetUrl(normalizedItem.summary_image_url) : '';
        const hasSummaryArt = Boolean(summaryImageUrl);
        const thumbnailEl = normalizedItem.thumbnail_url
            ? `<img data-role="thumb-default" src="${normalizedItem.thumbnail_url}" alt="" loading="lazy">`
            : '';
        const summaryEl = hasSummaryArt
            ? `<img data-role="thumb-summary" src="${summaryImageUrl}" alt="" loading="lazy" class="hidden">`
            : '';
        const toggleBtn = hasSummaryArt
            ? `<button class="summary-card__toggle" data-action="toggle-image" title="Toggle image" aria-pressed="false" aria-label="Toggle image">🖼️</button>`
            : '';

        const totalSecondsAttr = Number.isFinite(totalSecs) ? totalSecs : 0;
        const menuMarkup = `
                        <button class="summary-card__menu-btn" data-action="menu" aria-label="More options" aria-haspopup="menu" aria-expanded="false">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                <circle cx="5" cy="12" r="1.5"></circle>
                                <circle cx="12" cy="12" r="1.5"></circle>
                                <circle cx="19" cy="12" r="1.5"></circle>
                            </svg>
                        </button>
            <div class="summary-card__menu hidden" data-kebab-menu role="menu">
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="copy-link">Copy link</button>
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="image-new">Create image…</button>
                <button type="button" class="summary-card__menu-item" role="menuitem" data-action="reprocess">Reprocess…</button>
                <button type="button" class="summary-card__menu-item summary-card__menu-item--danger" role="menuitem" data-action="delete">Delete…</button>
            </div>
                        <div class="summary-card__popover hidden" data-delete-popover>
                            <div class="summary-card__popover-panel">
                                <p>Delete this summary?</p>
                                <div class="summary-card__popover-actions">
                                    <button type="button" data-action="cancel-delete">Cancel</button>
                                    <button type="button" data-action="confirm-delete">Delete</button>
                                </div>
                            </div>
                        </div>`;
        const mediaMenuMarkup = view === 'grid' ? menuMarkup : '';
        const outerMenuMarkup = view === 'grid' ? '' : menuMarkup;

        return `
            <div data-card data-decorated="true" data-report-id="${normalizedItem.file_stem}" data-video-id="${normalizedItem.video_id || ''}" data-source="${this.escapeHtml(source)}" data-canonical-url="${this.escapeHtml(normalizedItem.canonical_url || '')}" data-has-audio="${hasAudio ? 'true' : 'false'}" data-href="${href}" title="Open summary" tabindex="0" class="${cardClasses.join(' ')}"${styleAttr}>
                <div class="summary-card__inner">
                    ${outerMenuMarkup}
                    <div class="summary-card__media">
                        ${nowPlayingPill}
                        ${toggleBtn}
                        ${thumbnailEl}${summaryEl}
                        <div class="summary-card__eq ${isPlaying ? '' : 'hidden'}" data-card-eq>
                            <div class="summary-card__eq-bars">
                                <span class="waveform-bar" style="--delay:0"></span>
                                <span class="waveform-bar" style="--delay:1"></span>
                                <span class="waveform-bar" style="--delay:2"></span>
                                <span class="waveform-bar" style="--delay:3"></span>
                                <span class="waveform-bar" style="--delay:4"></span>
                            </div>
                        </div>
                        ${mediaMenuMarkup}
                        <div class="summary-card__progress" data-card-progress-container data-total-seconds="${totalSecondsAttr}">
                            <div class="summary-card__progress-bar" data-card-progress role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
                        </div>
                    </div>
                    <div class="summary-card__body">
                        <div class="summary-card__identity">
                            <span class="summary-card__avatar">${channelInitial}</span>
                            <div class="summary-card__identity-text">
                                <button class="summary-card__channel" data-filter-chip="channel" data-filter-value="${safeChannel}" title="Filter by ${safeChannel}">${safeChannel}</button>
                                ${identityMeta}
                            </div>
                        </div>
                        <h3 class="summary-card__title">${this.escapeHtml(normalizedItem.title)}</h3>
                        ${taxonomyMarkup}
                        ${consumptionMarkup}
                        <div class="summary-card__footer">
                            ${this.renderActionBar(normalizedItem, buttonDurations, hasAudio)}
                        </div>
                        <section role="region" aria-live="polite" hidden data-expand-region></section>
                    </div>
                </div>
            </div>`;
    }

    renderConsumptionSummary(durations = {}, hasAudio = false, source = 'youtube', hasWatchLink = false) {
        const segments = [];
        if (durations.read) {
            segments.push({ text: `Read ${durations.read}` });
        }
        // Only show Listen when audio truly exists; otherwise omit
        if (hasAudio) {
            segments.push({ text: durations.listen ? `Listen ${durations.listen}` : 'Listen ready' });
        }
        const watchLabel = source === 'youtube' ? 'Watch' : 'Open';
        if (durations.watch) {
            segments.push({ text: `${watchLabel} ${durations.watch}` });
        } else if (hasWatchLink) {
            segments.push({ text: `${watchLabel} ready` });
        }

        if (!segments.length) return '';

        const items = segments.map((segment) => {
            const classes = ['summary-card__consumption-item'];
            if (segment.muted) classes.push('summary-card__consumption-item--muted');
            return `<span class="${classes.join(' ')}">${this.escapeHtml(segment.text)}</span>`;
        }).join('');

        return `<div class="summary-card__consumption">${items}</div>`;
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

        if (categoryFilters.length > 0 && categoryFilters.length < allCategories.length) {
            categoryFilters.forEach(val =>
                sections.push({
                    type: 'category',
                    label: 'Category',
                    value: val
                })
            );
        }

        const sourceFilters = this.currentFilters?.source || [];
        const allSources = Array.from(document.querySelectorAll('input[data-filter="source"]')).map(el => el.value);
        if (sourceFilters.length > 0 && sourceFilters.length < allSources.length) {
            sourceFilters.forEach(val => {
                sections.push({
                    type: 'source',
                    label: 'Source',
                    value: val,
                    display: this.prettySourceLabel(val)
                });
            });
        }

        // Create horizontal scrolling container for chips
        if (sections.length > 0) {
            heroBadges.innerHTML = `
                <div class="flex overflow-x-auto pb-2 space-x-2 scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-600 scrollbar-track-transparent"
                     style="max-height: 80px; scrollbar-width: thin;">
                    ${sections.map(({ type, label, value, display }) => `
                        <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/40 dark:border-white/10 bg-white/70 dark:bg-white/5 text-slate-600 dark:text-slate-200 whitespace-nowrap flex-shrink-0">
                            <span class="uppercase tracking-wide text-[10px] text-slate-400 dark:text-slate-500">${this.escapeHtml(String(label))}</span>
                            <span class="text-[11px] font-medium">${this.escapeHtml(String(display ?? value))}</span>
                            <button class="ml-1 hover:bg-slate-200 dark:hover:bg-slate-600 rounded-full p-0.5 transition-colors"
                                    data-remove-filter="${this.escapeHtml(String(type))}"
                                    data-filter-value="${this.escapeHtml(String(value))}"
                                    title="Remove filter">
                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                                </svg>
                            </button>
                        </span>
                    `).join('')}
                    <button class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/40 dark:border-white/10 bg-white/70 dark:bg-white/5 text-slate-600 dark:text-slate-200 whitespace-nowrap flex-shrink-0"
                            data-clear-all="1" title="Clear all filters">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                        <span class="text-[11px] font-medium">Clear all</span>
                    </button>
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

        const clearAllBtn = heroBadges.querySelector('[data-clear-all]');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.clearAllFilters();
            });
        }

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
            const categoryInput = document.querySelector(`input[data-filter="category"][value="${filterValue}"]`);
            if (categoryInput) categoryInput.checked = false;
        } else if (filterType === 'source') {
            const sourceInput = document.querySelector(`input[data-filter="source"][value="${filterValue}"]`);
            if (sourceInput) sourceInput.checked = false;
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
        if (this.viewMode === 'wall') {
            this.pagination.innerHTML = '';
            return;
        }
        const totalPages = pagination.pages ?? pagination.total_pages ?? 1;
        const currentPage = pagination.page ?? 1;

        if (totalPages <= 1) {
            this.pagination.innerHTML = '';
            return;
        }

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

        const wallMode = this.viewMode === 'wall';
        const currentPage = pagination.page ?? 1;
        const totalPages = pagination.pages ?? pagination.total_pages ?? 1;
        const totalCountForDisplay = pagination.total ?? pagination.total_count ?? this.currentItems.length;

        // Create navigation arrows with the pagination text
        const canGoBack = !wallMode && currentPage > 1;
        const canGoForward = !wallMode && currentPage < totalPages;

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

        if (wallMode) {
            this.resultsCount.textContent = `${totalCountForDisplay} summaries available`;
        } else {
            this.resultsCount.innerHTML =
                `${leftArrow}${totalCountForDisplay} summaries found • Page ${currentPage} of ${totalPages}${rightArrow}`;

            // Add click handlers for navigation arrows
            this.resultsCount.querySelectorAll('[data-nav]').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const direction = e.currentTarget.dataset.nav;
                    if (direction === 'prev' && currentPage > 1) {
                        this.currentPage = currentPage - 1;
                        this.loadContent();
                    } else if (direction === 'next' && currentPage < totalPages) {
                        this.currentPage = currentPage + 1;
                        this.loadContent();
                    }
                });
            });
        }

        this.updateHeroBadges();
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
        if (!this.currentAudio) return;
        const src = this.audioElement.currentSrc || this.audioElement.src || '';
        const id = this.currentAudio.id;
        // One-shot fallback from by_video to /exports/<id>.mp3
        if (src.includes('/exports/by_video/') && id) {
            const fallback = `/exports/${id}.mp3`;
            this.audioElement.src = fallback;
            this.audioElement.load();
            this.refreshAudioVariantBlocks();
            return;
        }
        // Reddit legacy fallback: /exports/audio/reddit<id>.mp3
        if (id && !src.includes(`/exports/audio/reddit${id}.mp3`)) {
            const redditLegacy = `/exports/audio/reddit${id}.mp3`;
            this.audioElement.src = redditLegacy;
            this.audioElement.load();
            this.refreshAudioVariantBlocks();
            return;
        }
        // If we’re already on fallback (or no valid src), mark as unavailable and clean up UI
        try {
            const card = document.querySelector(`[data-report-id="${id}"]`);
            if (card) {
                card.setAttribute('data-has-audio', 'false');
                // Remove Listen buttons
                card.querySelectorAll('[data-listen-button]').forEach(el => el.remove());
                // Remove Listen segment
                card.querySelectorAll('.summary-card__consumption .summary-card__consumption-item').forEach(span => {
                    const t = (span.textContent || '').trim();
                    if (/^Listen\b/i.test(t)) span.remove();
                });
            }
        } catch (_) {}
        this.showToast('Audio not available for this summary', 'warn');
        // Reset current track
        this.isPlaying = false;
        this.currentAudio = null;
        this.resetAudioElement();
        this.updatePlayButton();
        this.updatePlayingCard();
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
        this.refreshAudioVariantBlocks();
    }

    handleCanPlay() {
        if (this.currentAudio && !this.isPlaying && this.userInitiatedPlay) {
            this.audioElement.play().then(() => {
                this.isPlaying = true;
                this.updatePlayButton();
                this.updatePlayingCard();
                this.refreshAudioVariantBlocks();
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
        document.body.classList.toggle('has-current-audio', hasTrack);
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
        // Update top mini-player play button
        if (this.topPlayIcon && this.topPauseIcon) {
            if (this.isPlaying) {
                this.topPlayIcon.classList.add('hidden');
                this.topPauseIcon.classList.remove('hidden');
            } else {
                this.topPlayIcon.classList.remove('hidden');
                this.topPauseIcon.classList.add('hidden');
            }
        }
        // Enable/disable top prev/next based on playlist
        if (this.topPrevBtn) {
            const enablePrev = !!this.currentAudio && Array.isArray(this.playlist) && this.playlist.length > 1;
            this.topPrevBtn.disabled = !enablePrev;
            this.topPrevBtn.classList.toggle('opacity-60', !enablePrev);
            this.topPrevBtn.classList.toggle('cursor-not-allowed', !enablePrev);
        }
        if (this.topNextBtn) {
            const enableNext = !!this.currentAudio && Array.isArray(this.playlist) && this.playlist.length > 1;
            this.topNextBtn.disabled = !enableNext;
            this.topNextBtn.classList.toggle('opacity-60', !enableNext);
            this.topNextBtn.classList.toggle('cursor-not-allowed', !enableNext);
        }

        // Show/hide top mini-player when sidebar collapsed (desktop)
        if (this.topMiniPlayer) {
            const collapsed = document.body.classList.contains('sidebar-collapsed');
            if (collapsed && this.currentAudio) {
                this.topMiniPlayer.classList.remove('hidden');
            } else {
                this.topMiniPlayer.classList.add('hidden');
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

        this.refreshAudioVariantBlocks();
    }

    setViewMode(mode) {
        const previousMode = this.viewMode;
        this.viewMode = mode;
        localStorage.setItem('ytv2.viewMode', mode);
        if (mode === 'wall') {
            this._previousSidebarCollapsed = this.sidebarCollapsed;
            this._previousPageBeforeWall = this.currentPage;
            this.currentPage = 1;
            if (!this.sidebarCollapsed && this.desktopMediaQuery?.matches) {
                this.sidebarCollapsed = true;
                localStorage.setItem('ytv2.sidebarCollapsed', '1');
                this.applySidebarCollapsedState();
            }
        } else {
            if (previousMode === 'wall' && typeof this._previousPageBeforeWall === 'number') {
                this.currentPage = this._previousPageBeforeWall;
                this._previousPageBeforeWall = undefined;
            }
            if (typeof this._previousSidebarCollapsed === 'boolean') {
                const shouldRestore = this._previousSidebarCollapsed;
                this._previousSidebarCollapsed = undefined;
                this.sidebarCollapsed = shouldRestore;
                localStorage.setItem('ytv2.sidebarCollapsed', shouldRestore ? '1' : '0');
                this.applySidebarCollapsedState();
            }
        }
        // Re-render current items
        this.updateViewToggle();
        if (this.currentItems && this.currentItems.length) {
            this.renderContent(this.currentItems);
        }
        this.loadContent();
    }

    updateViewToggle() {
        const buttons = [
            this.listViewBtn,
            this.gridViewBtn,
            this.wallViewBtn,
            this.listViewBtnMobile,
            this.gridViewBtnMobile,
            this.wallViewBtnMobile
        ].filter(Boolean);
        if (!buttons.length) return;

        const activeClasses = ['bg-audio-600', 'text-white', 'shadow-lg'];
        const inactiveClasses = ['bg-white/80', 'dark:bg-slate-900/70', 'text-slate-600', 'dark:text-slate-200', 'border', 'border-white/60', 'dark:border-slate-700/70', 'shadow-sm'];

        buttons.forEach(btn => {
            btn.classList.remove(...activeClasses, ...inactiveClasses);
            btn.classList.add(...inactiveClasses);
        });

        const map = {
            list: [this.listViewBtn, this.listViewBtnMobile],
            grid: [this.gridViewBtn, this.gridViewBtnMobile],
            wall: [this.wallViewBtn, this.wallViewBtnMobile]
        };
        const desired = (map[this.viewMode] || []).filter(Boolean);
        const fallback = (map.list || []).filter(Boolean);
        const targets = desired.length ? desired : (fallback.length ? fallback : [buttons[0]]);
        targets.forEach(btn => {
            btn.classList.remove(...inactiveClasses);
            btn.classList.add(...activeClasses);
        });

        document.body.classList.toggle('wall-mode', this.viewMode === 'wall');
        if (this.resultsHero) {
            this.resultsHero.classList.toggle('hidden', this.viewMode === 'wall');
        }

        this.updateHeroBadges();
    }

    applySidebarCollapsedState() {
        const isDesktop = this.desktopMediaQuery ? this.desktopMediaQuery.matches : window.innerWidth >= 1024;
        const shouldCollapse = Boolean(this.sidebarCollapsed && isDesktop);
        document.body.classList.toggle('sidebar-collapsed', shouldCollapse);
        if (this.sidebarElement) {
            this.sidebarElement.setAttribute('aria-hidden', shouldCollapse ? 'true' : 'false');
        }
        if (this.sidebarCollapseToggle) {
            this.sidebarCollapseToggle.setAttribute('aria-pressed', shouldCollapse ? 'true' : 'false');
        }
        if (this.sidebarExpandToggle) {
            this.sidebarExpandToggle.setAttribute('aria-hidden', shouldCollapse ? 'false' : 'true');
        }
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
        document.body.classList.add('has-current-audio');

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
            if (typeof btn.classList?.toggle === 'function') {
                btn.classList.toggle('is-active', isPlayingActive);
            }
            if (playIcon && pauseIcon) {
                if (isPlayingActive) {
                    playIcon.classList.add('hidden');
                    pauseIcon.classList.remove('hidden');
                } else {
                    playIcon.classList.remove('hidden');
                    pauseIcon.classList.add('hidden');
                }
            }

            btn.classList.toggle('variant-toggle--playing', isActive);
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
            if (this.topProgressBar) {
                this.topProgressBar.style.width = `${progress}%`;
            }
            if (this.topNowPlayingTitle && this.currentAudio) {
                this.topNowPlayingTitle.textContent = this.currentAudio.title;
            }
            
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

        this.refreshAudioVariantBlocks();
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
        const code = String(lang || '').toUpperCase();
        const label = flag ? `${flag} ${code}` : code;
        return `<span class="summary-pill summary-pill--lang">${this.escapeHtml(label)}</span>`;
    }

    inferSource(item = {}) {
        const raw = (item.content_source ?? item.source ?? '').toString().trim();
        const canonicalUrl = (item.canonical_url ?? item.url ?? '').toString().trim().toLowerCase();
        const videoIdRaw = item.video_id ?? '';
        const videoId = videoIdRaw != null ? videoIdRaw.toString().trim().toLowerCase() : '';
        const recordId = (item.id ?? '').toString().trim().toLowerCase();

        const normalized = raw.toLowerCase();
        const known = new Set(['youtube', 'reddit', 'wikipedia', 'lds', 'web', 'other']);
        let slug = normalized && known.has(normalized) ? normalized : '';

        const hasCanonical = (needle) => canonicalUrl.includes(needle);

        if (!slug) {
            if (hasCanonical('wikipedia.org')) slug = 'wikipedia';
            else if (hasCanonical('churchofjesuschrist.org') || hasCanonical('lds.org')) slug = 'lds';
            else if (hasCanonical('reddit.com')) slug = 'reddit';
            else if (hasCanonical('youtube.com') || hasCanonical('youtu.be')) slug = 'youtube';
        }

        if (!slug) {
            if (videoId.startsWith('reddit:') || recordId.startsWith('reddit:')) slug = 'reddit';
            else if (/^[a-z0-9_-]{11}$/i.test(videoId)) slug = 'youtube';
        }

        if (!slug && !canonicalUrl && !videoId) {
            slug = normalized || 'other';
        }

        if (!slug) slug = 'web';

        const label = raw || this.prettySourceLabel(slug);
        return { slug, label };
    }

    renderSourceBadge(source, displayLabel = null) {
        const slug = (source || 'youtube').toLowerCase();
        const map = {
            'youtube': { label: 'YouTube', icon: '▶️', value: 'youtube' },
            'reddit': { label: 'Reddit', icon: '🧵', value: 'reddit' },
            'wikipedia': { label: 'Wikipedia', icon: '📚', value: 'wikipedia' },
            'lds': { label: 'Gospel Library', icon: '🙏', value: 'lds' },
            'web': { label: 'Web', icon: '🌐', value: 'web' },
            'other': { label: 'Other', icon: '🔗', value: 'other' }
        };
        const entry = map[slug] || { label: displayLabel || this.prettySourceLabel(source), icon: '🔗', value: slug || 'other' };
        const label = `${entry.icon} ${entry.label}`;
        return `<span class="summary-pill summary-pill--source" data-filter-chip="source" data-filter-value="${this.escapeHtml(entry.value)}" title="Filter by ${this.escapeHtml(entry.label)}">${this.escapeHtml(label)}</span>`;
    }

    prettySourceLabel(source) {
        const slug = (source || '').toLowerCase();
        if (slug === 'youtube') return 'YouTube';
        if (slug === 'reddit') return 'Reddit';
        if (slug === 'wikipedia') return 'Wikipedia';
        if (slug === 'lds') return 'Gospel Library';
        if (slug === 'web') return 'Web';
        if (slug === 'other') return 'Other';
        if (!slug) return 'Other';
        return slug.charAt(0).toUpperCase() + slug.slice(1);
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

        const safeLabel = this.escapeHtml(label);
        const safeType = this.escapeHtml(type);

        return `<button class="summary-pill summary-pill--summary"
                 data-filter-chip="summary_type"
                 data-filter-value="${safeType}"
                 title="Filter by ${safeLabel}">${safeLabel}</button>`;
    }

    renderChip(text, type = 'category', compact = false, parent = null) {
        if (!text) return '';
        const classes = ['summary-chip'];
        if (type === 'subcategory') classes.push('summary-chip--subcategory');
        else classes.push('summary-chip--category');
        if (compact) classes.push('summary-chip--compact');
        const safeText = this.escapeHtml(text);
        const parentAttr = parent ? ` data-parent-category="${this.escapeHtml(parent)}"` : '';
        return `<button class="${classes.join(' ')}" data-filter-chip="${type}" data-filter-value="${safeText}"${parentAttr} title="Filter by ${safeText}">${safeText}</button>`;
    }

    renderCategorySection(itemId, categories = [], subcatPairs = []) {
        const uniqueCategories = Array.isArray(categories) ? categories.filter(Boolean) : [];
        const structuredPairs = Array.isArray(subcatPairs) ? subcatPairs.filter(([p, s]) => p && s) : [];

        const maxPrimary = 3;
        const primary = [];
        const hiddenCategories = [];

        uniqueCategories.forEach((cat) => {
            if (primary.length < maxPrimary) primary.push({ type: 'category', value: cat });
            else hiddenCategories.push(cat);
        });

        const remainingSubcats = [];
        structuredPairs.forEach(([parent, subcat]) => {
            if (primary.length < maxPrimary) primary.push({ type: 'subcategory', value: subcat, parent });
            else remainingSubcats.push([parent, subcat]);
        });

        const hiddenCount = hiddenCategories.length + remainingSubcats.length;
        if (!primary.length && !hiddenCount) return '';

        const extraId = `cat-extra-${itemId}`;
        const primaryHtml = primary
            .map(({ type, value, parent }) => this.renderChip(value, type, true, parent || null))
            .join('');
        const hiddenCategoryHtml = hiddenCategories.map(cat => this.renderChip(cat, 'category', true)).join('');
        const hiddenSubcatHtml = remainingSubcats.map(([parent, sc]) => this.renderChip(sc, 'subcategory', true, parent)).join('');

        const moreButton = hiddenCount > 0
            ? `<button type="button" class="summary-chip summary-chip--more summary-chip--compact" data-category-toggle="${extraId}" data-more-label="+${hiddenCount} more" aria-expanded="false" aria-controls="${extraId}">+${hiddenCount} more</button>`
            : '';

        const extraMarkup = hiddenCount > 0
            ? `<div class="summary-card__tags summary-card__tags--extra hidden" id="${extraId}" data-category-extra="${extraId}">${hiddenCategoryHtml}${hiddenSubcatHtml}</div>`
            : '';

        return `
            <div class="summary-card__taxonomy">
                <div class="summary-card__tags" data-category-group>
                    ${primaryHtml}${moreButton}
                </div>
                ${extraMarkup}
            </div>
        `;
    }

    renderInlineAudioVariant(reportId, entry, audioSrc) {
        const available = Boolean(audioSrc);
        const isActive = this.currentAudio && this.currentAudio.id === reportId;
        const isPlaying = isActive && this.isPlaying;
        const statusText = !available
            ? 'Audio summary is not available for this item.'
            : isActive
                ? (isPlaying ? 'Now playing via the global controls.' : 'Ready – press play to resume.')
                : 'Ready to play. Use the button below to start playback.';
        const buttonLabel = !available
            ? 'Unavailable'
            : isActive && isPlaying ? 'Pause audio' : 'Play audio';

        const buttonState = available ? '' : 'disabled aria-disabled="true"';
        const downloadLink = available
            ? `<a class="inline-flex items-center gap-1 rounded-full border border-white/30 bg-white/20 px-3 py-1 text-xs font-semibold text-white/90 backdrop-blur hover:bg-white/30 dark:border-slate-600/50 dark:bg-slate-700/40"
                   href="${audioSrc}" download
                   data-variant-audio-download>
                   Download
               </a>`
            : '';

        return `
            <div class="rounded-xl border border-slate-200/80 bg-slate-50/80 p-4 text-sm dark:border-slate-700/70 dark:bg-slate-800/60"
                 data-audio-variant data-report-id="${reportId || ''}" data-audio-available="${available ? '1' : ''}">
                <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div class="space-y-1">
                        <p class="font-semibold text-slate-800 dark:text-slate-100">${this.escapeHtml(entry.label || 'Audio summary')}</p>
                        <p class="text-slate-600 dark:text-slate-300" data-audio-status>${statusText}</p>
                        <p class="text-xs text-slate-500 dark:text-slate-400">Use the primary player controls to scrub or adjust speed.</p>
                    </div>
                    <div class="flex items-center gap-2 self-start md:self-auto">
                        ${downloadLink}
                        <button type="button" ${buttonState}
                                class="inline-flex items-center gap-2 rounded-full border border-white/40 bg-gradient-to-r from-audio-500 to-indigo-500 px-4 py-1.5 text-sm font-semibold text-white shadow-md disabled:cursor-not-allowed disabled:border-slate-400 disabled:bg-slate-300 disabled:text-slate-600 dark:disabled:border-slate-600 dark:disabled:bg-slate-700 dark:disabled:text-slate-300"
                                data-variant-audio-btn>
                            ${buttonLabel}
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    attachInlineAudioVariantHandlers(container, reportId, audioSrc) {
        const block = container.querySelector('[data-audio-variant]');
        if (!block) return;

        const playBtn = block.querySelector('[data-variant-audio-btn]');
        if (playBtn) {
            playBtn.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                if (!audioSrc) return;
                const isActive = this.currentAudio && this.currentAudio.id === reportId;
                if (isActive && this.isPlaying) {
                    this.togglePlayPause();
                } else {
                    this.playAudio(reportId);
                }
                this.refreshAudioVariantBlocks();
            });
        }

        const downloadLink = block.querySelector('[data-variant-audio-download]');
        if (downloadLink) {
            downloadLink.addEventListener('click', (event) => {
                event.stopPropagation();
            });
        }
    }

    refreshAudioVariantBlocks() {
        const blocks = document.querySelectorAll('[data-audio-variant]');
        if (!blocks.length) return;

        blocks.forEach((block) => {
            const reportId = block.getAttribute('data-report-id');
            const available = block.getAttribute('data-audio-available') === '1';
            const statusEl = block.querySelector('[data-audio-status]');
            const button = block.querySelector('[data-variant-audio-btn]');

            if (!available) {
                if (statusEl) statusEl.textContent = 'Audio summary is not available for this item.';
                if (button) {
                    button.textContent = 'Unavailable';
                    button.disabled = true;
                }
                return;
            }

            const isActive = this.currentAudio && this.currentAudio.id === reportId;
            const isPlaying = isActive && this.isPlaying;

            if (statusEl) {
                statusEl.textContent = isActive
                    ? (isPlaying ? 'Now playing via the global controls.' : 'Ready – press play to resume.')
                    : 'Ready to play. Use the button below to start playback.';
            }

            if (button) {
                button.disabled = false;
                button.textContent = isActive && isPlaying ? 'Pause audio' : 'Play audio';
            }
        });
    }

    renderActionBar(item, durations = {}, hasAudio = false) {
        const groupLabel = 'Summary actions';
        const segments = [];
        const source = (item.content_source || item.source || 'youtube').toString().toLowerCase();
        const hasWatchLink = source === 'youtube' ? Boolean(item.video_id) : Boolean(item.canonical_url);

        const readDuration = durations.read || '';
        segments.push({
            key: 'read',
            label: 'Read',
            title: readDuration ? `Read • ${readDuration}` : 'Read summary',
            icon: '<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5a2 2 0 012-2h4a2 2 0 012 2v14a1 1 0 01-1.447.894L9 18.118l-2.553 1.776A1 1 0 015 19V5z"/><path d="M12 3h4a2 2 0 012 2v14a1 1 0 01-1.447.894L17 18.118l-2.553 1.776A1 1 0 0113 19V5a2 2 0 00-1-1.732"/></svg>',
            duration: readDuration,
            listen: false,
            disabled: false
        });

        const listenDuration = durations.listen || '';
        if (hasAudio) {
            segments.push({
                key: 'listen',
                label: 'Listen',
                title: listenDuration ? `Listen • ${listenDuration}` : 'Play audio summary',
                icon: '<svg data-icon-play class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg><svg data-icon-pause class="w-3.5 h-3.5 hidden" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h3v14H6zm9 0h3v14h-3z"/></svg>',
                duration: listenDuration,
                listen: true,
                disabled: false
            });
        }

        const watchDuration = durations.watch || '';
        const watchLabel = source === 'youtube' ? 'Watch' : 'Open';
        const watchIcon = source === 'youtube'
            ? '<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M10 9l5 3-5 3V9z"/></svg>'
            : '<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17l9-9"/><path d="M7 7h9v9"/></svg>';
        const watchTitle = watchDuration
            ? `${watchLabel} • ${watchDuration}`
            : (source === 'youtube' ? 'Open on YouTube' : 'Open original source');
        if (hasWatchLink) {
            segments.push({
                key: 'watch',
                label: watchLabel,
                title: watchTitle,
                icon: watchIcon,
                duration: watchDuration,
                listen: false,
                disabled: false,
                primary: !hasAudio
            });
        } else if (source === 'youtube') {
            segments.push({
                key: 'watch',
                label: watchLabel,
                title: 'Source link not available',
                icon: watchIcon,
                duration: watchDuration,
                listen: false,
                disabled: true
            });
        }

        const buttonsHtml = segments.map((segment) => {
            const classes = ['variant-toggle', 'summary-card__action', `summary-card__action--${segment.key}`];
            if (segment.primary) classes.push('summary-card__action--primary');
            if (segment.disabled) classes.push('variant-toggle--disabled');

            const attrs = [`data-action="${segment.key}"`];
            if (segment.disabled) {
                attrs.push('disabled', 'aria-disabled="true"');
            }
            if (segment.listen && !segment.disabled) {
                attrs.push('data-listen-button', 'data-default-label="Listen"', 'data-playing-label="Pause"');
            }

            const durationHtml = segment.duration
                ? `<span class="variant-duration"${segment.listen && !segment.disabled ? ' data-duration' : ''}>${this.escapeHtml(segment.duration)}</span>`
                : '';
            const labelAttr = segment.listen ? ' data-label' : '';
            const safeTitle = this.escapeHtml(segment.title);
            const safeLabel = this.escapeHtml(segment.label);

            return `
                <button type="button" class="${classes.join(' ')}" ${attrs.join(' ')} title="${safeTitle}">
                    <span class="variant-icon">${segment.icon}</span>
                    <span class="variant-label" data-label-wrapper>
                        <span class="variant-text"${labelAttr}>${safeLabel}</span>
                        ${durationHtml}
                    </span>
                </button>
            `;
        }).join('');

        return `<div class="summary-card__cta variant-toggle-group" role="group" aria-label="${groupLabel}">${buttonsHtml}</div>`;
    }

    renderActionSegmentsV5(item, durations = {}, hasAudio = false, hasWatchLink = false, sourceSlug = 'web') {
        const segments = [];
        segments.push({
            key: 'read',
            label: 'Read',
            duration: durations.read || null,
            title: durations.read ? `Read • ${durations.read}` : 'Read summary',
            disabled: false
        });

        if (hasAudio) {
            segments.push({
                key: 'listen',
                label: 'Listen',
                duration: durations.listen || null,
                title: durations.listen ? `Listen • ${durations.listen}` : 'Play audio summary',
                disabled: false,
                listen: true
            });
        }

        if (hasWatchLink) {
            const watchLabel = sourceSlug === 'youtube' ? 'Watch' : 'Open';
            segments.push({
                key: 'watch',
                label: watchLabel,
                duration: durations.watch || null,
                title: durations.watch ? `${watchLabel} • ${durations.watch}` : (sourceSlug === 'youtube' ? 'Open on YouTube' : 'Open original source'),
                disabled: false
            });
        }

        if (!segments.length) return '';

        const buttons = segments.map((segment) => {
            const disabledAttr = segment.disabled ? 'disabled aria-disabled="true"' : '';
            const parts = [];
            if (segment.listen) {
                parts.push(`data-listen-button`);
                parts.push(`data-default-label="Listen"`);
                parts.push(`data-playing-label="Pause"`);
            }
            const durationHtml = segment.duration ? `<span class="stream-card__segment-duration">• ${this.escapeHtml(segment.duration)}</span>` : '';
            const labelHtml = segment.listen
                ? `<span class="stream-card__segment-label" data-label>${this.escapeHtml(segment.label)}</span>`
                : `<span class="stream-card__segment-label">${this.escapeHtml(segment.label)}</span>`;
            return `<button class="stream-card__segment" data-action="${segment.key}" title="${this.escapeHtml(segment.title)}" ${disabledAttr} ${parts.join(' ')}>${labelHtml}${durationHtml}</button>`;
        }).join('');

        return `<div class="stream-card__segments" role="group" aria-label="Summary actions">${buttons}</div>`;
    }


    renderMediaActionsV5(item, durations = {}, hasAudio = false, hasWatchLink = false, sourceSlug = 'web') {
        const buttons = [];

        if (hasAudio) {
            const duration = durations.listen || null;
            const listenIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 0116 0"></path><path d="M4 12v6a2 2 0 002 2h1a2 2 0 002-2v-3a2 2 0 00-2-2H4z"></path><path d="M20 12v6a2 2 0 01-2 2h-1a2 2 0 01-2-2v-3a2 2 0 012-2h3z"></path></svg>';
            const title = duration ? `Listen • ${duration}` : 'Play audio summary';
            const safeTitle = this.escapeHtml(title);
            buttons.push(`<button type="button" class="stream-card__media-btn" data-action="listen" data-listen-button data-default-label="Listen" data-playing-label="Pause" title="${safeTitle}" aria-pressed="false">${listenIcon}<span class="sr-only" data-label>Listen</span></button>`);
        }

        if (hasWatchLink) {
            const duration = durations.watch || null;
            const isYoutube = sourceSlug === 'youtube';
            const title = duration ? `${isYoutube ? 'Watch' : 'Open'} • ${duration}` : (isYoutube ? 'Open on YouTube' : 'Open original source');
            const icon = isYoutube
                ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><path d="M10 9l6 3-6 3V9z"></path></svg>'
                : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17l9-9"></path><path d="M7 7h9v9"></path></svg>';
            const label = isYoutube ? 'Watch' : 'Open';
            const safeTitle = this.escapeHtml(title);
            buttons.push(`<button type="button" class="stream-card__media-btn" data-action="watch" title="${safeTitle}">${icon}<span class="sr-only">${label}</span></button>`);
        }

        if (!buttons.length) return '';
        return `<div class="stream-card__media-actions">${buttons.join('')}</div>`;
    }

    normalizeCardItem(item) {
        const title = item.title || 'Untitled';
        const channel = item.channel ?? item.channel_name ?? 'Unknown Channel';
        const analysis = item.analysis ?? item.analysis_json ?? {};
        const fileStem = item.file_stem ?? item.video_id ?? '';
        const summaryType = item.summary_variant || item.summary_type || 'unknown';
        const canonicalUrl = item.canonical_url || item.url || '';
        const { slug: contentSource, label: sourceLabel } = this.inferSource({ ...item, canonical_url: canonicalUrl });
        return { ...item, title, channel, analysis, file_stem: fileStem, summary_type: summaryType, content_source: contentSource, source_label: sourceLabel, canonical_url: canonicalUrl };
    }

    // Normalize NAS-relative asset URLs (e.g., "exports/...") to absolute path "/exports/..."
    normalizeAssetUrl(u) {
        if (!u || typeof u !== 'string') return u;
        const trimmed = u.trim();
        if (!trimmed) return trimmed;
        if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed;
        // Ensure leading slash for dashboard static serving
        if (trimmed.startsWith('/')) return trimmed;
        return `/${trimmed}`;
    }

    // --- Global image mode controls ---
    updateImageModeUI() {
        const sets = [
            {
                thumb: this.imgModeThumbBtn,
                ai: this.imgModeAiBtn,
                rotate: this.imgModeRotateBtn
            },
            {
                thumb: this.imgModeThumbBtnMobile,
                ai: this.imgModeAiBtnMobile,
                rotate: this.imgModeRotateBtnMobile
            },
            {
                thumb: this.imgModeThumbSettingBtn,
                ai: this.imgModeAiSettingBtn,
                rotate: this.imgModeRotateSettingBtn
            }
        ];
        sets.forEach(s => {
            if (!s) return;
            [s.thumb, s.ai, s.rotate].forEach(btn => { if (btn) btn.classList.remove('bg-slate-200', 'dark:bg-slate-700'); });
            const active = this.imageMode === 'thumbnail' ? s.thumb : this.imageMode === 'ai' ? s.ai : s.rotate;
            if (active) active.classList.add('bg-slate-200', 'dark:bg-slate-700');
        });
    }

    setImageMode(mode) {
        this.imageMode = mode;
        localStorage.setItem('ytv2.imageMode', mode);
        this.updateImageModeUI();
        this.applyImageModeToAllCards();
    }

    applyImageModeToAllCards() {
        if (!this.contentGrid) return;
        const cards = this.contentGrid.querySelectorAll('[data-card]');
        let idx = 0;
        cards.forEach(card => this.applyImageModeToCard(card, idx++));
    }

    shouldShowSummaryByRotate(id) {
        try {
            let h = 0;
            for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) & 0xffffffff;
            return (h & 1) === 1; // ~50% probability
        } catch (_) { return false; }
    }

    applyImageModeToCard(card, index = 0) {
        if (!card) return;
        const media = card.querySelector('.summary-card__media, .stream-card__media, .mosaic-card__media, .wall-card__media, .relative.w-full.h-40');
        if (!media) return;
        const imgDefault = media.querySelector('[data-role="thumb-default"]');
        const imgSummary = media.querySelector('[data-role="thumb-summary"]');
        const toggleBtn = media.querySelector('[data-action="toggle-image"]');

        // If only one image exists, show it and hide the toggle
        if (imgSummary && !imgDefault) {
            imgSummary.classList.remove('hidden');
            if (toggleBtn) toggleBtn.classList.add('hidden');
            return;
        }
        if (imgDefault && !imgSummary) {
            imgDefault.classList.remove('hidden');
            if (toggleBtn) toggleBtn.classList.add('hidden');
            return;
        }
        if (!imgDefault || !imgSummary) return;
        if (toggleBtn) toggleBtn.classList.remove('hidden');

        let showSummary = false;
        if (this.imageMode === 'ai') showSummary = true;
        else if (this.imageMode === 'thumbnail') showSummary = false;
        else if (this.imageMode === 'rotate') {
            const id = card.getAttribute('data-report-id') || String(index);
            showSummary = this.shouldShowSummaryByRotate(id);
        }

        if (showSummary) {
            imgDefault.classList.add('hidden');
            imgSummary.classList.remove('hidden');
        } else {
            imgSummary.classList.add('hidden');
            imgDefault.classList.remove('hidden');
        }
    }

    wireImageErrorHandlers(card) {
        if (!card) return;
        const media = card.querySelector('.summary-card__media, .stream-card__media, .mosaic-card__media, .wall-card__media, .relative.w-full.h-40');
        if (!media) return;
        const imgDefault = media.querySelector('[data-role="thumb-default"]');
        const imgSummary = media.querySelector('[data-role="thumb-summary"]');
        const toggleBtn = media.querySelector('[data-action="toggle-image"]');
        if (imgSummary) {
            imgSummary.addEventListener('error', () => {
                imgSummary.classList.add('hidden');
                if (imgDefault) imgDefault.classList.remove('hidden');
                if (toggleBtn) toggleBtn.classList.add('hidden');
            }, { once: true });
        }
        if (imgDefault && imgDefault.tagName === 'IMG') {
            imgDefault.addEventListener('error', () => {
                if (imgSummary) {
                    imgDefault.classList.add('hidden');
                    imgSummary.classList.remove('hidden');
                    if (toggleBtn) toggleBtn.classList.add('hidden');
                }
            }, { once: true });
        }
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
                .filter(Boolean);

            const subcatPairs = subcategoriesStructure.categories.flatMap(c => {
                const parent = c?.category;
                if (!parent || !Array.isArray(c?.subcategories)) return [];
                return c.subcategories.map(sc => [parent, sc]);
            });

            const subcats = Array.from(new Set(subcatPairs.map(([, s]) => s)));

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
        this.seekToIn(this.progressContainer, event);
    }

    seekToIn(container, event) {
        if (!container) return;
        const rect = container.getBoundingClientRect();
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
            const isCurrentlyActive = this.currentAudio && this.currentAudio.id === id;
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
            const isActiveCard = this.currentAudio && this.currentAudio.id === id;
            if (!isActiveCard) {
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
        const v = this.searchInput.value;
        if (this.searchInputTop && this.searchInputTop.value !== v) this.searchInputTop.value = v;
        if (this.searchInputHeader && this.searchInputHeader.value !== v) this.searchInputHeader.value = v;
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
        if (this.sortToolbar) {
            this.sortToolbar.querySelectorAll('[data-sort]').forEach(btn => {
                const active = btn.dataset.sort === this.currentSort;
                if (active) {
                    btn.classList.add('bg-audio-500', 'text-white', 'dark:bg-audio-600');
                    btn.classList.remove('bg-white', 'dark:bg-slate-700', 'text-slate-700', 'dark:text-slate-200');
                } else {
                    btn.classList.remove('bg-audio-500', 'text-white', 'dark:bg-audio-600');
                    btn.classList.add('bg-white', 'dark:bg-slate-700', 'text-slate-700', 'dark:text-slate-200');
                }
            });
        }
        if (this.sortSelect) {
            this.sortSelect.value = this.currentSort;
        }
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
        this.updateShowAllButtonVisibility();
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

    selectAllFilters() {
        document.querySelectorAll('input[type="checkbox"][data-filter]').forEach(cb => {
            cb.checked = true;
        });
        this.currentFilters = this.computeFiltersFromDOM();
        this.currentPage = 1;
        this.updateHeroBadges();
        this.updateShowAllButtonVisibility();
        this.loadContent();
    }

    updateShowAllButtonVisibility() {
        const btn = document.getElementById('clearAllFilters');
        if (!btn) return;
        const inputs = Array.from(document.querySelectorAll('input[type="checkbox"][data-filter]'));
        if (!inputs.length) { btn.classList.add('hidden'); return; }
        const allChecked = inputs.every(cb => cb.checked);
        if (allChecked) btn.classList.add('hidden'); else btn.classList.remove('hidden');
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
                if (event.code === 'KeyW') this.openSourceLink(card.dataset.source || 'youtube', card.dataset.videoId || '', card.dataset.canonicalUrl || '');
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

    renderPendingImageOverrideChip(itemOrNormalized) {
        try {
            const a = (itemOrNormalized && itemOrNormalized.analysis) ? itemOrNormalized.analysis : {};
            const pending = a && typeof a === 'object' && a.summary_image_prompt
                && a.summary_image_prompt !== a.summary_image_prompt_last_used;
            if (!pending) return '';
            return '<span class="summary-pill summary-pill--pending" title="Custom image prompt pending">Pending override</span>';
        } catch (_) {
            return '';
        }
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

    async handleCreateImagePrompt(reportId) {
        try {
            // Prefill with last-used; fallback to pending override
            let defaultPrompt = '';
            try {
                const item = (this.currentItems || []).find(x => x.file_stem === reportId);
                const a = item && item.analysis ? item.analysis : {};
                defaultPrompt = a.summary_image_prompt_last_used || a.summary_image_prompt || '';
            } catch(_) {}
            const promptText = await this.promptForImagePrompt(defaultPrompt, reportId);
            if (!promptText && promptText !== '') return; // canceled
            const token = this.getReprocessToken();
            if (!token) { this.showToast('Token required', 'warn'); return; }
            const res = await fetch('/api/set-image-prompt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ video_id: reportId, prompt: promptText })
            });
            if (!res.ok) {
                const msg = await res.text().catch(()=>'');
                this.showToast(`Failed to save image prompt (${res.status})`, 'error');
                console.error('set-image-prompt failed', res.status, msg);
                return;
            }
            this.showToast('Image prompt saved. NAS will regenerate on next pass.', 'success');
        } catch (e) {
            console.error('handleCreateImagePrompt error', e);
            this.showToast('Failed to save image prompt', 'error');
        }
    }

    promptForImagePrompt(defaultText = '', reportId = null) {
        return new Promise((resolve) => {
            // Build lightweight modal
            const overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4';
            overlay.style.zIndex = '1000';
            overlay.setAttribute('role', 'dialog');
            overlay.setAttribute('aria-modal', 'true');

            const panel = document.createElement('div');
            panel.className = 'w-full max-w-xl rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-xl';
            // Variants list (if any)
            let variantsMarkup = '';
            try {
                if (reportId && Array.isArray(this.currentItems)) {
                    const item = this.currentItems.find(x => x.file_stem === reportId);
                    const variants = item && item.analysis && Array.isArray(item.analysis.summary_image_variants)
                        ? item.analysis.summary_image_variants : [];
                    if (variants.length) {
                        const rows = variants.map((v, i) => {
                            const url = this.normalizeAssetUrl(v.url || '');
                            const preview = this.truncateText((v.prompt || '').replace(/\s+/g, ' ').trim(), 120);
                            const when = this.formatRelativeTime(v.created_at);
                            const model = v.model || '';
                            const seed = (v.seed != null) ? ` • seed ${v.seed}` : '';
                            return `
                              <div class="flex items-start gap-3 p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 border border-transparent">
                                <div class="w-16 h-16 rounded-md overflow-hidden bg-slate-200 dark:bg-slate-700 flex-shrink-0">
                                  <a href="${url}" target="_blank" rel="noopener">
                                    <img src="${url}" alt="variant" class="w-full h-full object-cover" loading="lazy">
                                  </a>
                                </div>
                                <div class="flex-1 min-w-0">
                                  <div class="text-xs text-slate-500 dark:text-slate-400">${when || ''}${model ? ` • ${this.escapeHtml(model)}` : ''}${seed}</div>
                                  <div class="text-sm text-slate-700 dark:text-slate-200 truncate">${this.escapeHtml(preview || '')}</div>
                                  <div class="mt-2 flex items-center gap-2">
                                    <button type="button" data-use-prompt data-index="${i}" class="px-2 py-1 text-xs rounded-md border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700">Use this prompt</button>
                                    <button type="button" data-select-image data-index="${i}" class="px-2 py-1 text-xs rounded-md bg-audio-600 text-white hover:bg-audio-700">Select this image</button>
                                  </div>
                                </div>
                              </div>`;
                        }).join('');
                        variantsMarkup = `
                          <div class="px-4 pb-3">
                            <div class="text-xs uppercase tracking-wide text-slate-400 mb-2">Previous images</div>
                            <div class="max-h-56 overflow-auto pr-1 space-y-2" data-variants>${rows}</div>
                          </div>`;
                    }
                }
            } catch(_) {}

            panel.innerHTML = `
              <div class="px-4 py-3 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200">Create image</h3>
                <button type="button" data-close class="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Close">✕</button>
              </div>
              <div class="p-4 space-y-3">
                <label class="block text-sm text-slate-600 dark:text-slate-300 mb-1">Custom prompt</label>
                <textarea data-input rows="5" class="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white/90 dark:bg-slate-800/80 px-3 py-2 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-audio-500" placeholder="Describe the illustration you want..."></textarea>
                <p class="text-xs text-slate-500 dark:text-slate-400">NAS will use this prompt the next time it regenerates the summary image.</p>
              </div>
              ${variantsMarkup}
              <div class="px-4 py-3 border-t border-slate-200 dark:border-slate-700 flex items-center justify-end gap-2">
                <button type="button" data-cancel class="px-3 py-1.5 rounded-md border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200">Cancel</button>
                <button type="button" data-save class="px-3 py-1.5 rounded-md bg-audio-600 text-white hover:bg-audio-700">Save</button>
              </div>`;
            overlay.appendChild(panel);
            document.body.appendChild(overlay);

            const input = panel.querySelector('[data-input]');
            const save = panel.querySelector('[data-save]');
            const cancel = panel.querySelector('[data-cancel]');
            const close = panel.querySelector('[data-close]');
            const variantsEl = panel.querySelector('[data-variants]');
            input.value = defaultText || '';
            setTimeout(() => input.focus(), 10);

            const cleanup = () => {
                try { document.body.removeChild(overlay); } catch(_) {}
            };
            const finish = (val) => { cleanup(); resolve(val); };

            save.addEventListener('click', () => finish(input.value.trim()));
            cancel.addEventListener('click', () => finish(null));
            close.addEventListener('click', () => finish(null));
            overlay.addEventListener('click', (e) => { if (e.target === overlay) finish(null); });
            panel.addEventListener('keydown', (e) => { if (e.key === 'Escape') finish(null); });

            // Variants interactions
            if (variantsEl && reportId) {
                variantsEl.addEventListener('click', async (e) => {
                    const useBtn = e.target.closest('[data-use-prompt]');
                    const selectBtn = e.target.closest('[data-select-image]');
                    if (!useBtn && !selectBtn) return;
                    e.preventDefault();
                    const idx = Number((useBtn || selectBtn).dataset.index);
                    const item = (this.currentItems || []).find(x => x.file_stem === reportId);
                    const variants = item && item.analysis && Array.isArray(item.analysis.summary_image_variants)
                        ? item.analysis.summary_image_variants : [];
                    const selected = variants[idx];
                    if (!selected) return;
                    if (useBtn) {
                        input.value = selected.prompt || '';
                        input.focus();
                        input.setSelectionRange(input.value.length, input.value.length);
                        return;
                    }
                    if (selectBtn) {
                        const token = this.getReprocessToken();
                        if (!token) { this.showToast('Token required', 'warn'); return; }
                        try {
                            const res = await fetch('/api/select-image-variant', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'Authorization': `Bearer ${token}`
                                },
                                body: JSON.stringify({ video_id: reportId, url: selected.url })
                            });
                            if (!res.ok) {
                                const msg = await res.text().catch(()=> '');
                                console.error('select-image-variant failed', res.status, msg);
                                this.showToast(`Failed to select image (${res.status})`, 'error');
                                return;
                            }
                            this.showToast('Selected image updated', 'success');
                            // Update in-memory item and the card DOM inline
                            try {
                                if (item) {
                                    item.summary_image_url = selected.url;
                                    if (item.analysis) item.analysis.summary_image_selected_url = selected.url;
                                }
                            } catch(_) {}
                            this.updateCardSummaryImage(reportId, selected.url);
                        } catch (err) {
                            console.error('select-image-variant error', err);
                            this.showToast('Failed to select image', 'error');
                        }
                    }
                });
            }
        });
    }

    encodeBase64(value) {
        if (typeof btoa === 'function') {
            try {
                return btoa(value);
            } catch (_) {
                try {
                    return btoa(unescape(encodeURIComponent(value)));
                } catch (error) {
                    console.warn('Base64 encoding failed', error);
                }
            }
        }
        if (typeof Buffer !== 'undefined') {
            return Buffer.from(value, 'utf8').toString('base64');
        }
        return value;
    }

    updateCardSummaryImage(reportId, url) {
        try {
            const normalized = this.normalizeAssetUrl(url);
            const card = document.querySelector(`[data-report-id="${CSS.escape(reportId)}"]`);
            if (!card) return;
            const img = card.querySelector('[data-role="thumb-summary"]');
            if (img) {
                img.src = normalized;
                img.classList.remove('hidden');
            }
            // Also update any inline reader image if open
            const inline = document.querySelector(`[data-expand-region] [data-role="thumb-summary"]`);
            if (inline) {
                inline.src = normalized;
                inline.classList.remove('hidden');
            }
        } catch (_) {
            // no-op
        }
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
        let text = rawText.replace(/\r\n?/g, '\n').trim();

        // Convert inline bullet separators ("Header • point • point …") into
        // a header + newline-delimited hyphen bullets so we can render lists.
        // Works across paragraphs separated by blank lines.
        try {
            const paras = text.split(/\n{2,}/);
            const rebuilt = paras.map(p => {
                if (!p || p.indexOf('•') === -1) return p;
                // Split around the bullet dot with surrounding spaces
                const bits = p.split(/\s*•\s*/).map(s => s.trim()).filter(Boolean);
                if (bits.length < 2) return p;
                // Treat first chunk as a header when it doesn't start with a bullet marker
                const first = bits.shift();
                const header = first.length <= 160 ? first : null;
                const bullets = header ? bits : [first, ...bits];
                const headerLine = header ? header + '\n' : '';
                const bulletLines = bullets.map(b => `- ${b}`).join('\n');
                return headerLine + bulletLines;
            }).join('\n\n');
            text = rebuilt;
        } catch (_) {}

        // Detect "run-on hyphen bullets" and convert to line-broken bullets
        // Example: "... sentence. - point one - point two - point three" -> break into lines with "- "
        // Avoid hyphens in the middle of words by requiring surrounding whitespace/punctuation
        try {
            const newlineCount = (text.match(/\n/g) || []).length;
            const hyphenRuns = (text.match(/(?:^|[.!?])\s*[-–—]\s+/g) || []).length;
            if (newlineCount <= 2 && hyphenRuns >= 2) {
                // Insert newlines before hyphen bullets following sentence boundaries or start
                text = text
                    .replace(/(?:^|([.!?]))\s*[-–—]\s+/g, (m, p1) => (p1 ? p1 + '\n- ' : '- '))
                    .replace(/\s{2,}/g, ' ');
            }
        } catch (_) {}

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

        // If we now have clear bullet lines, render them as a list
        const bulletLines = text.split('\n').map(s => s.trim()).filter(s => /^[-•*]\s+/.test(s));
        if (bulletLines.length >= 2) {
            const prefaceIdx = text.indexOf('\n- ');
            const preface = prefaceIdx > 0 ? text.slice(0, prefaceIdx).trim() : '';
            const bulletHtml = bulletLines.map(l => l.replace(/^[-•*]\s+/, ''))
                .map(b => `<li>${this.escapeHtml(b)}</li>`).join('');
            const parts = [];
            if (preface) parts.push(`<p>${this.escapeHtml(preface)}</p>`);
            parts.push(`<ul class="kp-list">${bulletHtml}</ul>`);
            return parts.join('');
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
                        if (this.autoPlayOnLoad) {
                            this.setCurrentFromItem(item);
                        } else {
                            this.showNowPlayingPlaceholder();
                        }
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
        const sidebar = this.sidebarElement || document.getElementById('sidebar');
        if (sidebar) {
            this._collapsedForMobile = this.sidebarCollapsed;
            if (this.sidebarCollapsed) {
                this.sidebarCollapsed = false;
                this.applySidebarCollapsedState();
            }
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
        const sidebar = this.sidebarElement || document.getElementById('sidebar');
        if (sidebar) {
            // Hide the sidebar properly
            sidebar.classList.remove('flex');
            sidebar.classList.add('hidden');
            sidebar.style.display = '';
            // Restore body scroll
            document.body.style.overflow = '';
            if (typeof this._collapsedForMobile === 'boolean') {
                this.sidebarCollapsed = this._collapsedForMobile;
                this._collapsedForMobile = null;
                this.applySidebarCollapsedState();
            }
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
