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
}

function generateReportCard(report) {
    const thumbnailHTML = report.thumbnail_url 
        ? `<img src="${report.thumbnail_url}" alt="Video thumbnail" loading="lazy">`
        : `<div class="thumbnail-fallback">📺</div>`;
    
    return `
        <div class="report-card" data-title="${report.title}" data-channel="${report.channel}" data-model="${report.model}">
            <div class="report-thumbnail">
                ${thumbnailHTML}
                <div class="report-overlay">
                    <button class="play-button" onclick="openReport('${report.filename}')">
                        <svg viewBox="0 0 20 20" fill="currentColor">
                            <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.841z" />
                        </svg>
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
            if (e.target.closest('.play-button')) return; // Let the play button handle its own click
            
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
            cb.closest('.report-card').querySelector('.play-button').getAttribute('onclick').match(/'([^']+)'/)[1]
        );
        
        // Make delete request
        fetch('/delete-reports', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: filenames })
        }).then(() => {
            location.reload();
        }).catch(console.error);
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
function setupMiniPlayerControls() {
    const miniPlayer = document.getElementById('miniPlayer');
    const closePlayer = document.getElementById('closePlayer');
    const playBtn = document.getElementById('playBtn');
    
    if (closePlayer) {
        closePlayer.addEventListener('click', closeMiniPlayer);
    }
    
    if (playBtn) {
        playBtn.addEventListener('click', togglePlayback);
    }
}

function showMiniPlayer(videoData) {
    const miniPlayer = document.getElementById('miniPlayer');
    if (miniPlayer) {
        miniPlayer.style.display = 'block';
        // Update mini player content with videoData
    }
}

function closeMiniPlayer() {
    const miniPlayer = document.getElementById('miniPlayer');
    if (miniPlayer) {
        miniPlayer.style.display = 'none';
    }
}

function togglePlayback() {
    // Implement playback toggle logic
    console.log('Toggle playback');
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

// Export functions for global access
window.openReport = openReport;
window.handleSelectAll = handleSelectAll;
window.handleDelete = handleDelete;
window.openFilters = openFilters;
window.closeFilters = closeFilters;