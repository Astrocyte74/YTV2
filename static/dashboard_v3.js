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
        this.contentTypeFilters = document.getElementById('contentTypeFilters');
        this.complexityFilters = document.getElementById('complexityFilters');
        this.languageFilters = document.getElementById('languageFilters');
        
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
                document.querySelectorAll('input[data-filter="category"]').forEach(cb => {
                    cb.checked = true;
                });
                this.currentFilters = this.computeFiltersFromDOM();
                this.loadContent();
            });
        }
        if (clearAllCategories) {
            clearAllCategories.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="category"]').forEach(cb => {
                    cb.checked = false;
                });
                this.currentFilters = this.computeFiltersFromDOM();
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
                this.loadContent();
            });
        }
        if (clearAllContentTypes) {
            clearAllContentTypes.addEventListener('click', () => {
                document.querySelectorAll('input[data-filter="content_type"]').forEach(cb => {
                    cb.checked = false;
                });
                this.currentFilters = this.computeFiltersFromDOM();
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
            
            this.renderFilterSection(filters.category, this.categoryFilters, 'category');
            this.renderFilterSection(filters.content_type, this.contentTypeFilters, 'content_type');
            this.renderFilterSection(filters.complexity_level, this.complexityFilters, 'complexity');
            this.renderLanguageFilters(filters.language || []);
            
            // Bind show more toggles after content is loaded
            this.bindShowMoreToggles();
            
            // Fix 1: Initialize currentFilters after filters render
            // This ensures visual state (checkboxes) matches internal state
            this.currentFilters = this.computeFiltersFromDOM();
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
                        <span class="text-xs text-slate-400 dark:text-slate-500">${item.count}</span>
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
                                    <span class="text-xs text-slate-400 dark:text-slate-500">${sub.count}</span>
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
            <label class="flex items-center space-x-2 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700 rounded px-2 py-1 transition-colors">
                <input type="checkbox" 
                       value="${this.escapeHtml(item.value)}" 
                       data-filter="${filterType}"
                       checked
                       class="rounded border-slate-300 dark:border-slate-600 text-audio-500 focus:ring-audio-500 focus:ring-offset-0">
                <span class="text-sm text-slate-700 dark:text-slate-200 flex-1">${this.escapeHtml(item.value)}</span>
                <span class="text-xs text-slate-400 dark:text-slate-500">${item.count}</span>
            </label>
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
        return filters;
    }

    async loadContent() {
        const params = new URLSearchParams();
        
        // Add search query
        if (this.searchQuery) params.append('q', this.searchQuery);
        
        // Fix 2: Recompute state from DOM right before fetching (prevents drift)
        this.currentFilters = this.computeFiltersFromDOM();
        
        // Helper functions (OpenAI's drop-in solution)
        const getAllOptions = (filterType) =>
            Array.from(document.querySelectorAll(`input[data-filter="${filterType}"]`))
                .map(el => el.value);

        const anySelected = (filters) =>
            Object.values(filters).some(arr => Array.isArray(arr) && arr.length > 0);

        const noneSelected = (filters) =>
            !anySelected(filters);

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

        // Otherwise build params normally
        Object.entries(effectiveFilters).forEach(([key, values]) => {
            values.forEach(v => params.append(key, v));
        });
        
        console.debug('Final URL params:', params.toString());
        
        // Add pagination and sorting
        params.append('page', this.currentPage.toString());
        params.append('size', '12'); // Show 12 items per page
        params.append('sort', this.currentSort);

        try {
            const response = await fetch(`/api/reports?${params}`);
            const data = await response.json();
            this.currentItems = data.reports || data.data || [];
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
                this.applyFilterFromChip(filterType, filterValue);
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
        if (typeof data.summary === 'string') {
            summaryRaw = data.summary;
        } else if (data.summary && typeof data.summary === 'object') {
            // Try NEW format first (summary.summary)
            if (typeof data.summary.summary === 'string') {
                summaryRaw = data.summary.summary;
            }
            // Try NEW format direct comprehensive/audio
            else if (typeof data.summary.comprehensive === 'string') {
                summaryRaw = data.summary.comprehensive;
            }
            else if (typeof data.summary.audio === 'string') {
                summaryRaw = data.summary.audio;
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
          <div class="mt-3 mx-[-1rem] md:mx-[-1rem] sm:mx-0 rounded-xl bg-white/80 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 p-3 md:p-4 space-y-3 md:space-y-4" data-expanded>
            ${badges.length ? `<div class="flex items-center gap-2 text-slate-600 dark:text-slate-300 text-sm flex-wrap">${badges.join('')}</div>` : ''}
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

    async handleDelete(id, cardEl) {
        try {
            // Optimistic UI: show busy state
            const pop = cardEl.querySelector('[data-delete-popover]');
            if (pop) pop.classList.add('pointer-events-none', 'opacity-60');
            
            // Use the proper DELETE endpoint format
            const res = await fetch(`/api/delete/${encodeURIComponent(id)}`, {
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
        const duration = this.formatDuration(item.duration_seconds || 0);
        const categories = item.analysis?.category?.slice(0, 2) || ['General'];
        const hasAudio = item.media?.has_audio;
        const href = `/${item.file_stem}.json?v=2`;
        const buttonDurations = this.getButtonDurations(item);
        const totalSecs = (item.media_metadata && item.media_metadata.mp3_duration_seconds) ? item.media_metadata.mp3_duration_seconds : (item.duration_seconds || 0);
        const totalDur = (item.media_metadata && item.media_metadata.mp3_duration_seconds)
            ? this.formatDuration(item.media_metadata.mp3_duration_seconds)
            : (item.duration_seconds ? this.formatDuration(item.duration_seconds) : '');
        
        const isPlaying = this.currentAudio && this.currentAudio.id === item.file_stem && this.isPlaying;
        const channelInitial = (item.channel || '?').trim().charAt(0).toUpperCase();
        return `
            <div data-card data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-has-audio="${hasAudio ? 'true' : 'false'}" data-href="${href}" title="Open summary" tabindex="0" class="group relative list-layout cursor-pointer bg-white/80 dark:bg-slate-800/60 backdrop-blur-sm rounded-xl border border-slate-200/60 dark:border-slate-700 p-3 sm:p-4 hover:bg-white dark:hover:bg-slate-800 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200" style="--thumbW: 240px;">
                <div class="flex flex-col sm:flex-row gap-3 sm:gap-4 items-start">
                    <div class="relative w-full sm:w-56 aspect-video overflow-hidden rounded-lg bg-slate-100 flex-shrink-0">
                        ${item.thumbnail_url ? `<img src="${item.thumbnail_url}" alt="thumbnail" loading="lazy" class="absolute inset-0 w-full h-full object-cover">` : ''}
                        <div class="absolute inset-0 flex items-center justify-center pointer-events-none ${isPlaying ? '' : 'hidden'}" data-card-eq>
                            <div class="px-2 py-1 rounded-md bg-black/50 backdrop-blur-sm">
                                <div class="flex items-end gap-1 text-white">
                                    <span class="w-0.5 sm:w-1 h-3 sm:h-4 bg-current waveform-bar" style="--delay:0"></span>
                                    <span class="w-0.5 sm:w-1 h-4 sm:h-6 bg-current waveform-bar" style="--delay:1"></span>
                                    <span class="w-0.5 sm:w-1 h-6 sm:h-8 bg-current waveform-bar" style="--delay:2"></span>
                                    <span class="w-0.5 sm:w-1 h-4 sm:h-6 bg-current waveform-bar" style="--delay:3"></span>
                                    <span class="w-0.5 sm:w-1 h-3 sm:h-4 bg-current waveform-bar" style="--delay:4"></span>
                                </div>
                            </div>
                        </div>
                        <div class="absolute inset-x-0 bottom-0 h-1.5 sm:h-2 bg-black/25 cursor-pointer" data-card-progress-container data-total-seconds="${totalSecs}">
                            <div class="h-1.5 sm:h-2 bg-audio-500" style="width:0%" data-card-progress role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
                        </div>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-start justify-between gap-3">
                            <div class="flex-1 min-w-0 pr-12">
                                <h3 class="text-base sm:text-lg font-semibold text-slate-800 dark:text-slate-100 group-hover:text-audio-700 transition-colors line-clamp-2">
                                    ${this.escapeHtml(item.title)}
                                </h3>
                                <div class="text-sm text-slate-500 dark:text-slate-300 mt-0.5 line-clamp-1 flex items-center gap-2">
                                    <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 text-slate-700 text-[10px]">${channelInitial}</span>
                                    <span class="truncate">${this.escapeHtml(item.channel || '')}</span>
                                    ${isPlaying ? '<span class="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-audio-100 text-audio-700 whitespace-nowrap">Now Playing</span>' : ''}
                                </div>
                                <div class="mt-1 flex items-center gap-1 sm:gap-2 text-xs sm:text-sm text-slate-500 dark:text-slate-400 flex-wrap">
                                    <span class="whitespace-nowrap">${item.analysis?.complexity_level || 'Intermediate'}</span>
                                    <span class="hidden sm:inline">•</span>
                                    <span class="whitespace-nowrap">${item.analysis?.language || 'en'}</span>
                                </div>
                            </div>
                            <div class="absolute top-3 right-3 z-20">
                              <button class="p-2 rounded-md hover:bg-slate-200/60 dark:hover:bg-slate-700/60" data-action="menu" aria-label="More options" aria-haspopup="menu" aria-expanded="false">
                                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>
                              </button>
                              <div class="absolute right-0 mt-2 w-44 bg-white/95 dark:bg-slate-800/95 backdrop-blur border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl hidden z-50" data-kebab-menu role="menu">
                                <button class="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors" role="menuitem" data-action="copy-link">Copy link</button>
                                <button class="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors" role="menuitem" data-action="delete">Delete…</button>
                              </div>
                            </div>
                            <div class="absolute top-14 right-3 hidden z-50" data-delete-popover>
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
                                <button class="relative z-10 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-audio-100 dark:bg-slate-700 text-audio-800 dark:text-slate-300 hover:bg-audio-200 dark:hover:bg-slate-600 transition-all cursor-pointer hover:scale-105 active:scale-95" 
                                        data-filter-chip="category" 
                                        data-filter-value="${this.escapeHtml(cat)}"
                                        title="Click to filter by ${this.escapeHtml(cat)}">
                                    ${this.escapeHtml(cat)}
                                </button>
                            `).join('')}
                            ${item.analysis?.subcategory ? `
                                <button class="relative z-10 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-800/50 transition-all cursor-pointer hover:scale-105 active:scale-95" 
                                        data-filter-chip="subcategory" 
                                        data-filter-value="${this.escapeHtml(item.analysis.subcategory)}"
                                        title="Click to filter by ${this.escapeHtml(item.analysis.subcategory)}">
                                    ${this.escapeHtml(item.analysis.subcategory)}
                                </button>
                            ` : ''}
                        </div>
                        <!-- CTA row under meta -->
                        <div class="mt-3 flex flex-wrap items-center gap-2 text-sm">
                          <button class="inline-flex items-center gap-1 px-2.5 sm:px-3 py-1.5 rounded-full border border-slate-300/60 dark:border-slate-600/60 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-slate-700 dark:text-slate-200 font-medium text-xs sm:text-sm" data-action="read"><span>Read${buttonDurations.read ? ` ${buttonDurations.read}` : ''}</span><span aria-hidden="true">›</span></button>
                          ${hasAudio ? `<button class=\"inline-flex items-center gap-1 px-2.5 sm:px-3 py-1.5 rounded-full border border-slate-300/60 dark:border-slate-600/60 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-slate-700 dark:text-slate-200 font-medium text-xs sm:text-sm\" data-action=\"listen\"><span>Listen${buttonDurations.listen ? ` ${buttonDurations.listen}` : ''}</span><span aria-hidden=\"true\">›</span></button>` : ''}
                          <button class="inline-flex items-center gap-1 px-2.5 sm:px-3 py-1.5 rounded-full border border-slate-300/60 dark:border-slate-600/60 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-slate-700 dark:text-slate-200 font-medium text-xs sm:text-sm" data-action="watch"><span>Watch${buttonDurations.watch ? ` ${buttonDurations.watch}` : ''}</span><span aria-hidden="true">›</span></button>
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
        const buttonDurations = this.getButtonDurations(item);
        const totalSecs = (item.media_metadata && item.media_metadata.mp3_duration_seconds) ? item.media_metadata.mp3_duration_seconds : (item.duration_seconds || 0);
        const totalDur = (item.media_metadata && item.media_metadata.mp3_duration_seconds)
            ? this.formatDuration(item.media_metadata.mp3_duration_seconds)
            : (item.duration_seconds ? this.formatDuration(item.duration_seconds) : '');
        const categories = item.analysis?.category?.slice(0, 2) || ['General'];
        return `
        <div data-card data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-has-audio="${(item.media && item.media.has_audio) ? 'true' : 'false'}" data-href="${href}" title="Open summary" tabindex="0" class="group relative cursor-pointer bg-white/80 dark:bg-slate-800/60 rounded-xl border border-slate-200/60 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-800 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200 overflow-hidden">
            <div class="relative aspect-video bg-slate-100">
                ${item.thumbnail_url ? `<img src="${item.thumbnail_url}" alt="thumbnail" loading="lazy" class="absolute inset-0 w-full h-full object-cover">` : ''}
                <div class="absolute inset-0 flex items-center justify-center pointer-events-none" data-card-eq style="display: flex">
                    <div class="flex items-end gap-1">
                        <span class="w-0.5 sm:w-1 h-3 sm:h-4 waveform-bar-outlined" style="--delay:0"></span>
                        <span class="w-0.5 sm:w-1 h-4 sm:h-6 waveform-bar-outlined" style="--delay:1"></span>
                        <span class="w-0.5 sm:w-1 h-6 sm:h-8 waveform-bar-outlined" style="--delay:2"></span>
                        <span class="w-0.5 sm:w-1 h-4 sm:h-6 waveform-bar-outlined" style="--delay:3"></span>
                        <span class="w-0.5 sm:w-1 h-3 sm:h-4 waveform-bar-outlined" style="--delay:4"></span>
                    </div>
                </div>
                <div class="absolute inset-x-0 bottom-0 h-1.5 sm:h-2 bg-black/25 cursor-pointer" data-card-progress-container data-total-seconds="${totalSecs}">
                    <div class="h-1.5 sm:h-2 bg-audio-500" style="width:0%" data-card-progress role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
                </div>
                <div class="absolute top-2 right-2 z-20">
                  <button class="p-1.5 min-w-[36px] min-h-[36px] rounded-md bg-white/70 dark:bg-slate-900/60 hover:bg-white/90" data-action="menu" aria-label="More options" aria-haspopup="menu" aria-expanded="false">
                    <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>
                  </button>
                  <div class="absolute right-0 mt-2 w-40 bg-white/95 dark:bg-slate-800/95 backdrop-blur border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl hidden z-50" data-kebab-menu role="menu">
                    <button class="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors" role="menuitem" data-action="copy-link">Copy link</button>
                    <button class="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors" role="menuitem" data-action="delete">Delete…</button>
                  </div>
                </div>
                <div class="absolute top-12 right-2 hidden z-50" data-delete-popover>
                  <div class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-2 text-xs">
                    <div class="mb-2 text-slate-700 dark:text-slate-200">Delete this summary?</div>
                    <div class="flex items-center gap-2 justify-end">
                      <button class="px-2 py-1 rounded border border-slate-200 dark:border-slate-700" data-action="cancel-delete">Cancel</button>
                      <button class="px-2 py-1 rounded bg-red-600 text-white" data-action="confirm-delete">Delete</button>
                    </div>
                  </div>
                </div>
            </div>
            <div class="p-3 pr-12">
                <h3 class="text-sm font-semibold text-slate-800 dark:text-slate-100 group-hover:text-audio-700 line-clamp-2">${this.escapeHtml(item.title)}</h3>
                <div class="text-xs text-slate-500 dark:text-slate-300 mt-1 line-clamp-1 flex items-center gap-2">
                    <span class="inline-flex items-center justify-center w-4 h-4 rounded-full bg-slate-200 text-slate-700 text-[9px]">${channelInitial}</span>
                    ${this.escapeHtml(item.channel || '')}
                    ${isPlaying ? '<span class="ml-2 text-[10px] px-1 py-0.5 rounded bg-audio-100 text-audio-700">Now Playing</span>' : ''}
                </div>
                <div class="mt-1 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <span>${item.analysis?.complexity_level || 'Intermediate'}</span>
                    <span>•</span>
                    <span>${item.analysis?.language || 'en'}</span>
                </div>
                <!-- Category chips for grid view -->
                <div class="mt-2 flex flex-wrap gap-1">
                    ${categories.map(cat => `
                        <button class="relative z-10 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-audio-100 dark:bg-slate-700 text-audio-800 dark:text-slate-300 hover:bg-audio-200 dark:hover:bg-slate-600 transition-all cursor-pointer hover:scale-105 active:scale-95" 
                                data-filter-chip="category" 
                                data-filter-value="${this.escapeHtml(cat)}"
                                title="Click to filter by ${this.escapeHtml(cat)}">
                            ${this.escapeHtml(cat)}
                        </button>
                    `).join('')}
                    ${item.analysis?.subcategory ? `
                        <button class="relative z-10 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-800/50 transition-all cursor-pointer hover:scale-105 active:scale-95" 
                                data-filter-chip="subcategory" 
                                data-filter-value="${this.escapeHtml(item.analysis.subcategory)}"
                                title="Click to filter by ${this.escapeHtml(item.analysis.subcategory)}">
                            ${this.escapeHtml(item.analysis.subcategory)}
                        </button>
                    ` : ''}
                </div>
                <div class="mt-2 flex items-center gap-1.5 px-3 pb-2">
                    <button class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-slate-100/80 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 hover:bg-slate-200/80 dark:hover:bg-slate-700/80 transition-colors" data-action="read">
                        <span>Read</span>
                        <span class="text-[10px] opacity-70">${buttonDurations.read || '3m'}</span>
                    </button>
                    ${(item.media && item.media.has_audio) ? `
                    <button class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-slate-100/80 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 hover:bg-slate-200/80 dark:hover:bg-slate-700/80 transition-colors" data-action="listen">
                        <span>Listen</span>
                        <span class="text-[10px] opacity-70">${buttonDurations.listen || totalDur}</span>
                    </button>` : `
                    <button class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-slate-50/50 dark:bg-slate-900/50 text-slate-400 dark:text-slate-500 cursor-not-allowed opacity-60" disabled>
                        <span>Listen</span>
                        <span class="text-[10px] opacity-70">N/A</span>
                    </button>`}
                    <button class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-slate-100/80 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 hover:bg-slate-200/80 dark:hover:bg-slate-700/80 transition-colors" data-action="watch">
                        <span>Watch</span>
                        <span class="text-[10px] opacity-70">${buttonDurations.watch || totalDur}</span>
                    </button>
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
            // Clean up any leftover state from previous sessions
            this._cleanupScrubState();
            
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
        // Apply any pending seek set by a card-scrub on a non-active card
        if (typeof this._pendingSeek === 'number') {
            const duration = this.audioElement.duration;
            const pct = Math.max(0, Math.min(1, this._pendingSeek));
            if (duration && !isNaN(duration)) this.audioElement.currentTime = pct * duration;
            this._pendingSeek = null;
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
        // Card highlight
        this.contentGrid.querySelectorAll('[data-card]').forEach(card => {
            card.classList.remove('ring-2', 'ring-audio-400');
        });
        let active = null;
        if (this.currentAudio) {
            active = this.contentGrid.querySelector(`[data-report-id="${this.currentAudio.id}"]`);
            if (active) active.classList.add('ring-2', 'ring-audio-400');
        }

        // Update Listen buttons to reflect playing state
        const eqIcon = `
            <span class=\"flex items-end gap-0.5 mr-1\" aria-hidden=\"true\">
              <span class=\"w-[1.5px] h-2 bg-current opacity-90 waveform-bar\" style=\"--delay:0\"></span>
              <span class=\"w-[1.5px] h-1.5 bg-current opacity-90 waveform-bar\" style=\"--delay:1\"></span>
              <span class=\"w-[1.5px] h-2.5 bg-current opacity-90 waveform-bar\" style=\"--delay:2\"></span>
            </span>`;

        this.contentGrid.querySelectorAll('[data-card] [data-action="listen"]').forEach(btn => {
            // Ensure original label is stored once
            if (!btn.dataset.label) {
                try {
                    const txt = btn.textContent.trim();
                    btn.dataset.label = txt || 'Listen';
                } catch(_) { btn.dataset.label = 'Listen'; }
            }
            btn.classList.remove('bg-audio-600','text-white');
            btn.classList.add('border','border-slate-300/60','dark:border-slate-600/60');
            // Default label
            const defaultLabel = btn.dataset.label;
            // If this is the active card, flip the label depending on play state
            const isActive = !!(active && active.contains(btn));
            if (isActive) {
                if (this.isPlaying) {
                    btn.innerHTML = `${eqIcon}<span>Pause</span>`;
                } else {
                    btn.innerHTML = `<span>Play</span>`;
                }
                btn.classList.add('bg-audio-600','text-white');
                btn.classList.remove('border','border-slate-300/60','dark:border-slate-600/60');
            } else {
                // Restore original
                btn.innerHTML = `<span>${this.escapeHtml(defaultLabel)}</span><span aria-hidden=\"true\">›</span>`;
            }
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

    applyFilterFromChip(filterType, filterValue) {
        // Clear all current filters
        this.clearAllFilters();
        
        // Apply the clicked filter
        const checkbox = document.querySelector(`input[data-filter="${filterType}"][value="${filterValue}"]`);
        if (checkbox) {
            checkbox.checked = true;
            // If it's a subcategory, also check its parent category
            if (filterType === 'subcategory') {
                const parentCategory = checkbox.dataset.parentCategory;
                if (parentCategory) {
                    const parentCheckbox = document.querySelector(`input[data-filter="category"][value="${parentCategory}"]`);
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
});
