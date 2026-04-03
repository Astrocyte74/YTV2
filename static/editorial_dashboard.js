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
        var duration = formatDuration(item.duration_seconds);
        var thumb = getThumbnail(item);
        var sourceLabel = getSourceLabel(item);
        var ago = timeAgo(item.indexed_at);

        return '<article class="ed-card ed-card-feature" data-video-id="' + escapeHtml(item.video_id || item.id) + '">' +
            '<div class="ed-card-feature__image">' +
                '<img src="' + escapeHtml(thumb) + '" alt="" loading="lazy">' +
                (duration ? '<span class="ed-card__duration">' + duration + '</span>' : '') +
            '</div>' +
            '<div class="ed-card-feature__body">' +
                '<h3 class="ed-card-feature__title">' + escapeHtml(item.title) + '</h3>' +
                '<div class="ed-card__meta">' +
                    (sourceLabel ? '<span class="ed-card__source">' + escapeHtml(sourceLabel) + '</span>' : '') +
                    (ago ? '<span class="ed-card__time">' + ago + '</span>' : '') +
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

            this._topicsOpen = false;
            this._topicsSection = '';
            this._refineOpen = false;
            this._refineSection = '';
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
                var supportItems = this.getSupportItems(supportPool, 3);

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
                        html += renderFeatureCard(feedItems[f]);
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
                var activeCategory = this.state.filters.category || '';
                var isRecent = !activeCategory;

                // Editorial nav: Recent | Topics dropdown
                var navHtml = '<div class="ed-nav">';
                navHtml += '<button class="ed-nav__tab' + (isRecent ? ' ed-nav__tab--active' : '') +
                    '" data-action="nav-recent">Recent</button>';
                navHtml += '<div class="ed-nav__topics-wrap">';
                navHtml += '<button class="ed-nav__tab' + (!isRecent ? ' ed-nav__tab--active' : '') +
                    '" data-action="toggle-topics">' +
                    (this.state.filters.subcategory ? escapeHtml(this.state.filters.subcategory) :
                     (activeCategory ? escapeHtml(activeCategory) : 'Topics')) + ' ▾</button>';
                navHtml += this.renderTopicsDropdown();
                navHtml += '</div>';
                navHtml += '</div>';

                var hasFilters = Object.keys(this.state.filters).some(
                    function (k) { return this.state.filters[k] && k !== 'category' && k !== 'subcategory'; }.bind(this)
                );
                navHtml += '<div class="ed-refine-wrap">';
                navHtml += '<button class="ed-refine-btn' + (hasFilters ? ' ed-refine-btn--active' : '') +
                    '" data-action="toggle-refine">Refine' +
                    (hasFilters ? ' (' + Object.keys(this.state.filters).filter(function (k) { return k !== 'category' && k !== 'subcategory' && this.state.filters[k]; }.bind(this)).length + ')' : '') + '</button>';
                navHtml += this.renderRefineMenu();
                navHtml += '</div>';
                navHtml += '<a class="ed-topbar__link" href="/">Classic</a>';
                nav.innerHTML = navHtml;
            }
        }

        renderTopicsDropdown() {
            var opts = this.state.filterOptions || {};
            var categories = (opts.categories || [])
                .slice()
                .sort(function (a, b) { return (b.count || 0) - (a.count || 0); })
                .slice(0, 8);
            if (!categories.length) return '';

            var activeCategory = this.state.filters.category || '';
            var html = '<div class="ed-topics-dropdown' + (this._topicsOpen ? ' ed-topics-dropdown--open' : '') + '">';
            if (!this._topicsSection) {
                // First level: category list
                for (var i = 0; i < categories.length; i++) {
                    var isSelected = categories[i].value === activeCategory;
                    html += '<button class="ed-topics-dropdown__item' + (isSelected ? ' ed-topics-dropdown__item--active' : '') +
                        '" data-action="open-topic-section" data-topic="' + escapeHtml(categories[i].value) + '">' +
                        '<span>' + escapeHtml(categories[i].value) + '</span>' +
                        '<span class="ed-topics-dropdown__count">' + (categories[i].count || 0) + '</span>' +
                        '</button>';
                }
            } else {
                // Second level: "All [Category]" + subcategories
                html += '<div class="ed-topics-submenu__header">';
                html += '<button class="ed-topics-submenu__back" data-action="close-topic-section">\u2190 Topics</button>';
                html += '</div>';
                html += '<div class="ed-topics-submenu__list">';
                // "All [Category]" option
                var allActive = activeCategory === this._topicsSection && !this.state.filters.subcategory;
                html += '<button class="ed-topics-dropdown__item' + (allActive ? ' ed-topics-dropdown__item--active' : '') +
                    '" data-action="select-topic" data-topic="' + escapeHtml(this._topicsSection) + '">' +
                    'All ' + escapeHtml(this._topicsSection) + '</button>';
                // Subcategories
                var cat = categories.filter(function (c) { return c.value === this._topicsSection; }.bind(this))[0];
                var subs = (cat && cat.subcategories) || [];
                for (var s = 0; s < subs.length; s++) {
                    var isSubActive = this.state.filters.subcategory === subs[s].value;
                    html += '<button class="ed-topics-dropdown__item' + (isSubActive ? ' ed-topics-dropdown__item--active' : '') +
                        '" data-action="select-subtopic" data-topic="' + escapeHtml(this._topicsSection) +
                        '" data-subtopic="' + escapeHtml(subs[s].value) + '">' +
                        '<span>' + escapeHtml(subs[s].value) + '</span>' +
                        '<span class="ed-topics-dropdown__count">' + (subs[s].count || 0) + '</span>' +
                        '</button>';
                }
                html += '</div>';
            }
            html += '</div>';
            return html;
        }

        renderFilterChips() {
            var existing = document.getElementById('ed-filter-chips');
            if (existing) existing.remove();

            var activeFilters = Object.keys(this.state.filters).filter(
                function (k) { return this.state.filters[k]; }.bind(this)
            );
            var visibleFilters = activeFilters.filter(function (k) { return k !== 'category' && k !== 'subcategory'; });
            if (!visibleFilters.length && !this.state.search) return;

            var chipContainer = document.createElement('div');
            chipContainer.id = 'ed-filter-chips';
            chipContainer.className = 'ed-filter-chips';

            if (this.state.search) {
                chipContainer.innerHTML += '<span class="ed-chip" data-filter-key="search">' +
                    '"' + escapeHtml(this.state.search) + '" <button class="ed-chip__remove">&times;</button></span>';
            }

            for (var i = 0; i < visibleFilters.length; i++) {
                var key = visibleFilters[i];
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

        renderRefineMenu() {
            var filters = this.state.filterOptions;
            if (!filters) return '';
            var html = '<div class="ed-refine-menu' + (this._refineOpen ? ' ed-refine-menu--open' : '') + '" id="ed-refine-menu">';
            if (!this._refineSection) {
                html += '<div class="ed-refine-menu__list">';
                html += this.renderRefineMenuItem('sort', 'Sort', this.state.sort === 'oldest' ? 'Oldest' : 'Newest');

                var sources = filters.source || filters.content_source || [];
                if (sources.length > 1) {
                    html += this.renderRefineMenuItem(
                        'source',
                        'Source',
                        this.state.filters.source ? this.getFilterLabel('source', this.state.filters.source) : 'Any'
                    );
                }

                var contentTypes = filters.content_type || [];
                if (contentTypes.length > 1) {
                    html += this.renderRefineMenuItem(
                        'content_type',
                        'Type',
                        this.state.filters.content_type ? this.getFilterLabel('content_type', this.state.filters.content_type) : 'Any'
                    );
                }

                var audioOpts = filters.has_audio || [];
                if (audioOpts.length > 1) {
                    html += this.renderRefineMenuItem(
                        'has_audio',
                        'Audio',
                        this.state.filters.has_audio === 'true' ? 'With Audio' : 'Any'
                    );
                }
                html += '</div>';
            } else {
                html += this.renderRefineSubmenu();
            }
            html += '</div>';
            return html;
        }

        renderRefineMenuItem(section, label, value) {
            return '<button class="ed-refine-menu__item" data-action="open-refine-section" data-section="' + escapeHtml(section) + '">' +
                '<span class="ed-refine-menu__item-label">' + escapeHtml(label) + '</span>' +
                '<span class="ed-refine-menu__item-value">' + escapeHtml(value) + '</span>' +
                '</button>';
        }

        renderRefineSubmenu() {
            var filters = this.state.filterOptions || {};
            var section = this._refineSection;
            var html = '<div class="ed-refine-submenu">';
            html += '<div class="ed-refine-submenu__header">';
            html += '<button class="ed-refine-submenu__back" data-action="close-refine-section">← Refine</button>';
            html += '</div>';
            html += '<div class="ed-refine-submenu__list">';

            if (section === 'sort') {
                html += '<button class="ed-refine-menu__button' + (this.state.sort === 'newest' ? ' ed-refine-menu__button--active' : '') +
                    '" data-action="refine-sort" data-sort="newest">Newest</button>';
                html += '<button class="ed-refine-menu__button' + (this.state.sort === 'oldest' ? ' ed-refine-menu__button--active' : '') +
                    '" data-action="refine-sort" data-sort="oldest">Oldest</button>';
            } else if (section === 'source') {
                html += '<button class="ed-refine-menu__button' + (!this.state.filters.source ? ' ed-refine-menu__button--active' : '') +
                    '" data-filter-type="source" data-filter-value="">Any source</button>';
                var sources = filters.source || filters.content_source || [];
                for (var i = 0; i < sources.length; i++) {
                    var isActive = this.state.filters.source === String(sources[i].value);
                    html += '<button class="ed-refine-menu__button' + (isActive ? ' ed-refine-menu__button--active' : '') +
                        '" data-filter-type="source" data-filter-value="' + escapeHtml(sources[i].value) + '">' +
                        escapeHtml(sources[i].label) + '</button>';
                }
            } else if (section === 'content_type') {
                html += '<button class="ed-refine-menu__button' + (!this.state.filters.content_type ? ' ed-refine-menu__button--active' : '') +
                    '" data-filter-type="content_type" data-filter-value="">Any type</button>';
                var contentTypes = filters.content_type || [];
                for (var ct = 0; ct < contentTypes.length; ct++) {
                    var isTypeActive = this.state.filters.content_type === String(contentTypes[ct].value);
                    html += '<button class="ed-refine-menu__button' + (isTypeActive ? ' ed-refine-menu__button--active' : '') +
                        '" data-filter-type="content_type" data-filter-value="' + escapeHtml(contentTypes[ct].value) + '">' +
                        escapeHtml(contentTypes[ct].value) + '</button>';
                }
            } else if (section === 'has_audio') {
                html += '<button class="ed-refine-menu__button' + (!this.state.filters.has_audio ? ' ed-refine-menu__button--active' : '') +
                    '" data-filter-type="has_audio" data-filter-value="">Any audio</button>';
                html += '<button class="ed-refine-menu__button' + (this.state.filters.has_audio === 'true' ? ' ed-refine-menu__button--active' : '') +
                    '" data-filter-type="has_audio" data-filter-value="true">With Audio</button>';
            }

            html += '</div></div>';
            return html;
        }

        toggleRefine() {
            this._refineOpen = !this._refineOpen;
            this._topicsOpen = false;
            this._topicsSection = '';
            this._refineSection = '';
            this.renderTopbar();
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

            // Click delegation
            document.addEventListener('click', function (e) {
                // Refine toggle
                if (e.target.closest('[data-action="toggle-refine"]')) {
                    this.toggleRefine();
                    return;
                }

                // Refine sort buttons
                var refineSortBtn = e.target.closest('[data-action="refine-sort"]');
                if (refineSortBtn) {
                    this.state.sort = refineSortBtn.dataset.sort;
                    this._refineOpen = false;
                    this._refineSection = '';
                    this.state.page = 1;
                    this.loadContent();
                    return;
                }

                var openRefineSectionBtn = e.target.closest('[data-action="open-refine-section"]');
                if (openRefineSectionBtn) {
                    this._refineSection = openRefineSectionBtn.dataset.section || '';
                    this.renderTopbar();
                    return;
                }

                if (e.target.closest('[data-action="close-refine-section"]')) {
                    this._refineSection = '';
                    this.renderTopbar();
                    return;
                }

                // Nav: Recent
                if (e.target.closest('[data-action="nav-recent"]')) {
                    delete this.state.filters.category;
                    delete this.state.filters.subcategory;
                    this.state.page = 1;
                    this._topicsOpen = false;
                    this._topicsSection = '';
                    this.loadContent();
                    return;
                }

                // Nav: Topics dropdown toggle
                if (e.target.closest('[data-action="toggle-topics"]')) {
                    this._topicsOpen = !this._topicsOpen;
                    this._topicsSection = '';
                    this._refineOpen = false;
                    this._refineSection = '';
                    this.renderTopbar();
                    return;
                }

                // Open topic section (show subcategories)
                var openTopicBtn = e.target.closest('[data-action="open-topic-section"]');
                if (openTopicBtn) {
                    this._topicsSection = openTopicBtn.dataset.topic || '';
                    this.renderTopbar();
                    return;
                }

                if (e.target.closest('[data-action="close-topic-section"]')) {
                    this._topicsSection = '';
                    this.renderTopbar();
                    return;
                }

                // Nav: Topic selection ("All [Category]")
                var topicBtn = e.target.closest('[data-action="select-topic"]');
                if (topicBtn) {
                    this.state.filters.category = topicBtn.dataset.topic;
                    delete this.state.filters.subcategory;
                    this.state.page = 1;
                    this._topicsOpen = false;
                    this._topicsSection = '';
                    this.loadContent();
                    return;
                }

                // Nav: Subtopic selection
                var subtopicBtn = e.target.closest('[data-action="select-subtopic"]');
                if (subtopicBtn) {
                    this.state.filters.category = subtopicBtn.dataset.topic;
                    this.state.filters.subcategory = subtopicBtn.dataset.subtopic;
                    this.state.page = 1;
                    this._topicsOpen = false;
                    this._topicsSection = '';
                    this.loadContent();
                    return;
                }

                // Close topics dropdown on outside click
                if (this._topicsOpen) {
                    var topicsWrap = document.querySelector('.ed-nav__topics-wrap');
                    if (topicsWrap && !topicsWrap.contains(e.target)) {
                        this._topicsOpen = false;
                        this._topicsSection = '';
                        this.renderTopbar();
                    }
                }

                // Close refine on outside click
                if (this._refineOpen) {
                    var refineWrap = document.querySelector('.ed-refine-wrap');
                    if (refineWrap && !refineWrap.contains(e.target)) {
                        this._refineOpen = false;
                        this._refineSection = '';
                        this.renderTopbar();
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

                // Refine filter buttons
                var refineFilterBtn = e.target.closest('.ed-refine-menu__button[data-filter-type]');
                if (refineFilterBtn) {
                    var refineType = refineFilterBtn.dataset.filterType;
                    var refineValue = refineFilterBtn.dataset.filterValue;
                    if (!refineValue || this.state.filters[refineType] === refineValue) {
                        delete this.state.filters[refineType];
                    } else {
                        this.state.filters[refineType] = refineValue;
                    }
                    this._refineOpen = false;
                    this._refineSection = '';
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

            var html = '';

            // Close button — absolutely positioned, no header row
            html += '<button class="ed-reader__close" data-action="close-reader">&times;</button>';

            html += '<div class="ed-reader__body">';

            // Meta bar
            html += '<div class="ed-reader__meta">';
            if (channel) html += '<span class="ed-card__channel">' + escapeHtml(channel) + '</span>';
            if (duration) html += '<span class="ed-card__time">' + duration + '</span>';
            if (categories.length) html += '<span class="ed-card__category-chip">' + escapeHtml(categories[0]) + '</span>';
            html += '</div>';

            // Title
            html += '<h1 class="ed-reader__title">' + escapeHtml(title) + '</h1>';

            // Actions (before image — text-first flow)
            html += '<div class="ed-reader__actions">';
            html += '<a class="ed-btn ed-btn--primary ed-btn--sm" href="/' + escapeHtml(video.video_id || '') + '">Open full report</a>';
            if (canonicalUrl) {
                html += '<a class="ed-btn ed-btn--ghost ed-btn--sm" href="' + escapeHtml(canonicalUrl) + '" target="_blank" rel="noopener">Watch source</a>';
            }
            if (hasAudio && audioUrl) {
                html += '<button class="ed-btn ed-btn--secondary ed-btn--sm" data-action="play-audio" data-audio-url="' + escapeHtml(audioUrl) + '">Listen</button>';
            }
            html += '</div>';

            // Thumbnail (after actions — image as supporting content)
            if (thumb) {
                html += '<div class="ed-reader__thumb"><img src="' + escapeHtml(thumb) + '" alt=""></div>';
            }

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
        app.renderTopbar();
        await app.loadContent();
        window.__editorialApp = app;
    }
})();
