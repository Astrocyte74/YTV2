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
        this.currentFilters = {};
        this.currentPage = 1;
        this.currentSort = 'newest';
        this.searchQuery = '';
        this.viewMode = (localStorage.getItem('ytv2.viewMode') || 'list');
        
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
        this.nowPlayingPreview = document.getElementById('nowPlayingPreview');
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
        this.audioElement.addEventListener('ended', () => this.playNext());
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
        // Play All button removed - auto-playlist handles this
        if (this.listViewBtn) this.listViewBtn.addEventListener('click', () => this.setViewMode('list'));
        if (this.gridViewBtn) this.gridViewBtn.addEventListener('click', () => this.setViewMode('grid'));
        this.updateViewToggle();
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
        this.audioElement.addEventListener('volumechange', () => this.updateMuteIcon());
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
    setTheme(mode) { this.themeMode = mode || 'system'; localStorage.setItem('ytv2.theme', this.themeMode); this.applyTheme(this.themeMode); this.updateThemeChecks(); }
    applyTheme(mode) {
        const root = document.documentElement;
        const mq = window.matchMedia('(prefers-color-scheme: dark)');
        const wantsDark = mode === 'dark' || (mode === 'system' && mq.matches);
        root.classList.toggle('dark', wantsDark);
        if (!this._mqBound) { mq.addEventListener('change', () => { if ((localStorage.getItem('ytv2.theme') || 'system') === 'system') this.applyTheme('system'); }); this._mqBound = true; }
    }
    updateThemeChecks() {
        const id = `themeCheck-${this.themeMode}`;
        ['system','light','dark'].forEach(k => {
            const el = document.getElementById(`themeCheck-${k}`); if (el) el.textContent = (k===this.themeMode?'✓':'');
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
            <label class="flex items-center space-x-2 cursor-pointer hover:bg-slate-50 rounded px-2 py-1 transition-colors">
                <input type="checkbox" 
                       value="${this.escapeHtml(item.value)}" 
                       data-filter="${filterType}"
                       class="rounded border-slate-300 text-audio-500 focus:ring-audio-500 focus:ring-offset-0">
                <span class="text-sm text-slate-700 flex-1">${this.escapeHtml(item.value)}</span>
                <span class="text-xs text-slate-400">${item.count}</span>
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
        
        // Bind play buttons
        this.contentGrid.querySelectorAll('[data-play-btn]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const reportId = e.target.closest('[data-report-id]').dataset.reportId;
                this.playAudio(reportId);
            });
        });
        
        // Bind add to queue buttons
        this.contentGrid.querySelectorAll('[data-queue-btn]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const reportId = e.target.closest('[data-report-id]').dataset.reportId;
                this.addToQueue(reportId);
            });
        });

        // Bind delete buttons
        this.contentGrid.querySelectorAll('[data-delete-btn]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const card = e.target.closest('[data-report-id]');
                const stem = card.dataset.reportId;
                const title = card.querySelector('h3')?.textContent?.trim() || stem;
                this.openConfirm(stem, title);
            });
        });

        // Make whole card clickable (except controls)
        this.contentGrid.querySelectorAll('[data-card]').forEach(card => {
            card.addEventListener('click', (e) => {
                // Ignore if click on a control
                if (e.target.closest('[data-control]')) return;
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
            <div data-card data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-href="${href}" title="Open summary" tabindex="0" class="group cursor-pointer bg-white/80 dark:bg-slate-800/60 backdrop-blur-sm rounded-xl border border-slate-200/60 dark:border-slate-700 p-4 hover:bg-white dark:hover:bg-slate-800 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200">
                <div class="flex gap-4 items-start">
                    <div class="relative w-56 aspect-video overflow-hidden rounded-lg bg-slate-100 flex-shrink-0">
                        ${item.thumbnail_url ? `<img src="${item.thumbnail_url}" alt="thumbnail" class="absolute inset-0 w-full h-full object-cover">` : ''}
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-start justify-between gap-3">
                            <div class="flex-1 min-w-0">
                                <h3 class="text-lg font-semibold text-slate-800 group-hover:text-audio-700 transition-colors line-clamp-2">
                                    ${this.escapeHtml(item.title)}
                                </h3>
                                <div class="text-sm text-slate-500 mt-0.5 line-clamp-1 flex items-center gap-2">
                                    <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 text-slate-700 text-[10px]">${channelInitial}</span>
                                    ${this.escapeHtml(item.channel || '')}
                                    ${isPlaying ? '<span class="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-audio-100 text-audio-700">Now Playing</span>' : ''}
                                </div>
                                <div class="mt-1 flex items-center gap-2 text-sm text-slate-500">
                                    <span>${duration}</span>
                                    <span>•</span>
                                    <span>${item.analysis?.complexity_level || 'Intermediate'}</span>
                                    <span>•</span>
                                    <span>${item.analysis?.language || 'en'}</span>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                ${hasAudio ? `
                                <button data-control data-play-btn title="Listen" aria-label="Listen" class="p-3 rounded-full bg-audio-500 text-white hover:bg-audio-600 focus:ring-2 focus:ring-audio-500 transition-all duration-200 shadow-lg hover:shadow-xl hover:scale-105">
                                    <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                                </button>
                                ` : ''}
                                <button data-control data-delete-btn title="Delete" aria-label="Delete" class="p-2 rounded-lg text-red-600 hover:bg-red-50 focus:ring-2 focus:ring-red-500">
                                    <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6"/><path d="M10 11v6M14 11v6"/><path d="M9 6l1-2h4l1 2"/></svg>
                                </button>
                            </div>
                        </div>

                        <div class="mt-3 flex flex-wrap gap-2">
                            ${categories.map(cat => `
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-audio-100 dark:bg-slate-700 text-audio-800 dark:text-slate-300">${this.escapeHtml(cat)}</span>
                            `).join('')}
                        </div>
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
        <div data-card data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-href="${href}" title="Open summary" tabindex="0" class="group cursor-pointer bg-white/80 dark:bg-slate-800/60 rounded-xl border border-slate-200/60 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-800 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200 overflow-hidden">
            <div class="relative aspect-video bg-slate-100">
                ${item.thumbnail_url ? `<img src="${item.thumbnail_url}" alt="thumbnail" class="absolute inset-0 w-full h-full object-cover">` : ''}
            </div>
            <div class="p-3">
                <h3 class="text-sm font-semibold text-slate-800 group-hover:text-audio-700 line-clamp-2">${this.escapeHtml(item.title)}</h3>
                <div class="text-xs text-slate-500 mt-1 line-clamp-1 flex items-center gap-2">
                    <span class="inline-flex items-center justify-center w-4 h-4 rounded-full bg-slate-200 text-slate-700 text-[9px]">${channelInitial}</span>
                    ${this.escapeHtml(item.channel || '')}
                    ${isPlaying ? '<span class="ml-2 text-[10px] px-1 py-0.5 rounded bg-audio-100 text-audio-700">Now Playing</span>' : ''}
                </div>
                <div class="mt-1 flex items-center gap-2 text-xs text-slate-500">
                    <span>${duration}</span>
                    <span>•</span>
                    <span>${item.analysis?.language || 'en'}</span>
                </div>
                <div class="mt-2 flex items-center justify-between">
                    <button data-control data-play-btn title="Listen" aria-label="Listen" class="p-2.5 rounded-full bg-audio-500 text-white hover:bg-audio-600 transition-all duration-200 shadow-lg hover:shadow-xl hover:scale-105">
                        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    </button>
                    <button data-control data-delete-btn title="Delete" aria-label="Delete" class="p-2 rounded-lg text-red-600 hover:bg-red-50 focus:ring-2 focus:ring-red-500">
                        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6"/><path d="M10 11v6M14 11v6"/><path d="M9 6l1-2h4l1 2"/></svg>
                    </button>
                </div>
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
            
            // Update current track info
            this.currentAudio = {
                id: reportId,
                title: title,
                src: audioSrc
            };

            // Update player info
            if (this.nowPlayingTitle) this.nowPlayingTitle.textContent = title;
            if (this.nowPlayingMeta) this.nowPlayingMeta.textContent = 'Loading...';
            
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
        // Implementation for adding to queue
        console.log('Adding to queue:', reportId);
        // This would integrate with a playlist system
    }

    playAllResults() {
        if (!this.currentItems || this.currentItems.length === 0) return;
        this.playlist = this.currentItems.map(i => i.file_stem);
        this.currentTrackIndex = 0;
        this.playAudio(this.playlist[0]);
    }

    playNext() {
        if (!this.playlist || this.playlist.length === 0) return;
        this.currentTrackIndex = (this.currentTrackIndex + 1) % this.playlist.length;
        this.playAudio(this.playlist[this.currentTrackIndex]);
    }

    playPrevious() {
        if (!this.playlist || this.playlist.length === 0) return;
        this.currentTrackIndex = (this.currentTrackIndex - 1 + this.playlist.length) % this.playlist.length;
        this.playAudio(this.playlist[this.currentTrackIndex]);
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
            case 'KeyM':
                if (this.currentAudio) {
                    event.preventDefault();
                    this.toggleMute();
                }
                break;
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
}

// Initialize the dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.audioDashboard = new AudioDashboard();
});
