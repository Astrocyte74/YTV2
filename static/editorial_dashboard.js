/* ============================================================
   YTV2 Editorial Dashboard — Phase 3
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

    function renderRailCard(item) {
        var thumb = item.thumbnail_url || item.summary_image_url || '';
        var sourceLabel = item.source_label || item.source || '';
        var channel = item.channel || item.channel_name || '';
        var duration = formatDuration(item.duration_seconds);
        var ago = timeAgo(item.indexed_at);
        var hasAudio = item.media && item.media.has_audio;

        return '<a class="ed-rail-card" href="/' + escapeHtml(item.video_id || item.file_stem || '') + '">' +
            (thumb ? '<div class="ed-rail-card__thumb"><img src="' + escapeHtml(thumb) + '" alt="" loading="lazy"></div>' : '') +
            '<div class="ed-rail-card__body">' +
                '<h4 class="ed-rail-card__title">' + escapeHtml(item.title) + '</h4>' +
                '<div class="ed-rail-card__meta">' +
                    (sourceLabel ? '<span>' + escapeHtml(sourceLabel) + '</span>' : '') +
                    (duration ? '<span>' + duration + '</span>' : '') +
                    (hasAudio ? '<span>&#9835;</span>' : '') +
                '</div>' +
            '</div>' +
        '</a>';
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

            // Block 1: Hero — first item
            if (this.state.page === 1 || this.mounts.hero.children.length === 0) {
                var hero = items[0];
                if (this.mounts.hero) {
                    this.mounts.hero.innerHTML = renderHeroCard(hero);
                }
            }

            if (this.mounts.sections) {
                var html = '';

                // Block 2: Supporting stories — next 2-4 items with source variety
                var supportPool = items.slice(1, 9);  // scan up to 8
                var supportItems = this.getSupportItems(supportPool, 4);

                if (supportItems.length > 0) {
                    html += '<section class="ed-support">';
                    for (var s = 0; s < supportItems.length; s++) {
                        html += renderFeatureCard(supportItems[s]);
                    }
                    html += '</section>';
                }

                // Block 3: Main feed — exclude hero and chosen support items by id
                var supportIds = {};
                for (var si = 0; si < supportItems.length; si++) {
                    supportIds[supportItems[si].video_id || supportItems[si].id] = true;
                }
                var feedItems = [];
                for (var fi = 1; fi < items.length; fi++) {
                    var fid = items[fi].video_id || items[fi].id;
                    if (!supportIds[fid]) {
                        feedItems.push(items[fi]);
                    }
                }

                if (feedItems.length > 0) {
                    html += '<section class="ed-feed">';
                    for (var f = 0; f < feedItems.length; f++) {
                        html += renderCompactCard(feedItems[f]);
                    }
                    html += '</section>';
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

            // Hide rail (no longer used on homepage)
            if (this.mounts.rail) {
                this.mounts.rail.innerHTML = '';
            }

            // Sync filter UI state
            this.renderTopbar();
            this.renderFilterChips();
            this.updateFilterButtonStates();
        }

        getSupportItems(pool, max) {
            if (!pool || !pool.length) return [];
            var sourceCounts = {};
            var picked = [];
            for (var i = 0; i < pool.length && picked.length < max; i++) {
                var item = pool[i];
                var src = item.source || '';
                var count = sourceCounts[src] || 0;
                if (count < 2) {
                    picked.push(item);
                    sourceCounts[src] = count + 1;
                }
            }
            return picked;
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

        // ---- Rail module helpers ----

        getRelatedItems(heroItem, max) {
            if (!heroItem) return [];
            var allItems = this.state.allItems || [];
            var heroCategories = getCategories(heroItem);
            var heroSource = heroItem.source || '';
            var heroChannel = heroItem.channel || heroItem.channel_name || '';
            var scored = [];
            for (var i = 0; i < allItems.length; i++) {
                var item = allItems[i];
                if (item.video_id === heroItem.video_id || item.id === heroItem.id) continue;
                var score = 0;
                var itemCats = getCategories(item);
                // Category overlap
                for (var c = 0; c < itemCats.length; c++) {
                    if (heroCategories.indexOf(itemCats[c]) !== -1) score += 3;
                }
                // Same source
                if (heroSource && item.source === heroSource) score += 2;
                // Same channel
                if (heroChannel && (item.channel || item.channel_name) === heroChannel) score += 2;
                if (score > 0) scored.push({ item: item, score: score });
            }
            scored.sort(function (a, b) { return b.score - a.score; });
            return scored.slice(0, max || 4).map(function (s) { return s.item; });
        }

        getPivotButtons() {
            var opts = this.state.filterOptions || {};
            var buttons = [];
            // Top categories
            var cats = (opts.categories || []).slice(0, 5);
            for (var i = 0; i < cats.length; i++) {
                buttons.push({ type: 'category', value: cats[i].value, label: cats[i].value });
            }
            // Sources
            var sources = (opts.source || opts.content_source || []).slice(0, 3);
            for (var j = 0; j < sources.length; j++) {
                buttons.push({ type: 'source', value: sources[j].value, label: sources[j].label });
            }
            // Audio
            var audioOpts = opts.has_audio || [];
            for (var a = 0; a < audioOpts.length; a++) {
                if (audioOpts[a].value === true) {
                    buttons.push({ type: 'has_audio', value: 'true', label: 'With Audio' });
                }
            }
            return buttons;
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
                var hasFilters = Object.keys(this.state.filters).some(
                    function (k) { return this.state.filters[k]; }.bind(this)
                );
                navHtml += '<button class="ed-refine-btn' + (hasFilters ? ' ed-refine-btn--active' : '') +
                    '" data-action="toggle-refine">Refine' +
                    (hasFilters ? ' (' + Object.keys(this.state.filters).length + ')' : '') + '</button>';
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
                content_type: opts.content_type,
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
            // Only render when refine panel is open
            if (!this._refineOpen) return;

            var filters = this.state.filterOptions;
            if (!filters) return;

            // Remove existing if re-rendering
            var existing = document.getElementById('ed-quick-filters');
            if (existing) existing.remove();

            var container = document.createElement('div');
            container.id = 'ed-quick-filters';
            container.className = 'ed-quick-filters ed-quick-filters--open';

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

        toggleRefine() {
            this._refineOpen = !this._refineOpen;
            if (this._refineOpen) {
                this.renderQuickFilters();
            } else {
                var existing = document.getElementById('ed-quick-filters');
                if (existing) existing.remove();
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
                // Refine toggle
                if (e.target.closest('[data-action="toggle-refine"]')) {
                    this.toggleRefine();
                    return;
                }

                // Close refine on outside click
                if (this._refineOpen) {
                    var panel = document.getElementById('ed-quick-filters');
                    var refineBtn = document.querySelector('[data-action="toggle-refine"]');
                    if (panel && !panel.contains(e.target) && refineBtn && !refineBtn.contains(e.target)) {
                        this._refineOpen = false;
                        if (panel) panel.remove();
                    }
                }

                // Rail pivot buttons (act as filter shortcuts)
                var pivotBtn = e.target.closest('.ed-rail-pivot-btn');
                if (pivotBtn) {
                    var pType = pivotBtn.dataset.filterType;
                    var pValue = pivotBtn.dataset.filterValue;
                    if (this.state.filters[pType] === pValue) {
                        delete this.state.filters[pType];
                    } else {
                        this.state.filters[pType] = pValue;
                    }
                    this.state.page = 1;
                    this.loadContent();
                    return;
                }

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

                // Close reader
                if (e.target.closest('[data-action="close-reader"]')) {
                    this.closeReader();
                    return;
                }

                // Audio toggle
                if (e.target.closest('[data-action="audio-toggle"]')) {
                    this.toggleAudioPlayback();
                    return;
                }

                // Audio close
                if (e.target.closest('[data-action="audio-close"]')) {
                    this.closeAudio();
                    return;
                }

                // Audio seek
                if (e.target.classList.contains('ed-audio-bar__seek')) {
                    var audio = document.getElementById('ed-audio-element');
                    if (audio && audio.duration) {
                        audio.currentTime = parseFloat(e.target.value);
                    }
                    return;
                }

                // Reader play audio button
                var playBtn = e.target.closest('[data-action="play-audio"]');
                if (playBtn) {
                    var audioUrl = playBtn.dataset.audioUrl;
                    if (audioUrl) {
                        var readerTitle = document.querySelector('.ed-reader__title');
                        this.playAudio(audioUrl, readerTitle ? readerTitle.textContent : '');
                    }
                    return;
                }

                // Read button -> open side reader
                var readLink = e.target.closest('[data-action="read"]');
                if (readLink) {
                    var readCard = readLink.closest('.ed-card');
                    var vid = readCard ? readCard.dataset.videoId : null;
                    if (vid) {
                        e.preventDefault();
                        this.openReader(vid);
                        return;
                    }
                }

                // Listen button on card
                var listenBtn = e.target.closest('[data-action="listen"]');
                if (listenBtn) {
                    var listenCard = listenBtn.closest('.ed-card');
                    var listenVid = listenCard ? listenCard.dataset.videoId : null;
                    if (listenVid) {
                        e.preventDefault();
                        this.openReader(listenVid, { autoPlayAudio: true });
                        return;
                    }
                }

                // Card click (open side reader instead of navigating)
                var card = e.target.closest('.ed-card');
                if (card && !e.target.closest('.ed-btn') && !e.target.closest('a')) {
                    var videoId = card.dataset.videoId;
                    if (videoId) {
                        this.openReader(videoId);
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

        // ---- Side Reader ----

        async openReader(videoId, opts) {
            if (!videoId) return;
            opts = opts || {};
            this._activeReaderId = videoId;
            this._readerAutoPlayAudio = !!opts.autoPlayAudio;
            this.showReaderPanel('<div class="ed-loading">Loading...</div>');

            try {
                var resp = await fetch('/' + videoId + '.json');
                if (!resp.ok) throw new Error('Failed to load report');
                var data = await resp.json();
                this.renderReaderContent(data);
                if (this._readerAutoPlayAudio && this._readerAudioUrl) {
                    var readerTitle = document.querySelector('.ed-reader__title');
                    this.playAudio(this._readerAudioUrl, readerTitle ? readerTitle.textContent : '');
                }
            } catch (err) {
                console.error('[Editorial] Reader failed:', err);
                this.showReaderPanel('<div class="ed-loading" style="color:#ef4444">Error: ' + escapeHtml(err.message) + '</div>');
            }
        }

        showReaderPanel(contentHtml) {
            var panel = document.getElementById('ed-reader');
            if (!panel) {
                panel = document.createElement('div');
                panel.id = 'ed-reader';
                panel.className = 'ed-reader';
                document.body.appendChild(panel);
            }
            panel.innerHTML = contentHtml;
            panel.classList.add('ed-reader--open');
        }

        closeReader() {
            var panel = document.getElementById('ed-reader');
            if (panel) {
                panel.classList.remove('ed-reader--open');
            }
            this._activeReaderId = null;
        }

        renderReaderContent(data) {
            var video = data.video || {};
            var summary = data.summary || {};
            var analysis = data.analysis || {};
            var title = video.title || '';
            var channel = video.channel || '';
            var thumb = data.thumbnail_url || '';
            var canonicalUrl = video.url || '';
            var duration = formatDuration(video.duration_seconds);
            var summaryHtml = summary.html || summary.text || '<p>No summary available.</p>';
            var hasAudio = !!data.has_audio;
            var audioUrl = null;
            var variants = data.summary_variants || [];
            for (var vi = 0; vi < variants.length; vi++) {
                if (variants[vi].audio_url) {
                    audioUrl = variants[vi].audio_url;
                    break;
                }
            }

            // Categories
            var categories = [];
            if (Array.isArray(analysis.categories)) {
                for (var i = 0; i < analysis.categories.length; i++) {
                    categories.push(analysis.categories[i].category);
                }
            }

            var html = '<div class="ed-reader__header">';
            html += '<button class="ed-reader__close" data-action="close-reader">&times;</button>';
            html += '</div>';

            html += '<div class="ed-reader__body">';

            // Meta bar
            html += '<div class="ed-reader__meta">';
            if (channel) html += '<span class="ed-card__channel">' + escapeHtml(channel) + '</span>';
            if (duration) html += '<span class="ed-card__time">' + duration + '</span>';
            if (categories.length) html += '<span class="ed-card__category-chip">' + escapeHtml(categories[0]) + '</span>';
            html += '</div>';

            // Title
            html += '<h1 class="ed-reader__title">' + escapeHtml(title) + '</h1>';

            // Thumbnail
            if (thumb) {
                html += '<div class="ed-reader__thumb"><img src="' + escapeHtml(thumb) + '" alt=""></div>';
            }

            // Actions
            html += '<div class="ed-reader__actions">';
            html += '<a class="ed-btn ed-btn--secondary ed-btn--sm" href="/' + escapeHtml(video.video_id || '') + '">Full page</a>';
            if (canonicalUrl) {
                html += '<a class="ed-btn ed-btn--ghost ed-btn--sm" href="' + escapeHtml(canonicalUrl) + '" target="_blank" rel="noopener">Watch source</a>';
            }
            if (hasAudio && audioUrl) {
                html += '<button class="ed-btn ed-btn--secondary ed-btn--sm" data-action="play-audio" data-audio-url="' + escapeHtml(audioUrl) + '">Listen</button>';
            }
            html += '</div>';

            // Summary content
            html += '<div class="ed-reader__summary">' + summaryHtml + '</div>';

            html += '</div>'; // ed-reader__body

            // Store audio URL for auto-play
            this._readerAudioUrl = audioUrl;

            this.showReaderPanel(html);
        }

        // ---- Audio Player ----

        playAudio(url, title) {
            var player = this.mounts.player;
            if (!player) return;

            var audio = player.querySelector('audio');
            if (!audio) {
                audio = document.createElement('audio');
                audio.id = 'ed-audio-element';
            }

            // If same URL and paused, resume
            var resolvedUrl = new URL(url, window.location.origin).href;
            if (audio.src && audio.src === resolvedUrl && audio.paused) {
                audio.play();
                player.classList.add('active');
                return;
            }

            audio.src = url;
            audio.preload = 'metadata';
            player.innerHTML = '';
            player.appendChild(audio);

            var bar = document.createElement('div');
            bar.className = 'ed-audio-bar';
            bar.innerHTML =
                '<button class="ed-audio-bar__play" data-action="audio-toggle">&#9654;</button>' +
                '<span class="ed-audio-bar__title">' + escapeHtml(title || 'Playing') + '</span>' +
                '<span class="ed-audio-bar__time">0:00</span>' +
                '<input type="range" class="ed-audio-bar__seek" min="0" max="100" value="0" step="0.1">' +
                '<span class="ed-audio-bar__duration">--:--</span>' +
                '<button class="ed-audio-bar__close" data-action="audio-close">&times;</button>';
            player.appendChild(bar);

            var self = this;
            audio.addEventListener('loadedmetadata', function () {
                var durSpan = bar.querySelector('.ed-audio-bar__duration');
                if (durSpan) durSpan.textContent = formatDuration(audio.duration);
                var seek = bar.querySelector('.ed-audio-bar__seek');
                if (seek) seek.max = Math.floor(audio.duration);
            });

            audio.addEventListener('timeupdate', function () {
                var timeSpan = bar.querySelector('.ed-audio-bar__time');
                if (timeSpan) timeSpan.textContent = formatDuration(audio.currentTime);
                var seek = bar.querySelector('.ed-audio-bar__seek');
                if (seek && audio.duration) seek.value = audio.currentTime;
            });

            audio.addEventListener('ended', function () {
                var playBtn = bar.querySelector('.ed-audio-bar__play');
                if (playBtn) playBtn.innerHTML = '&#9654;';
            });

            player.classList.add('active');
            audio.play().catch(function () {});
            var playBtn = bar.querySelector('.ed-audio-bar__play');
            if (playBtn) playBtn.innerHTML = '&#10074;&#10074;';
        }

        toggleAudioPlayback() {
            var audio = document.getElementById('ed-audio-element');
            if (!audio) return;
            var playBtn = document.querySelector('.ed-audio-bar__play');
            if (audio.paused) {
                audio.play();
                if (playBtn) playBtn.innerHTML = '&#10074;&#10074;';
            } else {
                audio.pause();
                if (playBtn) playBtn.innerHTML = '&#9654;';
            }
        }

        closeAudio() {
            var audio = document.getElementById('ed-audio-element');
            if (audio) { audio.pause(); audio.src = ''; }
            if (this.mounts.player) {
                this.mounts.player.classList.remove('active');
                this.mounts.player.innerHTML = '';
            }
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
