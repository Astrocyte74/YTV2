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
        
        this.initializeElements();
        this.bindEvents();
        this.loadInitialData();
    }

    initializeElements() {
        // Audio elements
        this.audioElement = document.getElementById('audioElement');
        this.audioPlayerContainer = document.getElementById('audioPlayerContainer');
        
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
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
    }

    async loadInitialData() {
        try {
            await Promise.all([
                this.loadFilters(),
                this.loadContent()
            ]);
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
            
            this.renderContent(data.data);
            this.renderPagination(data.pagination);
            this.updateResultsInfo(data.pagination);
        } catch (error) {
            console.error('Failed to load content:', error);
            this.showError('Failed to load content');
        }
    }

    renderContent(items) {
        this.contentGrid.innerHTML = items.map(item => this.createContentCard(item)).join('');
        
        // Bind play buttons
        this.contentGrid.querySelectorAll('[data-play-btn]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const reportId = e.target.closest('[data-report-id]').dataset.reportId;
                this.playAudio(reportId);
            });
        });
        
        // Bind add to queue buttons
        this.contentGrid.querySelectorAll('[data-queue-btn]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const reportId = e.target.closest('[data-report-id]').dataset.reportId;
                this.addToQueue(reportId);
            });
        });
    }

    createContentCard(item) {
        const duration = this.formatDuration(item.duration_seconds || 0);
        const categories = item.analysis?.category?.slice(0, 2) || ['General'];
        const hasAudio = item.media?.has_audio;
        
        return `
            <div data-report-id="${item.file_stem}" data-video-id="${item.video_id || ''}" class="group bg-white/70 backdrop-blur-sm rounded-xl border border-slate-200/50 p-6 hover:bg-white/90 hover:shadow-lg transition-all duration-300">
                <!-- Header -->
                <div class="flex items-start justify-between mb-4">
                    <div class="flex-1 min-w-0 mr-4">
                        <h3 class="text-lg font-semibold text-slate-800 group-hover:text-audio-700 transition-colors line-clamp-2 mb-2">
                            <a href="/${item.file_stem}.json?v=2" class="hover:underline">${this.escapeHtml(item.title)}</a>
                        </h3>
                        <div class="flex items-center space-x-2 text-sm text-slate-500">
                            <span>${duration}</span>
                            <span>•</span>
                            <span>${item.analysis?.complexity_level || 'Intermediate'}</span>
                            <span>•</span>
                            <span>${item.analysis?.language || 'en'}</span>
                        </div>
                    </div>
                    ${item.thumbnail_url ? `
                    <img src="${item.thumbnail_url}" alt="thumbnail" class="w-12 h-12 rounded-lg object-cover flex-shrink-0"/>
                    ` : ''}
                    
                    <!-- Audio Status -->
                    ${hasAudio ? `
                        <div class="flex-shrink-0 w-12 h-12 bg-gradient-to-r from-audio-400 to-audio-600 rounded-lg flex items-center justify-center shadow-sm">
                            <svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/>
                            </svg>
                        </div>
                    ` : `
                        <div class="flex-shrink-0 w-12 h-12 bg-slate-200 rounded-lg flex items-center justify-center">
                            <svg class="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                            </svg>
                        </div>
                    `}
                </div>

                <!-- Categories -->
                <div class="flex flex-wrap gap-2 mb-4">
                    ${categories.map(cat => `
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-audio-100 text-audio-800">
                            ${this.escapeHtml(cat)}
                        </span>
                    `).join('')}
                </div>

                <!-- Key Topics (if available) -->
                ${item.analysis?.key_topics?.length ? `
                    <div class="mb-4">
                        <p class="text-sm text-slate-600 line-clamp-2">
                            Topics: ${item.analysis.key_topics.slice(0, 3).join(', ')}
                        </p>
                    </div>
                ` : ''}

                <!-- Actions -->
                <div class="flex items-center justify-between pt-4 border-t border-slate-100">
                    ${hasAudio ? `
                        <button data-play-btn 
                                class="inline-flex items-center space-x-2 bg-audio-500 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-audio-600 transition-colors">
                            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M8 5v14l11-7z"/>
                            </svg>
                            <span>Play Audio</span>
                        </button>
                        <a href="/${item.file_stem}.json?v=2" class="text-sm text-audio-600 hover:text-audio-700 transition-colors">View Summary →</a>
                        <button data-queue-btn 
                                class="inline-flex items-center space-x-2 text-slate-600 hover:text-audio-600 transition-colors">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                            </svg>
                            <span class="text-sm">Add to Queue</span>
                        </button>
                    ` : `
                        <span class="text-sm text-slate-500">No audio available</span>
                        <a href="/${item.file_stem}.json" 
                           class="text-sm text-audio-600 hover:text-audio-700 transition-colors">
                            View Report →
                        </a>
                    `}
                </div>
            </div>
        `;
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

            // Show audio player if hidden
            this.audioPlayerContainer.classList.remove('hidden');
            
            // Update player info
            this.playerTitle.textContent = title;
            this.playerMeta.textContent = 'Loading...';
            
            // Load and play audio
            this.audioElement.src = audioSrc;
            this.audioElement.load();
            
            // Update now playing preview
            this.updateNowPlayingPreview();
            
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
