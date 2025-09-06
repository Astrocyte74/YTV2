// Dashboard JavaScript - Modern 2025 YouTube Reports Dashboard
document.addEventListener('DOMContentLoaded', function() {
    // Initialize dashboard
    initializeDashboard();
    
    // Setup event listeners
    setupEventListeners();
    
    // Load and display reports
    loadReports();
});

function initializeDashboard() {
    console.log('🚀 Dashboard initialized');
    updateReportCount();
}

function setupEventListeners() {
    // Search functionality
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', handleSearch);
    }
    
    // Sort functionality
    const sortOrder = document.getElementById('sortOrder');
    if (sortOrder) {
        sortOrder.addEventListener('change', handleSort);
    }
    
    // Filter functionality
    const filtersBtn = document.getElementById('filtersBtn');
    if (filtersBtn) {
        filtersBtn.addEventListener('click', openFilters);
    }
    
    // Select all functionality
    const selectAllBtn = document.getElementById('selectAllBtn');
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', handleSelectAll);
    }
    
    // Delete functionality
    const deleteBtn = document.getElementById('deleteBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', handleDelete);
    }
    
    // Mini player controls
    setupMiniPlayerControls();
    
    // Filter drawer controls
    setupFilterDrawer();
}

function loadReports() {
    const reportsGrid = document.getElementById('reportsGrid');
    if (!reportsGrid) return;
    
    const reports = window.REPORTS_DATA || [];
    
    if (reports.length === 0) {
        reportsGrid.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📭</div>
                <h3>No Reports Available</h3>
                <p>Send a YouTube URL to the bot to get started.</p>
            </div>
        `;
        return;
    }
    
    // Generate report cards
    const reportsHTML = reports.map(report => generateReportCard(report)).join('');
    reportsGrid.innerHTML = reportsHTML;
    
    // Setup card interactions
    setupReportCards();
    
    // Setup checkbox event listeners
    document.querySelectorAll('.report-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function(e) {
            e.stopPropagation(); // Prevent event from bubbling up to card click
            updateDeleteButton();
        });
        checkbox.addEventListener('click', function(e) {
            e.stopPropagation(); // Prevent event from bubbling up to card click
        });
    });
}

function generateReportCard(report) {
    const thumbnailHTML = report.thumbnail_url 
        ? `<img src="${report.thumbnail_url}" alt="Video thumbnail" loading="lazy">`
        : `<div class="thumbnail-fallback">📺</div>`;
    
    // Ensure we have video data for mini-player
    const videoData = {
        url: report.url || report.video_url,
        video_id: report.video_id,
        title: report.title,
        channel: report.channel,
        duration: report.duration || 0,
        thumbnail_url: report.thumbnail_url
    };
    
    return `
        <div class="report-card" 
             data-title="${report.title}" 
             data-channel="${report.channel}" 
             data-model="${report.model}"
             data-video-data='${JSON.stringify(videoData).replace(/'/g, "&#39;")}'>
            <div class="report-checkbox-container">
                <input type="checkbox" class="report-checkbox" data-filename="${report.filename}">
            </div>
            <div class="report-thumbnail">
                ${thumbnailHTML}
                <div class="report-overlay">
                    <button class="play-button" onclick="openReport('${report.filename}')">
                        <svg viewBox="0 0 20 20" fill="currentColor">
                            <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.841z" />
                        </svg>
                    </button>
                    <button class="mini-play-button" onclick="launchMiniPlayer(this)" title="Play in mini-player">
                        <svg viewBox="0 0 20 20" fill="currentColor">
                            <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.841z" />
                        </svg>
                        <span class="mini-icon">🎬</span>
                    </button>
                </div>
            </div>
            <div class="report-content">
                <div class="report-header">
                    <div class="model-badge">${report.model}</div>
                </div>
                <h3 class="report-title">${report.title}</h3>
                <div class="report-meta">
                    <span>📺 ${report.channel}</span>
                    <span>📅 ${report.created_date}</span>
                    <span>⏰ ${report.created_time}</span>
                </div>
                <p class="report-summary">${report.summary_preview}</p>
            </div>
        </div>
    `;
}

function setupReportCards() {
    const reportCards = document.querySelectorAll('.report-card');
    reportCards.forEach(card => {
        card.addEventListener('click', function(e) {
            if (e.target.closest('.play-button') || e.target.closest('.report-checkbox')) return; // Let the play button and checkbox handle their own clicks
            
            const filename = this.querySelector('.play-button').getAttribute('onclick').match(/'([^']+)'/)[1];
            openReport(filename);
        });
    });
}

function openReport(filename) {
    window.location.href = `/${filename}`;
}

function handleSearch() {
    const searchTerm = this.value.toLowerCase();
    const reportCards = document.querySelectorAll('.report-card');
    
    reportCards.forEach(card => {
        const title = card.dataset.title.toLowerCase();
        const channel = card.dataset.channel.toLowerCase();
        const model = card.dataset.model.toLowerCase();
        
        const matches = title.includes(searchTerm) || 
                       channel.includes(searchTerm) || 
                       model.includes(searchTerm);
        
        card.style.display = matches ? 'block' : 'none';
    });
    
    updateReportCount();
}

function handleSort() {
    const sortValue = this.value;
    const reportsGrid = document.getElementById('reportsGrid');
    const reportCards = Array.from(reportsGrid.querySelectorAll('.report-card'));
    
    reportCards.sort((a, b) => {
        switch(sortValue) {
            case 'title':
                return a.dataset.title.localeCompare(b.dataset.title);
            case 'oldest':
                return parseFloat(a.dataset.timestamp || '0') - parseFloat(b.dataset.timestamp || '0');
            case 'newest':
            default:
                return parseFloat(b.dataset.timestamp || '0') - parseFloat(a.dataset.timestamp || '0');
        }
    });
    
    // Re-append sorted cards
    reportCards.forEach(card => reportsGrid.appendChild(card));
}

function updateReportCount() {
    const visibleCards = document.querySelectorAll('.report-card:not([style*="display: none"])');
    const totalCards = document.querySelectorAll('.report-card');
    const countElement = document.getElementById('reportCount');
    
    if (countElement) {
        const visibleCount = visibleCards.length;
        const totalCount = totalCards.length;
        countElement.textContent = visibleCount === totalCount 
            ? `${totalCount} reports` 
            : `${visibleCount} of ${totalCount} reports`;
    }
}

function handleSelectAll() {
    const checkboxes = document.querySelectorAll('.report-checkbox');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    
    checkboxes.forEach(cb => cb.checked = !allChecked);
    updateDeleteButton();
}

function handleDelete() {
    const checkedBoxes = document.querySelectorAll('.report-checkbox:checked');
    if (checkedBoxes.length === 0) return;
    
    if (confirm(`Delete ${checkedBoxes.length} selected reports?`)) {
        const filenames = Array.from(checkedBoxes).map(cb => 
            cb.getAttribute('data-filename')
        );
        
        // Make delete request
        fetch('/delete-reports', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: filenames })
        }).then(response => {
            if (response.ok) {
                location.reload();
            } else {
                console.error('Delete failed:', response.status);
                alert('Failed to delete some reports. Check console for details.');
            }
        }).catch(error => {
            console.error('Delete error:', error);
            alert('Failed to delete reports. Check console for details.');
        });
    }
}

function updateDeleteButton() {
    const deleteBtn = document.getElementById('deleteBtn');
    const checkedCount = document.querySelectorAll('.report-checkbox:checked').length;
    
    if (deleteBtn) {
        deleteBtn.disabled = checkedCount === 0;
        deleteBtn.textContent = checkedCount > 0 ? `Delete (${checkedCount})` : 'Delete';
    }
}

// Filter Drawer Functions
function setupFilterDrawer() {
    const filterDrawer = document.getElementById('filterDrawer');
    const filterBackdrop = document.getElementById('filterBackdrop');
    const filterClose = document.getElementById('filterClose');
    
    if (filterBackdrop) {
        filterBackdrop.addEventListener('click', closeFilters);
    }
    
    if (filterClose) {
        filterClose.addEventListener('click', closeFilters);
    }
}

function openFilters() {
    const filterDrawer = document.getElementById('filterDrawer');
    if (filterDrawer) {
        filterDrawer.classList.add('open');
        populateFilters();
    }
}

function closeFilters() {
    const filterDrawer = document.getElementById('filterDrawer');
    if (filterDrawer) {
        filterDrawer.classList.remove('open');
    }
}

function populateFilters() {
    const reports = window.REPORTS_DATA || [];
    const models = [...new Set(reports.map(r => r.model))];
    const channels = [...new Set(reports.map(r => r.channel))];
    
    const filterContent = document.getElementById('filterContent');
    if (!filterContent) return;
    
    filterContent.innerHTML = `
        <div class="filter-group">
            <h4>🤖 AI Models</h4>
            <div class="filter-options">
                ${models.map(model => `
                    <label class="filter-option">
                        <input type="checkbox" value="${model}" checked>
                        <span>${model}</span>
                    </label>
                `).join('')}
            </div>
        </div>
        
        <div class="filter-group">
            <h4>📺 Channels</h4>
            <div class="filter-options">
                ${channels.map(channel => `
                    <label class="filter-option">
                        <input type="checkbox" value="${channel}" checked>
                        <span>${channel}</span>
                    </label>
                `).join('')}
            </div>
        </div>
    `;
}

// Mini Player Functions
let currentVideoData = null;
let currentVideoElement = null;
let isPlaying = false;

function setupMiniPlayerControls() {
    const closePlayer = document.getElementById('closePlayer');
    const playBtn = document.getElementById('playBtn');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    
    if (closePlayer) {
        closePlayer.addEventListener('click', closeMiniPlayer);
    }
    
    if (playBtn) {
        playBtn.addEventListener('click', togglePlayback);
    }
    
    if (prevBtn) {
        prevBtn.addEventListener('click', playPrevious);
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', playNext);
    }
}

function showMiniPlayer(videoData) {
    const miniPlayer = document.getElementById('miniPlayer');
    const titleElement = document.getElementById('miniPlayerTitle');
    const totalTimeElement = document.getElementById('totalTime');
    
    if (!miniPlayer) return;
    
    currentVideoData = videoData;
    
    // Update mini player content
    if (titleElement && videoData.title) {
        titleElement.textContent = videoData.title;
    }
    
    if (totalTimeElement && videoData.duration) {
        totalTimeElement.textContent = formatDuration(videoData.duration);
    }
    
    // Create embedded YouTube player
    createVideoPlayer(videoData);
    
    // Show the mini player with mobile fixes
    miniPlayer.style.display = 'block';
    miniPlayer.classList.add('active');
    
    // Force reflow on mobile devices
    miniPlayer.offsetHeight;
    
    // Add slide-up animation with mobile-specific delay
    const isMobile = window.innerWidth <= 640;
    const delay = isMobile ? 100 : 50;
    
    setTimeout(() => {
        miniPlayer.classList.add('visible');
        miniPlayer.classList.add('show'); // Ensure both classes are added
        
        // Double-check visibility on mobile
        if (isMobile) {
            setTimeout(() => {
                if (!miniPlayer.classList.contains('visible')) {
                    console.log('Mobile mini-player fix: re-adding visibility classes');
                    miniPlayer.classList.add('visible', 'show');
                    miniPlayer.style.transform = 'translate3d(0, 0, 0)';
                    miniPlayer.style.webkitTransform = 'translate3d(0, 0, 0)';
                }
            }, 200);
        }
    }, delay);
}

function closeMiniPlayer() {
    const miniPlayer = document.getElementById('miniPlayer');
    
    if (miniPlayer) {
        miniPlayer.classList.remove('visible');
        
        setTimeout(() => {
            miniPlayer.style.display = 'none';
            miniPlayer.classList.remove('active');
            
            // Clean up video element
            if (currentVideoElement) {
                currentVideoElement.remove();
                currentVideoElement = null;
            }
            
            currentVideoData = null;
            isPlaying = false;
            updatePlayButton();
        }, 300);
    }
}

function createVideoPlayer(videoData) {
    // Clean up existing video element
    if (currentVideoElement) {
        currentVideoElement.remove();
    }
    
    // Extract video ID from URL
    const videoId = extractVideoId(videoData.url || videoData.video_id);
    if (!videoId) return;
    
    // Create YouTube iframe for thumbnail/preview
    // Note: Actual playback would require YouTube API integration
    // For now, we'll create a preview that opens YouTube in new tab
    currentVideoElement = document.createElement('div');
    currentVideoElement.className = 'video-preview';
    currentVideoElement.innerHTML = `
        <div class="video-thumbnail" onclick="openVideoInNewTab('${videoData.url}')">
            <img src="https://img.youtube.com/vi/${videoId}/maxresdefault.jpg" 
                 alt="Video thumbnail" 
                 onerror="this.src='https://img.youtube.com/vi/${videoId}/hqdefault.jpg'">
            <div class="play-overlay">
                <svg viewBox="0 0 24 24" fill="white" width="48" height="48">
                    <path d="M8 5v14l11-7z"/>
                </svg>
            </div>
        </div>
    `;
    
    // Append to mini player (hidden for now, just for functionality)
    const miniPlayer = document.getElementById('miniPlayer');
    if (miniPlayer) {
        currentVideoElement.style.display = 'none'; // Hide for minimal design
        miniPlayer.appendChild(currentVideoElement);
    }
}

function togglePlayback() {
    if (!currentVideoData) return;
    
    // For demo purposes, this opens the video in a new tab
    // Real implementation would integrate with YouTube API
    const videoId = extractVideoId(currentVideoData.url || currentVideoData.video_id);
    if (videoId) {
        openVideoInNewTab(currentVideoData.url);
        
        // Simulate playback state for UI feedback
        isPlaying = !isPlaying;
        updatePlayButton();
        
        if (isPlaying) {
            startProgressSimulation();
        }
    }
}

function updatePlayButton() {
    const playBtn = document.getElementById('playBtn');
    const playIcon = playBtn?.querySelector('.play-icon');
    const pauseIcon = playBtn?.querySelector('.pause-icon');
    
    if (playIcon && pauseIcon) {
        if (isPlaying) {
            playIcon.style.display = 'none';
            pauseIcon.style.display = 'block';
        } else {
            playIcon.style.display = 'block';
            pauseIcon.style.display = 'none';
        }
    }
}

function startProgressSimulation() {
    // Simulate progress for demo purposes
    let progress = 0;
    const duration = currentVideoData?.duration || 300; // fallback to 5 minutes
    
    const updateProgress = () => {
        if (!isPlaying || progress >= duration) {
            isPlaying = false;
            updatePlayButton();
            return;
        }
        
        progress += 1;
        const progressPercent = (progress / duration) * 100;
        
        // Update progress bar
        const progressFill = document.querySelector('.progress-fill');
        if (progressFill) {
            progressFill.style.width = `${progressPercent}%`;
        }
        
        // Update current time display
        const currentTimeElement = document.getElementById('currentTime');
        if (currentTimeElement) {
            currentTimeElement.textContent = formatDuration(progress);
        }
        
        setTimeout(updateProgress, 1000);
    };
    
    if (isPlaying) {
        updateProgress();
    }
}

function playPrevious() {
    const reports = window.REPORTS_DATA || [];
    if (!currentVideoData || reports.length <= 1) return;
    
    // Find current report index
    const currentIndex = reports.findIndex(report => 
        report.url === currentVideoData.url || report.video_id === currentVideoData.video_id
    );
    
    if (currentIndex > 0) {
        const previousReport = reports[currentIndex - 1];
        showMiniPlayer(previousReport);
    } else {
        // Loop to last report
        const lastReport = reports[reports.length - 1];
        showMiniPlayer(lastReport);
    }
}

function playNext() {
    const reports = window.REPORTS_DATA || [];
    if (!currentVideoData || reports.length <= 1) return;
    
    // Find current report index
    const currentIndex = reports.findIndex(report => 
        report.url === currentVideoData.url || report.video_id === currentVideoData.video_id
    );
    
    if (currentIndex < reports.length - 1) {
        const nextReport = reports[currentIndex + 1];
        showMiniPlayer(nextReport);
    } else {
        // Loop to first report
        const firstReport = reports[0];
        showMiniPlayer(firstReport);
    }
}

function extractVideoId(url) {
    if (!url) return null;
    
    const patterns = [
        /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
        /^([a-zA-Z0-9_-]{11})$/ // Just video ID
    ];
    
    for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match) return match[1];
    }
    
    return null;
}

function openVideoInNewTab(url) {
    if (url) {
        window.open(url, '_blank', 'noopener,noreferrer');
    }
}

function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '0:00';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}

// Utility Functions
function debounce(func, wait) {
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

// Launch Mini Player Function
function launchMiniPlayer(buttonElement) {
    const card = buttonElement.closest('.report-card');
    if (!card) return;
    
    const videoDataAttr = card.getAttribute('data-video-data');
    if (!videoDataAttr) return;
    
    try {
        const videoData = JSON.parse(videoDataAttr.replace(/&#39;/g, "'"));
        showMiniPlayer(videoData);
    } catch (e) {
        console.error('Error parsing video data:', e);
        
        // Fallback: create video data from card attributes
        const fallbackVideoData = {
            title: card.getAttribute('data-title'),
            channel: card.getAttribute('data-channel'),
            url: '', // Would need to be provided in the report data
            duration: 0
        };
        
        if (fallbackVideoData.title) {
            showMiniPlayer(fallbackVideoData);
        }
    }
}

// Export functions for global access
window.openReport = openReport;
window.handleSelectAll = handleSelectAll;
window.handleDelete = handleDelete;
window.openFilters = openFilters;
window.closeFilters = closeFilters;
window.launchMiniPlayer = launchMiniPlayer;
window.showMiniPlayer = showMiniPlayer;
window.closeMiniPlayer = closeMiniPlayer;