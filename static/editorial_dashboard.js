/* ============================================================
   YTV2 Editorial Dashboard — Phase 2
   ============================================================ */

(function () {
    'use strict';

    // ---- Inline helpers ----

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function formatDuration(seconds) {
        if (!seconds || seconds <= 0) return '';
        var h = Math.floor(seconds / 3600);
        var m = Math.floor((seconds % 3600) / 60);
        var s = Math.floor(seconds % 60);
        if (h > 0) {
            return h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
        }
        return m + ':' + String(s).padStart(2, '0');
    }

    function buildFilterQuery(params) {
        var parts = [];
        Object.keys(params).forEach(function (key) {
            var val = params[key];
            if (val === undefined || val === null || val === '') return;
            if (Array.isArray(val)) {
                val.forEach(function (v) { parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(v)); });
            } else {
                parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(val));
            }
        });
        return parts.length ? '?' + parts.join('&') : '';
    }

    function getCategories(item) {
        var analysis = item.analysis || {};
        if (Array.isArray(analysis.categories) && analysis.categories.length > 0) {
            return analysis.categories.map(function (c) { return c.category; });
        }
        if (Array.isArray(analysis.category)) return analysis.category;
        return [];
    }

    function getPrimaryCategory(item) {
        var cats = getCategories(item);
        return cats.length > 0 ? cats[0] : '';
    }

    function getExcerpt(text, maxLen) {
        if (!text) return '';
        var clean = text.replace(/<[^>]+>/g, '').trim();
        if (clean.length <= (maxLen || 180)) return clean;
        return clean.substring(0, maxLen || 180).replace(/\s+\S*$/, '') + '...';
    }

    function getThumbnail(item) {
        return item.thumbnail_url ||
            item.summary_image_url ||
            '/static/placeholder-thumb.png';
    }

    function getSourceLabel(item) {
        return item.source_label || item.source || '';
    }

    function timeAgo(dateStr) {
        if (!dateStr) return '';
        var d = new Date(dateStr);
        if (isNaN(d.getTime())) return '';
        var now = new Date();
        var diffMs = now - d;
        var diffMins = Math.floor(diffMs / 60000);
        if (diffMins < 60) return diffMins + 'm ago';
        var diffHrs = Math.floor(diffMins / 60);
        if (diffHrs < 24) return diffHrs + 'h ago';
        var diffDays = Math.floor(diffHrs / 24);
        if (diffDays < 30) return diffDays + 'd ago';
        var diffMonths = Math.floor(diffDays / 30);
        return diffMonths + 'mo ago';
    }

    // ---- Card factories ----

    function renderHeroCard(item) {
        var media = item.media || {};
        var hasAudio = !!media.has_audio;
        var duration = formatDuration(item.duration_seconds);
        var excerpt = getExcerpt(item.summary_text, 240);
        var thumb = getThumbnail(item);
        var sourceLabel = getSourceLabel(item);
        var channel = item.channel || item.channel_name || '';
        var category = getPrimaryCategory(item);
        var ago = timeAgo(item.indexed_at);

        return '<article class="ed-card ed-card-hero" data-video-id="' + escapeHtml(item.video_id || item.id) + '">' +
            '<div class="ed-card-hero__image">' +
                '<img src="' + escapeHtml(thumb) + '" alt="" loading="eager">' +
                (duration ? '<span class="ed-card__duration">' + duration + '</span>' : '') +
                (hasAudio ? '<span class="ed-card__audio-badge">Audio</span>' : '') +
            '</div>' +
            '<div class="ed-card-hero__body">' +
                '<div class="ed-card__meta">' +
                    (sourceLabel ? '<span class="ed-card__source">' + escapeHtml(sourceLabel) + '</span>' : '') +
                    (channel ? '<span class="ed-card__channel">' + escapeHtml(channel) + '</span>' : '') +
                    (ago ? '<span class="ed-card__time">' + ago + '</span>' : '') +
                '</div>' +
                '<h2 class="ed-card-hero__title">' + escapeHtml(item.title) + '</h2>' +
                (excerpt ? '<p class="ed-card-hero__excerpt">' + escapeHtml(excerpt) + '</p>' : '') +
                (category ? '<span class="ed-card__category-chip">' + escapeHtml(category) + '</span>' : '') +
                '<div class="ed-card__actions">' +
                    '<a class="ed-btn ed-btn--primary" href="/' + escapeHtml(item.video_id || item.file_stem) + '" data-action="read">Read</a>' +
                    (hasAudio ? '<button class="ed-btn ed-btn--secondary" data-action="listen">Listen</button>' : '') +
                    (item.canonical_url ? '<a class="ed-btn ed-btn--secondary" href="' + escapeHtml(item.canonical_url) + '" target="_blank" rel="noopener" data-action="watch">Watch</a>' : '') +
                '</div>' +
            '</div>' +
        '</article>';
    }

    function renderFeatureCard(item) {
        var media = item.media || {};
        var hasAudio = !!media.has_audio;
        var duration = formatDuration(item.duration_seconds);
        var excerpt = getExcerpt(item.summary_text, 120);
        var thumb = getThumbnail(item);
        var sourceLabel = getSourceLabel(item);
        var channel = item.channel || item.channel_name || '';
        var ago = timeAgo(item.indexed_at);

        return '<article class="ed-card ed-card-feature" data-video-id="' + escapeHtml(item.video_id || item.id) + '">' +
            '<div class="ed-card-feature__image">' +
                '<img src="' + escapeHtml(thumb) + '" alt="" loading="lazy">' +
                (duration ? '<span class="ed-card__duration">' + duration + '</span>' : '') +
                (hasAudio ? '<span class="ed-card__audio-badge">Audio</span>' : '') +
            '</div>' +
            '<div class="ed-card-feature__body">' +
                '<div class="ed-card__meta">' +
                    (sourceLabel ? '<span class="ed-card__source">' + escapeHtml(sourceLabel) + '</span>' : '') +
                    (channel ? '<span class="ed-card__channel">' + escapeHtml(channel) + '</span>' : '') +
                    (ago ? '<span class="ed-card__time">' + ago + '</span>' : '') +
                '</div>' +
                '<h3 class="ed-card-feature__title">' + escapeHtml(item.title) + '</h3>' +
                (excerpt ? '<p class="ed-card-feature__excerpt">' + escapeHtml(excerpt) + '</p>' : '') +
                '<div class="ed-card__actions">' +
                    '<a class="ed-btn ed-btn--sm" href="/' + escapeHtml(item.video_id || item.file_stem) + '" data-action="read">Read</a>' +
                    (item.canonical_url ? '<a class="ed-btn ed-btn--sm ed-btn--ghost" href="' + escapeHtml(item.canonical_url) + '" target="_blank" rel="noopener" data-action="watch">Watch</a>' : '') +
                '</div>' +
            '</div>' +
        '</article>';
    }

    function renderCompactCard(item) {
        var media = item.media || {};
        var hasAudio = !!media.has_audio;
        var duration = formatDuration(item.duration_seconds);
        var thumb = getThumbnail(item);
        var sourceLabel = getSourceLabel(item);
        var channel = item.channel || item.channel_name || '';
        var ago = timeAgo(item.indexed_at);

        return '<article class="ed-card ed-card-compact" data-video-id="' + escapeHtml(item.video_id || item.id) + '">' +
            '<div class="ed-card-compact__image">' +
                '<img src="' + escapeHtml(thumb) + '" alt="" loading="lazy">' +
                (duration ? '<span class="ed-card__duration ed-card__duration--sm">' + duration + '</span>' : '') +
            '</div>' +
            '<div class="ed-card-compact__body">' +
                '<h4 class="ed-card-compact__title">' + escapeHtml(item.title) + '</h4>' +
                '<div class="ed-card__meta">' +
                    (sourceLabel ? '<span class="ed-card__source">' + escapeHtml(sourceLabel) + '</span>' : '') +
                    (channel ? '<span class="ed-card__channel">' + escapeHtml(channel) + '</span>' : '') +
                    (ago ? '<span class="ed-card__time">' + ago + '</span>' : '') +
                    (hasAudio ? '<span class="ed-card__audio-indicator">&#9835;</span>' : '') +
                '</div>' +
            '</div>' +
        '</article>';
    }

    // ---- EditorialDashboard class ----

    // Filter keys that map to URL query params
    var URL_FILTER_KEYS = ['source', 'category', 'subcategory', 'channel', 'language', 'content_type', 'summary_type', 'has_audio'];

    class EditorialDashboard {
        constructor() {
            this.config = window.EDITORIAL_CONFIG || { features: {} };
            this.nasConfig = window.NAS_CONFIG || {};
            this.dashboardConfig = window.DASHBOARD_CONFIG || {};

            this.state = {
                items: [],
                allItems: [],       // accumulated items across pages
                page: 1,
                size: 50,
                total: 0,
                filters: {},
                search: '',
                sort: 'newest',
                loading: false,
                error: null,
                filterOptions: null,
                hasMore: true,
            };

            this.mounts = {
                topbar: document.getElementById('ed-topbar'),
                hero: document.getElementById('ed-hero'),
                sections: document.getElementById('ed-sections'),
                rail: document.getElementById('ed-rail'),
                player: document.getElementById('ed-player'),
            };
        }

        // ---- URL state ----

        readStateFromURL() {
            var params = new URLSearchParams(window.location.search);
            this.state.search = params.get('q') || '';
            this.state.sort = params.get('sort') || 'newest';
            this.state.page = parseInt(params.get('page'), 10) || 1;
            this.state.filters = {};

            for (var i = 0; i < URL_FILTER_KEYS.length; i++) {
                var key = URL_FILTER_KEYS[i];
                var val = params.get(key);
                if (val !== null && val !== '') {
                    this.state.filters[key] = val;
                }
            }
        }

        writeStateToURL() {
            var params = new URLSearchParams();
            if (this.state.search) params.set('q', this.state.search);
            if (this.state.sort && this.state.sort !== 'newest') params.set('sort', this.state.sort);
            for (var i = 0; i < URL_FILTER_KEYS.length; i++) {
                var key = URL_FILTER_KEYS[i];
                if (this.state.filters[key]) params.set(key, this.state.filters[key]);
            }
            var qs = params.toString();
            var url = window.location.pathname + (qs ? '?' + qs : '');
            history.replaceState(null, '', url);
        }

        // ---- Data loading ----

        async loadFilters() {
            try {
                var resp = await fetch('/api/filters');
                if (!resp.ok) return;
                this.state.filterOptions = await resp.json();
            } catch (e) {
                console.warn('[Editorial] Failed to load filters:', e);
            }
        }

        async loadContent() {
            this.state.loading = true;
            if (this.state.page === 1) {
                this.state.allItems = [];
                this.renderLoading();
            }

            var params = {
                page: this.state.page,
                size: this.state.size,
                sort: this.state.sort,
            };
            if (this.state.search) {
                params.q = this.state.search;
            }
            Object.keys(this.state.filters).forEach(function (key) {
                var val = this.state.filters[key];
                if (val) params[key] = val;
            }.bind(this));

            var url = '/api/reports' + buildFilterQuery(params);
            try {
                var resp = await fetch(url);
                if (!resp.ok) throw new Error('API returned ' + resp.status);
                var data = await resp.json();
                var newItems = data.reports || data.items || [];
                this.state.total = data.total_count || (data.pagination && data.pagination.total) || 0;

                if (this.state.page === 1) {
                    this.state.allItems = newItems;
                } else {
                    this.state.allItems = this.state.allItems.concat(newItems);
                }
                this.state.items = this.state.allItems;
                this.state.hasMore = this.state.allItems.length < this.state.total;

                console.log('[Editorial] Loaded', newItems.length, 'page', this.state.page,
                    '| total accumulated:', this.state.allItems.length, 'of', this.state.total);

                this.writeStateToURL();
                this.render();
            } catch (err) {
                this.state.error = err.message;
                console.error('[Editorial] loadContent failed:', err);
                this.renderError();
            } finally {
                this.state.loading = false;
            }
        }

        async loadMore() {
            if (this.state.loading || !this.state.hasMore) return;
            this.state.page++;
            await this.loadContent();
        }

        // ---- Rendering ----

        render() {
            var items = this.state.items;
            if (!items.length) {
                this.renderEmpty();
                return;
            }

            // Hero: first item only on page 1
            if (this.state.page === 1 || this.mounts.hero.children.length === 0) {
                var hero = items[0];
                if (this.mounts.hero) {
                    this.mounts.hero.innerHTML = renderHeroCard(hero);
                }
            }

            // Section grouping: items after hero, grouped by category
            var sectionItems = items.slice(1);
            var sections = this.groupByCategory(sectionItems);

            if (this.mounts.sections) {
                var html = '';
                var sectionOrder = Object.keys(sections);
                for (var i = 0; i < sectionOrder.length; i++) {
                    var cat = sectionOrder[i];
                    var catItems = sections[cat];
                    html += '<section class="ed-section">';
                    html += '<h2 class="ed-section__title">' + escapeHtml(cat) +
                        ' <span class="ed-section__count">' + catItems.length + '</span></h2>';
                    html += '<div class="ed-section__grid">';
                    for (var j = 0; j < catItems.length; j++) {
                        if (j < 2) {
                            html += renderFeatureCard(catItems[j]);
                        } else {
                            html += renderCompactCard(catItems[j]);
                        }
                    }
                    html += '</div></section>';
                }

                // Load more trigger
                if (this.state.hasMore) {
                    html += '<div id="ed-load-more" class="ed-load-more">';
                    html += '<button class="ed-btn ed-btn--secondary ed-load-more__btn">Load more</button>';
                    html += '<span class="ed-load-more__count">' + this.state.allItems.length + ' of ' + this.state.total + '</span>';
                    html += '</div>';
                } else if (this.state.total > 0) {
                    html += '<div class="ed-load-more"><span class="ed-load-more__count">All ' + this.state.total + ' items loaded</span></div>';
                }

                this.mounts.sections.innerHTML = html;
            }

            // Right rail: recent compact cards
            if (this.mounts.rail) {
                var railItems = sectionItems.slice(-10);
                var railHtml = '<h3 class="ed-rail__title">Recent</h3>';
                for (var k = 0; k < railItems.length; k++) {
                    railHtml += renderCompactCard(railItems[k]);
                }
                this.mounts.rail.innerHTML = railHtml;
            }

            // Sync filter UI state
            this.renderFilterChips();
            this.updateFilterButtonStates();
        }

        updateFilterButtonStates() {
            var buttons = document.querySelectorAll('.ed-filter-btn');
            for (var i = 0; i < buttons.length; i++) {
                var btn = buttons[i];
                var type = btn.dataset.filterType;
                var value = btn.dataset.filterValue;
                var isActive = this.state.filters[type] === value;
                btn.classList.toggle('ed-filter-btn--active', isActive);
            }
        }

        groupByCategory(items) {
            var groups = {};
            for (var i = 0; i < items.length; i++) {
                var cat = getPrimaryCategory(items[i]) || 'Uncategorized';
                if (!groups[cat]) groups[cat] = [];
                groups[cat].push(items[i]);
            }
            return groups;
        }

        renderTopbar() {
            var search = this.mounts.topbar;
            if (!search) return;

            var searchInput = search.querySelector('.ed-topbar__search');
            if (searchInput) {
                searchInput.innerHTML =
                    '<input type="text" class="ed-search__input" placeholder="Search summaries..." value="' +
                    escapeHtml(this.state.search) + '">';
            }

            var nav = search.querySelector('.ed-topbar__nav');
            if (nav) {
                var sortOpts = [
                    { value: 'newest', label: 'Newest' },
                    { value: 'oldest', label: 'Oldest' },
                ];
                var navHtml = '<select class="ed-sort__select">';
                for (var i = 0; i < sortOpts.length; i++) {
                    navHtml += '<option value="' + sortOpts[i].value + '"' +
                        (this.state.sort === sortOpts[i].value ? ' selected' : '') + '>' +
                        sortOpts[i].label + '</option>';
                }
                navHtml += '</select>';
                navHtml += '<a class="ed-topbar__link" href="/">Classic</a>';
                nav.innerHTML = navHtml;
            }
        }

        renderFilterChips() {
            var existing = document.getElementById('ed-filter-chips');
            if (existing) existing.remove();

            var activeFilters = Object.keys(this.state.filters).filter(
                function (k) { return this.state.filters[k]; }.bind(this)
            );
            if (!activeFilters.length && !this.state.search) return;

            var chipContainer = document.createElement('div');
            chipContainer.id = 'ed-filter-chips';
            chipContainer.className = 'ed-filter-chips';

            if (this.state.search) {
                chipContainer.innerHTML += '<span class="ed-chip" data-filter-key="search">' +
                    '"' + escapeHtml(this.state.search) + '" <button class="ed-chip__remove">&times;</button></span>';
            }

            for (var i = 0; i < activeFilters.length; i++) {
                var key = activeFilters[i];
                var val = this.state.filters[key];
                var label = this.getFilterLabel(key, val);
                chipContainer.innerHTML += '<span class="ed-chip" data-filter-key="' + escapeHtml(key) + '">' +
                    escapeHtml(label) +
                    ' <button class="ed-chip__remove">&times;</button></span>';
            }

            var main = document.getElementById('ed-main');
            if (main) main.insertBefore(chipContainer, main.firstChild);
        }

        getFilterLabel(key, value) {
            var opts = this.state.filterOptions || {};
            // Try to find the human-readable label from filter options
            var lists = {
                source: opts.source || opts.content_source,
                category: (opts.categories || []).map(function (c) { return { value: c.value, label: c.value }; }),
                subcategory: this.flattenSubcategories(opts.categories),
                channel: opts.channels,
                language: opts.languages,
                summary_type: opts.summary_type,
            };
            var list = lists[key];
            if (list) {
                for (var i = 0; i < list.length; i++) {
                    if (String(list[i].value) === String(value)) {
                        return (list[i].label || list[i].value);
                    }
                }
            }
            return key + ': ' + value;
        }

        flattenSubcategories(categories) {
            if (!categories) return [];
            var result = [];
            for (var i = 0; i < categories.length; i++) {
                var subs = categories[i].subcategories || [];
                for (var j = 0; j < subs.length; j++) {
                    result.push(subs[j]);
                }
            }
            return result;
        }

        renderQuickFilters() {
            var filters = this.state.filterOptions;
            if (!filters) return;

            // Remove existing quick filters if re-rendering
            var existing = document.getElementById('ed-quick-filters');
            if (existing) existing.remove();

            var container = document.createElement('div');
            container.id = 'ed-quick-filters';
            container.className = 'ed-quick-filters';

            // Source filters
            var sources = filters.source || filters.content_source || [];
            if (sources.length > 1) {
                var html = '<div class="ed-filter-group"><span class="ed-filter-group__label">Source</span>';
                for (var i = 0; i < sources.length; i++) {
                    var s = sources[i];
                    var isActive = this.state.filters.source === s.value;
                    html += '<button class="ed-filter-btn' + (isActive ? ' ed-filter-btn--active' : '') +
                        '" data-filter-type="source" data-filter-value="' + escapeHtml(s.value) + '">' +
                        escapeHtml(s.label) + ' <small>' + s.count + '</small></button>';
                }
                html += '</div>';
                container.innerHTML += html;
            }

            // Category filters (top 6)
            var categories = (filters.categories || []).slice(0, 6);
            if (categories.length > 1) {
                var catHtml = '<div class="ed-filter-group"><span class="ed-filter-group__label">Category</span>';
                for (var j = 0; j < categories.length; j++) {
                    var c = categories[j];
                    var isCatActive = this.state.filters.category === c.value;
                    catHtml += '<button class="ed-filter-btn' + (isCatActive ? ' ed-filter-btn--active' : '') +
                        '" data-filter-type="category" data-filter-value="' + escapeHtml(c.value) + '">' +
                        escapeHtml(c.value) + ' <small>' + c.count + '</small></button>';
                }
                catHtml += '</div>';
                container.innerHTML += catHtml;
            }

            // Content type filter
            var contentTypes = filters.content_type || [];
            if (contentTypes.length > 1) {
                var ctHtml = '<div class="ed-filter-group"><span class="ed-filter-group__label">Type</span>';
                for (var ct = 0; ct < contentTypes.length; ct++) {
                    var t = contentTypes[ct];
                    var isTypeActive = this.state.filters.content_type === t.value;
                    ctHtml += '<button class="ed-filter-btn' + (isTypeActive ? ' ed-filter-btn--active' : '') +
                        '" data-filter-type="content_type" data-filter-value="' + escapeHtml(t.value) + '">' +
                        escapeHtml(t.value) + ' <small>' + t.count + '</small></button>';
                }
                ctHtml += '</div>';
                container.innerHTML += ctHtml;
            }

            // Has audio filter
            var audioOpts = filters.has_audio || [];
            if (audioOpts.length > 1) {
                var auHtml = '<div class="ed-filter-group"><span class="ed-filter-group__label">Audio</span>';
                for (var au = 0; au < audioOpts.length; au++) {
                    var a = audioOpts[au];
                    if (a.value === true) {
                        var isAudioActive = this.state.filters.has_audio === 'true';
                        auHtml += '<button class="ed-filter-btn' + (isAudioActive ? ' ed-filter-btn--active' : '') +
                            '" data-filter-type="has_audio" data-filter-value="true">' +
                            'With Audio <small>' + a.count + '</small></button>';
                    }
                }
                auHtml += '</div>';
                container.innerHTML += auHtml;
            }

            var hero = this.mounts.hero;
            if (hero && hero.parentNode) {
                hero.parentNode.insertBefore(container, hero);
            }
        }

        renderLoading() {
            if (this.mounts.hero) {
                this.mounts.hero.innerHTML = '<div class="ed-loading">Loading...</div>';
            }
            if (this.mounts.sections) this.mounts.sections.innerHTML = '';
            if (this.mounts.rail) this.mounts.rail.innerHTML = '';
        }

        renderLoadingMore() {
            var trigger = document.getElementById('ed-load-more');
            if (trigger) {
                trigger.innerHTML = '<div class="ed-loading" style="padding:1rem">Loading more...</div>';
            }
        }

        renderError() {
            if (this.mounts.hero) {
                this.mounts.hero.innerHTML =
                    '<div class="ed-loading" style="color:#ef4444">Error: ' +
                    escapeHtml(this.state.error) + '</div>';
            }
        }

        renderEmpty() {
            if (this.mounts.hero) {
                this.mounts.hero.innerHTML = '<div class="ed-loading">No reports found</div>';
            }
        }

        // ---- Event handling ----

        bindEvents() {
            // Search input
            document.addEventListener('input', function (e) {
                if (e.target.classList.contains('ed-search__input')) {
                    this.debounceSearch(e.target.value);
                }
            }.bind(this));

            // Sort change
            document.addEventListener('change', function (e) {
                if (e.target.classList.contains('ed-sort__select')) {
                    this.state.sort = e.target.value;
                    this.state.page = 1;
                    this.loadContent();
                }
            }.bind(this));

            // Click delegation
            document.addEventListener('click', function (e) {
                // Filter buttons
                var btn = e.target.closest('.ed-filter-btn');
                if (btn) {
                    var type = btn.dataset.filterType;
                    var value = btn.dataset.filterValue;
                    if (this.state.filters[type] === value) {
                        delete this.state.filters[type];
                    } else {
                        this.state.filters[type] = value;
                    }
                    this.state.page = 1;
                    this.loadContent();
                    return;
                }

                // Filter chip remove
                var chip = e.target.closest('.ed-chip__remove');
                if (chip) {
                    var chipEl = chip.closest('.ed-chip');
                    if (chipEl) {
                        var key = chipEl.dataset.filterKey;
                        if (key === 'search') {
                            this.state.search = '';
                            var input = document.querySelector('.ed-search__input');
                            if (input) input.value = '';
                        } else {
                            delete this.state.filters[key];
                        }
                        this.state.page = 1;
                        this.loadContent();
                    }
                    return;
                }

                // Load more button
                var loadMoreBtn = e.target.closest('.ed-load-more__btn');
                if (loadMoreBtn) {
                    this.loadMore();
                    return;
                }

                // Card click (navigate to report)
                var card = e.target.closest('.ed-card');
                if (card && !e.target.closest('.ed-btn') && !e.target.closest('a')) {
                    var videoId = card.dataset.videoId;
                    if (videoId) {
                        window.location.href = '/' + videoId;
                    }
                }
            }.bind(this));

            // Browser back/forward
            window.addEventListener('popstate', function () {
                this.readStateFromURL();
                this.state.page = 1;
                this.loadContent();
            }.bind(this));

            // Scroll-based progressive load (supplements the button)
            this._scrollHandler = function () {
                if (this.state.loading || !this.state.hasMore) return;
                var sentinel = document.getElementById('ed-load-more');
                if (!sentinel) return;
                var rect = sentinel.getBoundingClientRect();
                if (rect.top < window.innerHeight + 400) {
                    this.loadMore();
                }
            }.bind(this);
            window.addEventListener('scroll', this._scrollHandler, { passive: true });
        }

        debounceSearch(query) {
            clearTimeout(this._searchTimer);
            this._searchTimer = setTimeout(function () {
                this.state.search = query.trim();
                this.state.page = 1;
                this.loadContent();
            }.bind(this), 350);
        }
    }

    // ---- Bootstrap ----
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    async function init() {
        console.log('[Editorial] Initializing...');
        var app = new EditorialDashboard();
        app.readStateFromURL();
        app.bindEvents();
        app.renderTopbar();
        await app.loadFilters();
        app.renderQuickFilters();
        await app.loadContent();
        window.__editorialApp = app;
    }
})();
