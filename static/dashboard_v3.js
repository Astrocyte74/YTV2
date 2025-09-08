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
        
        // Player info
        // Legacy bottom-player ids not present anymore; keep null-safe
        this.playerTitle = document.getElementById('playerTitle');
        this.playerMeta = document.getElementById('playerMeta');
        
        // Search and filters
        this.searchInput = document.getElementById('searchInput');
        this.sortSelect = document.getElementById('sortSelect');
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
        
        // Action buttons
        this.playAllBtn = document.getElementById('playAllBtn');
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
        
        // Search and filters
        this.searchInput.addEventListener('input', 
            this.debounce(() => this.handleSearch(), 500));
        this.sortSelect.addEventListener('change', () => this.handleSortChange());
        
        // UI controls
        this.queueToggle.addEventListener('click', () => this.toggleQueue());
        this.playAllBtn.addEventListener('click', () => this.playAllResults());
        if (this.listViewBtn) this.listViewBtn.addEventListener('click', () => this.setViewMode('list'));
        if (this.gridViewBtn) this.gridViewBtn.addEventListener('click', () => this.setViewMode('grid'));
        this.updateViewToggle();
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
    }

    async loadInitialData() {
        try {
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

    createContentCard(item) {
        const duration = this.formatDuration(item.duration_seconds || 0);
        const categories = item.analysis?.category?.slice(0, 2) || ['General'];
        const hasAudio = item.media?.has_audio;
        const href = `/${item.file_stem}.json?v=2`;
        
        return `
            <div data-card data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-href="${href}" tabindex="0" class="group cursor-pointer bg-white/80 backdrop-blur-sm rounded-xl border border-slate-200/60 p-4 hover:bg-white hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200">
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
                                <div class="text-sm text-slate-500 mt-0.5 line-clamp-1">${this.escapeHtml(item.channel || '')}</div>
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
                                <button data-control data-play-btn title="Play audio" class="p-2 rounded-lg text-audio-600 hover:bg-audio-100 focus:ring-2 focus:ring-audio-500">
                                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 3c3.866 0 7 3.134 7 7v8a2 2 0 01-2 2h-1a1 1 0 01-1-1V12a1 1 0 00-1-1H10a1 1 0 00-1 1v7a1 1 0 01-1 1H7a2 2 0 01-2-2V10c0-3.866 3.134-7 7-7z"/></svg>
                                </button>
                                ` : ''}
                                <a data-control href="${href}" class="text-sm text-audio-600 hover:text-audio-700">View →</a>
                            </div>
                        </div>

                        <div class="mt-3 flex flex-wrap gap-2">
                            ${categories.map(cat => `
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-audio-100 text-audio-800">${this.escapeHtml(cat)}</span>
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
        return `
        <div data-card data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" data-href="${href}" tabindex="0" class="group cursor-pointer bg-white/80 rounded-xl border border-slate-200/60 hover:bg-white hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200 overflow-hidden">
            <div class="relative aspect-video bg-slate-100">
                ${item.thumbnail_url ? `<img src="${item.thumbnail_url}" alt="thumbnail" class="absolute inset-0 w-full h-full object-cover">` : ''}
            </div>
            <div class="p-3">
                <h3 class="text-sm font-semibold text-slate-800 group-hover:text-audio-700 line-clamp-2">${this.escapeHtml(item.title)}</h3>
                <div class="text-xs text-slate-500 mt-1 line-clamp-1">${this.escapeHtml(item.channel || '')}</div>
                <div class="mt-1 flex items-center gap-2 text-xs text-slate-500">
                    <span>${duration}</span>
                    <span>•</span>
                    <span>${item.analysis?.language || 'en'}</span>
                </div>
                <div class="mt-2 flex items-center justify-between">
                    <button data-control data-play-btn title="Play audio" class="p-1.5 rounded-md text-audio-600 hover:bg-audio-100">
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 3c3.866 0 7 3.134 7 7v8a2 2 0 01-2 2h-1a1 1 0 01-1-1V12a1 1 0 00-1-1H10a1 1 0 00-1 1v7a1 1 0 01-1 1H7a2 2 0 01-2-2V10c0-3.866 3.134-7 7-7z"/></svg>
                    </button>
                    <a data-control href="${href}" class="text-xs text-audio-600 hover:text-audio-700">View →</a>
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
            
            // Load and play audio
            this.audioElement.src = audioSrc;
            this.audioElement.load();
            
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
        if (this.currentAudio && !this.isPlaying) {
            this.audioElement.play().then(() => {
                this.isPlaying = true;
                this.updatePlayButton();
                this.updatePlayingCard();
            }).catch(error => {
                console.error('Auto-play failed:', error);
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
            this.totalTimeEl.textContent = this.formatDuration(duration);
            this.playerMeta.textContent = `${this.formatDuration(duration)} audio summary`;
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

    handleSortChange() {
        this.currentSort = this.sortSelect.value;
        this.currentPage = 1;
        this.loadContent();
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
        // Implementation for playing all filtered results
        console.log('Playing all results');
    }

    playNext() {
        // Implementation for next track
        console.log('Playing next');
    }

    playPrevious() {
        // Implementation for previous track
        console.log('Playing previous');
    }

    handleKeyboard(event) {
        // Space bar for play/pause
        if (event.code === 'Space' && this.currentAudio) {
            event.preventDefault();
            this.togglePlayPause();
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
