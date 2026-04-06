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

    var _imageMode = localStorage.getItem('ytv2.imageMode') || 'default';
    // Migrate old accent-only key to combined theme key
    var _theme = localStorage.getItem('ytv2.theme') || localStorage.getItem('ytv2.accentTheme') || 'default';
    if (localStorage.getItem('ytv2.accentTheme')) {
        localStorage.removeItem('ytv2.accentTheme');
        localStorage.setItem('ytv2.theme', _theme);
    }

    function getThumbnail(item) {
        if (_imageMode === 'ai1') {
            return item.summary_image_url ||
                item.thumbnail_url ||
                '/static/placeholder-thumb.png';
        }
        if (_imageMode === 'ai2') {
            var analysis = item.analysis || {};
            return analysis.summary_image_ai2_url ||
                item.summary_image_ai2_url ||
                item.summary_image_url ||
                item.thumbnail_url ||
                '/static/placeholder-thumb.png';
        }
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

    // ---- Image helpers (ported from classic) ----

    function isAi2Variant(v) {
        var m = (v.image_mode || '').toLowerCase();
        var tmpl = (v.template || '').toLowerCase();
        var ps = (v.prompt_source || '').toLowerCase();
        var url = v.url || '';
        return m === 'ai2' || tmpl === 'ai2_freestyle' || (ps && ps.startsWith('ai2')) || /(?:^|\/)AI2_/i.test(url);
    }

    function normalizeAssetUrl(u) {
        if (!u || typeof u !== 'string') return u || '';
        var trimmed = u.trim();
        if (!trimmed) return '';
        if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed;
        if (trimmed.startsWith('/')) return trimmed;
        return '/' + trimmed;
    }

    function urlPath(url) {
        if (!url) return '';
        try { return new URL(url, 'http://x').pathname; }
        catch (_) { return url.replace(/^https?:\/\/[^\/]+/, ''); }
    }

    function getAi2VariantUrls(analysis) {
        var urls = [];
        var seen = {};
        function push(u) {
            var n = normalizeAssetUrl(u);
            if (n && !seen[n]) { seen[n] = true; urls.push(n); }
        }
        var direct = (analysis && analysis.summary_image_ai2_url) || '';
        push(direct);
        var variants = (analysis && Array.isArray(analysis.summary_image_variants)) ? analysis.summary_image_variants : [];
        for (var i = 0; i < variants.length; i++) {
            var v = variants[i] || {};
            var u = v.url || '';
            if (isAi2Variant(v)) push(u);
        }
        return urls;
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

    var REPROCESS_VARIANTS = [
        { id: 'comprehensive', label: 'Comprehensive', kind: 'text', hint: 'Long-form narrative summary' },
        { id: 'bullet-points', label: 'Key Points', kind: 'text', hint: 'Compact bullet digest' },
        { id: 'key-insights', label: 'Insights', kind: 'text', hint: 'Higher-level takeaways' },
        { id: 'audio', label: 'Audio (EN)', kind: 'audio', hint: 'English listening track' },
        { id: 'audio-fr', label: 'Audio français', kind: 'audio', proficiency: true, hint: 'French audio with level selection' },
        { id: 'audio-es', label: 'Audio español', kind: 'audio', proficiency: true, hint: 'Spanish audio with level selection' }
    ];

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
            this._settingsOpen = false;
            this._sortOpen = false;

            // Related mode state
            this._selectedItemId = null;
            this._relatedMode = false;
            this._baseOrderedItems = null;
            this._relatedAnchorIndex = -1;
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
                // Clear related mode when reloading from page 1
                this._relatedMode = false;
                this._baseOrderedItems = null;
                this._relatedAnchorIndex = -1;
                this._selectedItemId = null;
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

            // Related-mode banner (above hero)
            if (this.mounts.hero) {
                var bannerHtml = '';
                if (this._relatedMode && this._selectedItemId) {
                    var anchor = this._getSelectedItem();
                    var anchorTitle = anchor ? (anchor.title || '') : '';
                    var truncatedTitle = anchorTitle.length > 50 ? anchorTitle.substring(0, 50).replace(/\s+\S*$/, '') + '...' : anchorTitle;
                    bannerHtml = '<div class="ed-related-banner">' +
                        '<span class="ed-related-banner__label">Related to:</span> ' +
                        '<span class="ed-related-banner__title">' + escapeHtml(truncatedTitle) + '</span>' +
                        '<button class="ed-related-banner__close" data-action="exit-related">Back to Recent</button>' +
                        '</div>';
                }

                // Block 1: Hero — always re-render (banner appears/disappears with related mode)
                var hero = items[0];
                this.mounts.hero.innerHTML = bannerHtml + renderHeroCard(hero);
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

        // ---- Related mode: heuristic similarity (ported from dashboard_v3.js) ----

        _tokenizeTitle(text) {
            try {
                var stop = { the: 1, a: 1, an: 1, and: 1, or: 1, of: 1, to: 1, in: 1, on: 1, for: 1, with: 1, from: 1, by: 1, at: 1, is: 1, are: 1, be: 1, this: 1, that: 1, it: 1, as: 1, vs: 1, 'vs.': 1, you: 1, your: 1 };
                return String(text || '')
                    .toLowerCase()
                    .replace(/[^a-z0-9\s]+/g, ' ')
                    .split(/\s+/)
                    .filter(function (t) { return t && !stop[t]; });
            } catch (_) { return []; }
        }

        _jaccard(a, b) {
            var A = {};
            var B = {};
            for (var i = 0; i < a.length; i++) A[a[i]] = true;
            for (var j = 0; j < b.length; j++) B[b[j]] = true;
            var inter = 0;
            var keysA = Object.keys(A);
            for (var k = 0; k < keysA.length; k++) {
                if (B[keysA[k]]) inter++;
            }
            var uniSize = keysA.length + Object.keys(B).length - inter;
            return uniSize > 0 ? inter / uniSize : 0;
        }

        _extractCatsAndSubcats(item) {
            if (!item) return { categories: [], subcats: [], subcatPairs: [] };

            var subcategoriesStructure = null;

            // Check for new structured subcategories_json field first
            if (item.subcategories_json) {
                try {
                    subcategoriesStructure = JSON.parse(item.subcategories_json);
                } catch (e) { /* ignore */ }
            }

            // Also check for pre-parsed categories from analysis
            if (!subcategoriesStructure && item.analysis && Array.isArray(item.analysis.categories) && item.analysis.categories.length) {
                subcategoriesStructure = { categories: item.analysis.categories };
            }

            // Use structured data if available
            if (subcategoriesStructure && subcategoriesStructure.categories && subcategoriesStructure.categories.length) {
                var categories = subcategoriesStructure.categories
                    .map(function (c) { return c && c.category; })
                    .filter(Boolean);

                var subcatPairs = [];
                for (var ci = 0; ci < subcategoriesStructure.categories.length; ci++) {
                    var cat = subcategoriesStructure.categories[ci];
                    var parent = cat && cat.category;
                    if (!parent || !Array.isArray(cat.subcategories)) continue;
                    for (var si = 0; si < cat.subcategories.length; si++) {
                        subcatPairs.push([parent, cat.subcategories[si]]);
                    }
                }

                var seen = {};
                var subcats = [];
                for (var pi = 0; pi < subcatPairs.length; pi++) {
                    var s = subcatPairs[pi][1];
                    if (!seen[s]) { seen[s] = true; subcats.push(s); }
                }

                return { categories: categories, subcats: subcats, subcatPairs: subcatPairs };
            }

            // Fallback: legacy logic
            var analysis = item.analysis || {};
            var cats = [];
            if (analysis.schema_version >= 2 && Array.isArray(analysis.categories)) {
                cats = analysis.categories.map(function (c) { return c && c.category; }).filter(Boolean);
            } else if (Array.isArray(analysis.category)) {
                cats = analysis.category.slice();
            }
            return { categories: cats, subcats: [], subcatPairs: [] };
        }

        _computeHeuristicSimilarity(baseItem, candItem) {
            if (!baseItem || !candItem || baseItem === candItem) return 0;
            var score = 0;
            try {
                var info1 = this._extractCatsAndSubcats(baseItem);
                var info2 = this._extractCatsAndSubcats(candItem);

                // Category overlap
                var catSet1 = {};
                for (var c1 = 0; c1 < info1.categories.length; c1++) catSet1[info1.categories[c1]] = true;
                var catInter = 0;
                for (var c2 = 0; c2 < info2.categories.length; c2++) {
                    if (catSet1[info2.categories[c2]]) catInter++;
                }
                score += catInter * 2.0;

                // Subcategory pair overlap
                var pairSet1 = {};
                for (var p1 = 0; p1 < info1.subcatPairs.length; p1++) {
                    pairSet1[info1.subcatPairs[p1].join('>')] = true;
                }
                var pairInter = 0;
                for (var p2 = 0; p2 < info2.subcatPairs.length; p2++) {
                    if (pairSet1[info2.subcatPairs[p2].join('>')]) pairInter++;
                }
                score += pairInter * 4.0;

                // Channel/source boost
                var ch1 = (baseItem.channel || '').toLowerCase().trim();
                var ch2 = (candItem.channel || '').toLowerCase().trim();
                if (ch1 && ch2 && ch1 === ch2) score += 1.5;

                // Title token overlap
                var t1 = this._tokenizeTitle(baseItem.title);
                var t2 = this._tokenizeTitle(candItem.title);
                score += 0.8 * this._jaccard(t1, t2);
            } catch (_) { /* no-op */ }
            return score;
        }

        // ---- Related mode: state management ----

        _selectItem(videoId) {
            // Selection is now driven by openReader — this is a compatibility shim
            if (!videoId) return;
            this._selectedItemId = videoId;
            this._updateSelectedVisualState();
            this.renderTopbar();
        }

        _updateSelectedVisualState() {
            // Remove all existing selected states
            var prev = document.querySelectorAll('.ed-card--selected');
            for (var i = 0; i < prev.length; i++) {
                prev[i].classList.remove('ed-card--selected');
            }
            // Apply to matching card
            if (this._selectedItemId) {
                var card = document.querySelector('.ed-card[data-video-id="' + CSS.escape(this._selectedItemId) + '"]');
                if (card) card.classList.add('ed-card--selected');
            }
        }

        _getSelectedItem() {
            if (!this._selectedItemId) return null;
            var items = (this._relatedMode && this._baseOrderedItems) ? this._baseOrderedItems : (this.state.items || []);
            for (var i = 0; i < items.length; i++) {
                var id = items[i].video_id || items[i].id;
                if (id === this._selectedItemId) return items[i];
            }
            return null;
        }

        _captureCardRects() {
            var cards = document.querySelectorAll('.ed-card[data-video-id]');
            var rects = {};
            for (var i = 0; i < cards.length; i++) {
                var vid = cards[i].getAttribute('data-video-id');
                if (vid) {
                    rects[vid] = cards[i].getBoundingClientRect();
                }
            }
            return rects;
        }

        _animateCardReflow(beforeRects) {
            if (!beforeRects) return;
            // Respect reduced motion preference
            if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

            var cards = document.querySelectorAll('.ed-card[data-video-id]');
            for (var i = 0; i < cards.length; i++) {
                var vid = cards[i].getAttribute('data-video-id');
                if (!vid) continue;
                var from = beforeRects[vid];
                if (!from) continue;
                var to = cards[i].getBoundingClientRect();
                var dx = from.left - to.left;
                var dy = from.top - to.top;
                // Skip if barely moved
                if (Math.abs(dx) < 2 && Math.abs(dy) < 2) continue;
                try {
                    cards[i].animate(
                        [
                            { transform: 'translate(' + dx + 'px, ' + dy + 'px)' },
                            { transform: 'translate(0px, 0px)' }
                        ],
                        {
                            duration: 360,
                            easing: 'cubic-bezier(0.22, 1, 0.36, 1)'
                        }
                    );
                } catch (_) { }
            }
        }

        _enterRelatedMode() {
            var items = this.state.items || [];
            if (!items.length || !this._selectedItemId) return;

            // Capture FIRST positions before re-render
            var beforeRects = this._captureCardRects();

            // Snapshot current order
            this._baseOrderedItems = items.slice();

            // Find anchor's original index
            this._relatedAnchorIndex = -1;
            for (var i = 0; i < this._baseOrderedItems.length; i++) {
                var id = this._baseOrderedItems[i].video_id || this._baseOrderedItems[i].id;
                if (id === this._selectedItemId) {
                    this._relatedAnchorIndex = i;
                    break;
                }
            }
            if (this._relatedAnchorIndex === -1) return;

            var anchor = this._baseOrderedItems[this._relatedAnchorIndex];

            // Score all other items against anchor
            var scored = [];
            for (var j = 0; j < this._baseOrderedItems.length; j++) {
                if (j === this._relatedAnchorIndex) continue;
                var sc = this._computeHeuristicSimilarity(anchor, this._baseOrderedItems[j]);
                scored.push({ item: this._baseOrderedItems[j], score: sc });
            }
            scored.sort(function (a, b) { return b.score - a.score; });

            // Build derived order: [anchor, ...rest by score]
            var derived = [anchor];
            for (var k = 0; k < scored.length; k++) {
                derived.push(scored[k].item);
            }

            this._relatedMode = true;
            this.state.items = derived;
            this.render();
            this._updateSelectedVisualState();

            // Re-render reader to update the related bar
            if (this._currentReaderData) {
                this.renderReaderContent(this._currentReaderData);
            }

            // LAST + INVERT + PLAY
            this._animateCardReflow(beforeRects);

            // Scroll to top so user sees the new hero
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        _exitRelatedMode() {
            // Capture FIRST positions before restoring
            var beforeRects = this._captureCardRects();

            if ((this._baseOrderedItems || []).length > 0) {
                this.state.items = this._baseOrderedItems.slice();
            }
            this._relatedMode = false;
            this._baseOrderedItems = null;
            this._relatedAnchorIndex = -1;
            this.render();

            // Re-render reader to update the related bar
            if (this._currentReaderData) {
                this.renderReaderContent(this._currentReaderData);
            }

            // Animate cards back to their original positions
            this._animateCardReflow(beforeRects);
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

                // Editorial nav: Sort dropdown | Topics dropdown
                var navHtml = '<div class="ed-nav">';
                navHtml += '<div class="ed-nav__sort-wrap">';
                navHtml += '<button class="ed-nav__tab' + (this._sortOpen ? ' ed-nav__tab--active' : '') +
                    '" data-action="toggle-sort">' +
                    (this.state.sort === 'oldest' ? 'Oldest' : 'Newest') + ' ▾</button>';
                navHtml += this.renderSortDropdown();
                navHtml += '</div>';
                navHtml += '<div class="ed-nav__topics-wrap">';
                navHtml += '<button class="ed-nav__tab' + (activeCategory ? ' ed-nav__tab--active' : '') +
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

                // Note: Related toggle lives in the reader header bar, not the topbar,
                // because the reader panel covers the topbar on normal-width screens.

                navHtml += '<div class="ed-settings-wrap">';
                navHtml += '<button class="ed-refine-btn" data-action="toggle-settings">Settings</button>';
                navHtml += this.renderSettingsPanel();
                navHtml += '</div>';
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
                // First level: "All topics" clear option (only when a filter is active)
                if (activeCategory) {
                    html += '<button class="ed-topics-dropdown__item" data-action="nav-recent">' +
                        '<span>All topics</span>' +
                        '</button>';
                }
                // Category list
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

        renderSortDropdown() {
            var html = '<div class="ed-sort-dropdown' + (this._sortOpen ? ' ed-sort-dropdown--open' : '') + '">';
            var opts = [
                { value: 'newest', label: 'Newest first' },
                { value: 'oldest', label: 'Oldest first' },
            ];
            for (var i = 0; i < opts.length; i++) {
                var isActive = this.state.sort === opts[i].value;
                html += '<button class="ed-sort-dropdown__item' + (isActive ? ' ed-sort-dropdown__item--active' : '') +
                    '" data-action="set-sort" data-sort="' + opts[i].value + '">' +
                    escapeHtml(opts[i].label) +
                    '</button>';
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
            var visibleFilters = activeFilters;
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

            if (section === 'source') {
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
            this._settingsOpen = false;
            this._sortOpen = false;
            this.renderTopbar();
        }

        renderSettingsPanel() {
            var html = '<div class="ed-settings-panel' + (this._settingsOpen ? ' ed-settings-panel--open' : '') + '">';
            html += '<div class="ed-settings-section">';
            html += '<div class="ed-settings-label">Image display</div>';
            html += '<div class="ed-settings-segmented">';
            var modes = [
                { key: 'default', label: 'Default' },
                { key: 'ai1', label: 'AI 1' },
                { key: 'ai2', label: 'AI 2' },
            ];
            for (var mi = 0; mi < modes.length; mi++) {
                var isActive = _imageMode === modes[mi].key;
                html += '<button class="ed-settings-seg' + (isActive ? ' ed-settings-seg--active' : '') +
                    '" data-action="set-image-mode" data-mode="' + modes[mi].key + '">' + modes[mi].label + '</button>';
            }
            html += '</div></div>';
            html += '<div class="ed-settings-divider"></div>';
            html += '<div class="ed-settings-section">';
            html += '<div class="ed-settings-label">Theme</div>';
            html += '<div class="ed-settings-accent-grid">';
            var themes = [
                { key: 'default', label: 'Midnight', color: '#7c8cf8' },
                { key: 'emerald', label: 'Emerald', color: '#34d399' },
                { key: 'amber', label: 'Amber', color: '#f59e0b' },
                { key: 'rose', label: 'Rose', color: '#fb7185' },
                { key: 'cyan', label: 'Cyan', color: '#22d3ee' },
                { key: 'slate', label: 'Slate', color: '#818cf8' },
                { key: 'paper', label: 'Paper', color: '#2563eb' },
                { key: 'frost', label: 'Frost', color: '#0284c7' },
                { key: 'sand', label: 'Sand', color: '#c2410c' },
            ];
            for (var ai = 0; ai < themes.length; ai++) {
                var thmActive = _theme === themes[ai].key;
                html += '<button class="ed-settings-accent-btn' + (thmActive ? ' ed-settings-accent-btn--active' : '') +
                    '" data-action="set-theme" data-theme="' + themes[ai].key + '">' +
                    '<span class="ed-accent-dot" style="background:' + themes[ai].color + '"></span>' +
                    themes[ai].label + '</button>';
            }
            html += '</div></div>';
            html += '<div class="ed-settings-divider"></div>';
            html += '<a class="ed-settings-link" href="/">Classic dashboard</a>';
            html += '</div>';
            return html;
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
                // Related toggle
                if (e.target.closest('[data-action="toggle-related"]')) {
                    if (this._relatedMode) {
                        this._exitRelatedMode();
                        // Preserve reader context — do NOT clear _selectedItemId
                        this.renderTopbar();
                    } else {
                        this._enterRelatedMode();
                        this.renderTopbar();
                    }
                    return;
                }

                // Exit related mode (Back to Recent)
                if (e.target.closest('[data-action="exit-related"]')) {
                    this._exitRelatedMode();
                    // Preserve reader context — do NOT clear _selectedItemId
                    this.renderTopbar();
                    return;
                }

                // Refine toggle
                if (e.target.closest('[data-action="toggle-refine"]')) {
                    this.toggleRefine();
                    return;
                }

                // Settings toggle
                if (e.target.closest('[data-action="toggle-settings"]')) {
                    this._settingsOpen = !this._settingsOpen;
                    this._topicsOpen = false;
                    this._topicsSection = '';
                    this._refineOpen = false;
                    this._sortOpen = false;
                    this._refineSection = '';
                    this.renderTopbar();
                    return;
                }

                // Image mode change
                var imgModeBtn = e.target.closest('[data-action="set-image-mode"]');
                if (imgModeBtn) {
                    var newMode = imgModeBtn.dataset.mode || 'default';
                    _imageMode = newMode;
                    localStorage.setItem('ytv2.imageMode', newMode);
                    this._swapCardImages();
                    // Keep settings open so user sees the active state change
                    this._settingsOpen = true;
                    this.renderTopbar();
                    // Update reader thumbnail if open
                    try {
                        var readerImg = document.querySelector('.ed-reader__thumb img');
                        if (readerImg && this._currentReaderData) {
                            var readerItem = this._currentReaderData;
                            readerImg.src = getThumbnail(readerItem);
                        }
                    } catch (_) {}
                    return;
                }

                // Theme change
                var themeBtn = e.target.closest('[data-action="set-theme"]');
                if (themeBtn) {
                    var theme = themeBtn.dataset.theme || 'default';
                    _theme = theme;
                    localStorage.setItem('ytv2.theme', theme);
                    if (theme === 'default') {
                        document.documentElement.removeAttribute('data-ed-theme');
                    } else {
                        document.documentElement.setAttribute('data-ed-theme', theme);
                    }
                    this._settingsOpen = true;
                    this.renderTopbar();
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

                // Nav: Recent / clear topic (used by "All topics" in dropdown)
                if (e.target.closest('[data-action="nav-recent"]')) {
                    delete this.state.filters.category;
                    delete this.state.filters.subcategory;
                    this.state.page = 1;
                    this._topicsOpen = false;
                    this._topicsSection = '';
                    this.loadContent();
                    return;
                }

                // Sort dropdown toggle
                if (e.target.closest('[data-action="toggle-sort"]')) {
                    this._sortOpen = !this._sortOpen;
                    this._topicsOpen = false;
                    this._topicsSection = '';
                    this._refineOpen = false;
                    this._refineSection = '';
                    this._settingsOpen = false;
                    this.renderTopbar();
                    return;
                }

                // Sort selection
                var sortBtn = e.target.closest('[data-action="set-sort"]');
                if (sortBtn) {
                    this.state.sort = sortBtn.dataset.sort;
                    this._sortOpen = false;
                    this.state.page = 1;
                    this.loadContent();
                    return;
                }

                // Close sort dropdown on outside click
                if (this._sortOpen) {
                    var sortWrap = document.querySelector('.ed-nav__sort-wrap');
                    if (sortWrap && !sortWrap.contains(e.target)) {
                        this._sortOpen = false;
                        this.renderTopbar();
                    }
                }

                // Nav: Topics dropdown toggle
                if (e.target.closest('[data-action="toggle-topics"]')) {
                    this._topicsOpen = !this._topicsOpen;
                    this._topicsSection = '';
                    this._sortOpen = false;
                    this._refineOpen = false;
                    this._refineSection = '';
                    this._settingsOpen = false;
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

                // Close settings on outside click
                if (this._settingsOpen) {
                    var settingsWrap = document.querySelector('.ed-settings-wrap');
                    if (settingsWrap && !settingsWrap.contains(e.target)) {
                        this._settingsOpen = false;
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
                            if (key === 'category') delete this.state.filters.subcategory;
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

                // Admin menu toggle
                if (e.target.closest('[data-action="toggle-admin-menu"]')) {
                    this.toggleAdminMenu();
                    return;
                }

                // Admin actions
                if (e.target.closest('[data-action="admin-delete"]')) {
                    this.showDeleteConfirm();
                    return;
                }
                if (e.target.closest('[data-action="admin-regenerate"]')) {
                    this.showRegenerateModal();
                    return;
                }
                if (e.target.closest('[data-action="admin-images"]')) {
                    this.showImagesModal();
                    return;
                }

                // Close admin menu on outside click
                var adminMenuEl = document.querySelector('.ed-reader__admin-menu--open');
                if (adminMenuEl) {
                    var adminToggle = document.querySelector('.ed-reader__admin-toggle');
                    if (adminToggle && !adminToggle.contains(e.target) && !adminMenuEl.contains(e.target)) {
                        adminMenuEl.classList.remove('ed-reader__admin-menu--open');
                    }
                }

                // Modal dismiss (cancel button, or click directly on backdrop element)
                if (e.target.closest('[data-action="modal-cancel"]')) {
                    this.closeModal();
                    return;
                }
                if (e.target.classList.contains('ed-modal-backdrop')) {
                    this.closeModal();
                    return;
                }

                // Token save
                if (e.target.closest('[data-action="save-token"]')) {
                    this.saveTokenFromModal();
                    return;
                }

                // Proficiency toggle (within regenerate modal)
                var profBtnEl = e.target.closest('.ed-proficiency-btn');
                if (profBtnEl) {
                    e.preventDefault();
                    var profCard = profBtnEl.closest('[data-regen-card]');
                    if (profCard) {
                        var siblings = profCard.querySelectorAll('.ed-proficiency-btn');
                        for (var pb = 0; pb < siblings.length; pb++) {
                            siblings[pb].classList.remove('ed-proficiency-btn--active');
                        }
                        profBtnEl.classList.add('ed-proficiency-btn--active');
                    }
                    return;
                }

                // Regenerate card interaction → update card state + CTA
                if (e.target.closest('[data-regen-card]')) {
                    var self = this;
                    setTimeout(function () { self._syncRegenSelectionState(); }, 0);
                    return;
                }

                // Modal confirm actions
                if (e.target.closest('[data-action="confirm-delete"]')) {
                    this.executeDelete();
                    return;
                }
                if (e.target.closest('[data-action="confirm-regenerate"]')) {
                    this.executeRegenerate();
                    return;
                }
                if (e.target.closest('[data-action="save-image-prompt"]')) {
                    this.executeSetImagePrompt();
                    return;
                }
                if (e.target.closest('[data-action="confirm-delete-image"]')) {
                    this.showDeleteImageConfirm(e.target.closest('[data-action="confirm-delete-image"]'));
                    return;
                }
                if (e.target.closest('[data-action="do-delete-image"]')) {
                    this.executeDeleteImageVariant();
                    return;
                }
                if (e.target.closest('[data-action="confirm-delete-all-images"]')) {
                    this.showDeleteAllImagesConfirm();
                    return;
                }
                if (e.target.closest('[data-action="do-delete-all-images"]')) {
                    this.executeDeleteAllImages();
                    return;
                }
                if (e.target.closest('[data-action="select-image-variant"]')) {
                    this.executeSelectImageVariant(e.target.closest('[data-action="select-image-variant"]'));
                    return;
                }
                if (e.target.closest('[data-action="switch-image-mode"]')) {
                    this.switchImageMode(e.target.closest('[data-action="switch-image-mode"]'));
                    return;
                }
                if (e.target.closest('[data-action="use-variant-prompt"]')) {
                    this.useVariantPrompt(e.target.closest('[data-action="use-variant-prompt"]'));
                    return;
                }
                var variantRow = e.target.closest('.ed-img-row[data-variant-url]');
                if (variantRow && !e.target.closest('button, a, input, textarea, select, label')) {
                    this._loadVariantPromptByUrl(variantRow.dataset.variantUrl);
                    return;
                }
                if (e.target.closest('[data-action="use-default-prompt"]')) {
                    this.useDefaultPrompt();
                    return;
                }

                // Switch summary variant
                var variantBtn = e.target.closest('[data-action="switch-variant"]');
                if (variantBtn) {
                    var idx = parseInt(variantBtn.dataset.variantIdx, 10);
                    this.switchReaderVariant(idx);
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
                        // Re-anchor related mode if active
                        if (this._relatedMode) {
                            this._enterRelatedMode();
                        }
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
            this._selectedItemId = videoId;
            this._readerAutoPlayAudio = !!opts.autoPlayAudio;
            this.showReaderPanel('<div class="ed-loading">Loading...</div>');

            try {
                var resp = await fetch('/' + videoId + '.json');
                if (!resp.ok) throw new Error('Failed to load report');
                var data = await resp.json();
                this._currentReaderData = data;
                this.renderReaderContent(data);
                if (this._readerAutoPlayAudio && this._readerAudioUrl) {
                    var readerTitle = document.querySelector('.ed-reader__title');
                    this.playAudio(this._readerAudioUrl, readerTitle ? readerTitle.textContent : '');
                }
            } catch (err) {
                console.error('[Editorial] Reader failed:', err);
                this.showReaderPanel('<div class="ed-loading" style="color:#ef4444">Error: ' + escapeHtml(err.message) + '</div>');
            }
            this._updateSelectedVisualState();
            this.renderTopbar();
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

        _swapCardImages() {
            var articles = document.querySelectorAll('article[data-video-id]');
            if (!articles.length) return;
            var items = this.state.allItems || [];
            var byId = {};
            for (var i = 0; i < items.length; i++) {
                var id = items[i].video_id || items[i].id;
                if (id) byId[id] = items[i];
            }
            for (var j = 0; j < articles.length; j++) {
                var vid = articles[j].dataset.videoId;
                if (vid && byId[vid]) {
                    var img = articles[j].querySelector('img');
                    if (img) img.src = getThumbnail(byId[vid]);
                }
            }
        }

        closeReader() {
            var panel = document.getElementById('ed-reader');
            if (panel) {
                panel.classList.remove('ed-reader--open');
            }
            this._activeReaderId = null;
            this._selectedItemId = null;
            this._updateSelectedVisualState();
            this.renderTopbar();
        }

        switchReaderVariant(idx) {
            var variants = this._readerVariants;
            if (!variants || idx < 0 || idx >= variants.length) return;
            this._readerActiveVariant = idx;

            var v = variants[idx];
            var summaryEl = document.querySelector('.ed-reader__summary');
            if (summaryEl) {
                summaryEl.innerHTML = v.html || v.text || '<p>No summary available.</p>';
            }

            // Update active tab
            var tabs = document.querySelectorAll('.ed-reader__variant');
            for (var t = 0; t < tabs.length; t++) {
                var tabIdx = parseInt(tabs[t].dataset.variantIdx, 10);
                tabs[t].classList.toggle('ed-reader__variant--active', tabIdx === idx);
            }

            // Update listen button audio URL
            var listenBtn = document.querySelector('[data-action="play-audio"]');
            if (listenBtn) {
                if (v.audio_url) {
                    listenBtn.dataset.audioUrl = v.audio_url;
                    listenBtn.disabled = false;
                    listenBtn.classList.remove('ed-btn--disabled');
                } else {
                    listenBtn.dataset.audioUrl = '';
                    listenBtn.disabled = true;
                    listenBtn.classList.add('ed-btn--disabled');
                }
            }
        }

        renderReaderContent(data) {
            this._readerData = data;
            var video = data.video || {};
            var summary = data.summary || {};
            var analysis = data.analysis || {};
            var title = video.title || '';
            var channel = video.channel || '';
            var thumb = getThumbnail(data);
            var canonicalUrl = video.url || '';
            var duration = formatDuration(video.duration_seconds);
            var summaryHtml = summary.html || summary.text || '<p>No summary available.</p>';
            var hasAudio = !!data.has_audio;
            var audioUrl = null;
            var variants = data.summary_variants || [];

            // Store variants for switching
            this._readerVariants = variants.length > 0 ? variants : [{ variant: 'default', html: summaryHtml, text: summary.text || '' }];
            this._readerActiveVariant = 0;

            for (var vi = 0; vi < variants.length; vi++) {
                if (variants[vi].audio_url) {
                    audioUrl = variants[vi].audio_url;
                    break;
                }
            }

            // Use first variant's html if available
            if (variants.length > 0 && variants[0].html) {
                summaryHtml = variants[0].html;
            }

            // Humanize variant names
            var variantLabels = {
                'key-insights': 'Key Insights',
                'bullet-points': 'Key Points',
                'comprehensive': 'Full Summary',
                'deep-research': 'Research'
            };

            function humanizeVariant(slug) {
                if (variantLabels[slug]) return variantLabels[slug];
                return slug.replace(/-/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
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

            // Admin menu (...)
            html += '<button class="ed-reader__admin-toggle" data-action="toggle-admin-menu">...</button>';
            html += '<div class="ed-reader__admin-menu">';
            html += '<button class="ed-reader__admin-item" data-action="admin-regenerate">Regenerate...</button>';
            html += '<button class="ed-reader__admin-item" data-action="admin-images">Manage Images...</button>';
            html += '<button class="ed-reader__admin-item ed-reader__admin-item--danger" data-action="admin-delete">Delete...</button>';
            html += '</div>';

            // View mode segmented control: Recent | Related
            var isRelated = this._relatedMode && this._selectedItemId;
            html += '<div class="ed-reader__view-bar">';
            html += '<button class="ed-view-tab' + (!isRelated ? ' ed-view-tab--active' : '') + '" data-action="exit-related">Recent</button>';
            html += '<button class="ed-view-tab' + (isRelated ? ' ed-view-tab--active' : '') + '" data-action="toggle-related">Related</button>';
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

            // Source link + audio (inline, minimal)
            if (canonicalUrl) {
                html += '<div class="ed-reader__source-link"><a href="' + escapeHtml(canonicalUrl) + '" target="_blank" rel="noopener">↗ View source</a></div>';
            }
            if (hasAudio && audioUrl) {
                html += '<button class="ed-btn ed-btn--ghost ed-btn--sm ed-reader__listen-btn" data-action="play-audio" data-audio-url="' + escapeHtml(audioUrl) + '">▶ Listen</button>';
            }

            // Variant tabs (only if multiple variants)
            if (this._readerVariants.length > 1) {
                html += '<div class="ed-reader__variants">';
                for (var ti = 0; ti < this._readerVariants.length; ti++) {
                    var vSlug = this._readerVariants[ti].variant || '';
                    var vLabel = humanizeVariant(vSlug);
                    html += '<button class="ed-reader__variant' + (ti === 0 ? ' ed-reader__variant--active' : '') +
                        '" data-action="switch-variant" data-variant-idx="' + ti + '">' + escapeHtml(vLabel) + '</button>';
                }
                html += '</div>';
            }

            // Thumbnail (after variant tabs — image as supporting content)
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

        // ---- SSE Live Updates ----

        connectEventSource() {
            if (this._eventSource) return; // already connected
            try {
                this._eventSource = new EventSource('/api/report-events');
                var self = this;

                this._eventSource.addEventListener('report-synced', function (e) {
                    try {
                        var data = JSON.parse(e.data);
                        console.log('[Editorial SSE] report-synced:', data.video_id);
                        self._handleReportSynced(data);
                    } catch (err) {
                        console.warn('[Editorial SSE] report-synced parse error:', err);
                    }
                });

                this._eventSource.addEventListener('reprocess-scheduled', function (e) {
                    try {
                        var data = JSON.parse(e.data);
                        console.log('[Editorial SSE] reprocess-scheduled:', data.video_id);
                        self.showToast('Regeneration scheduled for ' + (data.video_id || 'report'));
                    } catch (err) {
                        console.warn('[Editorial SSE] reprocess-scheduled parse error:', err);
                    }
                });

                this._eventSource.addEventListener('reprocess-complete', function (e) {
                    try {
                        var data = JSON.parse(e.data);
                        console.log('[Editorial SSE] reprocess-complete:', data.video_id, data.summary_type, data.status);
                        if (data.status === 'error') {
                            self.showToast('Regeneration failed for ' + (data.summary_type || 'report'));
                        } else {
                            self.showToast('Regeneration complete — ' + (data.summary_type || 'report'));
                            // Refresh reader if open for this video
                            if (self._activeReaderId === data.video_id) {
                                self.openReader(data.video_id);
                            }
                        }
                    } catch (err) {
                        console.warn('[Editorial SSE] reprocess-complete parse error:', err);
                    }
                });

                this._eventSource.addEventListener('reprocess-error', function (e) {
                    try {
                        var data = JSON.parse(e.data);
                        console.warn('[Editorial SSE] reprocess-error:', data.video_id, data.error);
                        var msg = 'Regeneration failed';
                        if (data.error === 'no-summary-types') {
                            msg = 'No summary types found for this report';
                        } else if (data.error === 'missing-url') {
                            msg = 'Could not resolve video URL';
                        } else if (data.error) {
                            msg = 'Regeneration failed: ' + data.error.substring(0, 80);
                        }
                        self.showToast(msg);
                    } catch (err) {
                        console.warn('[Editorial SSE] reprocess-error parse error:', err);
                    }
                });

                this._eventSource.addEventListener('audio-synced', function (e) {
                    try {
                        var data = JSON.parse(e.data);
                        console.log('[Editorial SSE] audio-synced:', data.video_id);
                        if (self._activeReaderId === data.video_id) {
                            self.showToast('Audio generation complete');
                            // Re-open reader to pick up new audio
                            self.openReader(data.video_id);
                        }
                    } catch (err) {
                        console.warn('[Editorial SSE] audio-synced parse error:', err);
                    }
                });

                this._eventSource.addEventListener('report-added', function (e) {
                    try {
                        var data = JSON.parse(e.data);
                        console.log('[Editorial SSE] report-added:', data.video_id);
                        self.showToast('New report available');
                        // Reload content to show the new report
                        self.state.page = 1;
                        self.loadContent();
                    } catch (err) {
                        console.warn('[Editorial SSE] report-added parse error:', err);
                    }
                });

                this._eventSource.addEventListener('image-prompt-set', function (e) {
                    try {
                        var data = JSON.parse(e.data);
                        console.log('[Editorial SSE] image-prompt-set:', data.video_id);
                        if (self._pendingImageGeneration && self._pendingImageGeneration.mode === (data.mode || 'ai1')) {
                            // Generation started, pending row will resolve via report-synced
                        }
                    } catch (err) {
                        console.warn('[Editorial SSE] image-prompt-set parse error:', err);
                    }
                });

                this._eventSource.addEventListener('error', function () {
                    console.warn('[Editorial SSE] Connection error — will auto-reconnect');
                });

                console.log('[Editorial] SSE connected to /api/report-events');
            } catch (err) {
                console.warn('[Editorial] Failed to connect SSE:', err);
            }
        }

        _handleReportSynced(data) {
            var videoId = data.video_id;
            if (!videoId) return;

            // If the user is viewing this report in the reader, refresh it
            if (this._activeReaderId === videoId) {
                console.log('[Editorial] Refreshing reader for synced report:', videoId);
                this.showToast('Report updated — refreshing');
                this.openReader(videoId);
            }

            // Check if this report exists in the current feed — refresh if on page 1
            if (this.state.page === 1) {
                var existsInFeed = false;
                for (var i = 0; i < this.state.items.length; i++) {
                    if (this.state.items[i].video_id === videoId || this.state.items[i].id === videoId) {
                        existsInFeed = true;
                        break;
                    }
                }
                if (existsInFeed) {
                    // Silently reload to pick up updated data
                    this.loadContent();
                }
            }
        }

        // ---- Admin Actions ----

        // Token management — shows editorial modal, never browser prompt()
        getAdminToken() {
            return localStorage.getItem('ytv2.reprocessToken') || '';
        }

        requireAdminToken(callback) {
            var token = this.getAdminToken();
            if (token) { callback(token); return; }
            this.showTokenPrompt(callback);
        }

        showTokenPrompt(callback) {
            this.showModal(
                '<div class="ed-modal__header">' +
                    '<h2 class="ed-modal__title">Admin token required</h2>' +
                    '<p class="ed-modal__subtitle">Enter your reprocess token to perform admin actions.</p>' +
                '</div>' +
                '<div class="ed-modal__body">' +
                    '<input type="password" class="ed-token-input" placeholder="Token" autocomplete="off">' +
                    '<p class="ed-token-helper">The token is stored locally and reused for future actions.</p>' +
                '</div>' +
                '<div class="ed-modal__footer">' +
                    '<button class="ed-btn ed-btn--ghost" data-action="modal-cancel">Cancel</button>' +
                    '<button class="ed-btn ed-btn--primary" data-action="save-token">Save token</button>' +
                '</div>',
                'ed-modal--admin'
            );
            this._tokenCallback = callback;
        }

        saveTokenFromModal() {
            var input = document.querySelector('.ed-token-input');
            var token = input ? input.value.trim() : '';
            if (!token) return;
            localStorage.setItem('ytv2.reprocessToken', token);
            this.closeModal();
            if (this._tokenCallback) {
                this._tokenCallback(token);
                this._tokenCallback = null;
            }
        }

        toggleAdminMenu() {
            var menu = document.querySelector('.ed-reader__admin-menu');
            if (menu) menu.classList.toggle('ed-reader__admin-menu--open');
        }

        closeAdminMenu() {
            var menu = document.querySelector('.ed-reader__admin-menu');
            if (menu) menu.classList.remove('ed-reader__admin-menu--open');
        }

        showModal(html, cssClass) {
            this.closeModal();
            var backdrop = document.createElement('div');
            backdrop.className = 'ed-modal-backdrop';
            var modal = document.createElement('div');
            modal.className = 'ed-modal' + (cssClass ? ' ' + cssClass : '');
            modal.innerHTML = html;
            backdrop.appendChild(modal);
            document.body.appendChild(backdrop);
        }

        closeModal() {
            var existing = document.querySelector('.ed-modal-backdrop');
            if (existing) existing.remove();
        }

        showToast(message, type) {
            var toast = document.createElement('div');
            toast.className = 'ed-toast' + (type === 'error' ? ' ed-toast--error' : '');
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(function () { toast.classList.add('ed-toast--fade'); }, 2500);
            setTimeout(function () { toast.remove(); }, 3000);
        }

        // Editorial confirmation dialog — replaces browser confirm()
        showConfirm(title, body, action, dangerLabel) {
            this.showModal(
                '<div class="ed-modal__header">' +
                    '<h2 class="ed-modal__title">' + escapeHtml(title) + '</h2>' +
                '</div>' +
                '<div class="ed-modal__body">' +
                    '<div class="ed-confirm-body">' + body + '</div>' +
                '</div>' +
                '<div class="ed-modal__footer">' +
                    '<button class="ed-btn ed-btn--ghost" data-action="modal-cancel">Cancel</button>' +
                    '<button class="ed-btn ed-btn--danger" data-action="' + escapeHtml(action) + '">' + escapeHtml(dangerLabel || 'Confirm') + '</button>' +
                '</div>',
                'ed-modal--admin'
            );
        }

        // ---- Delete ----

        showDeleteConfirm() {
            this.closeAdminMenu();
            var title = document.querySelector('.ed-reader__title');
            var titleText = title ? title.textContent : 'this report';
            this.showConfirm(
                'Delete report',
                '<p>This will permanently delete <strong>"' + escapeHtml(titleText) + '"</strong> and all associated files (summary, images, audio). This cannot be undone.</p>',
                'confirm-delete',
                'Delete'
            );
        }

        async executeDelete() {
            var videoId = this._activeReaderId;
            if (!videoId) return;
            var btn = document.querySelector('[data-action="confirm-delete"]');
            if (btn) { btn.disabled = true; btn.textContent = 'Deleting...'; }
            try {
                var resp = await fetch('/api/delete/' + encodeURIComponent(videoId), { method: 'DELETE' });
                if (!resp.ok) throw new Error('Delete failed (' + resp.status + ')');
                this.closeModal();
                this.closeReader();
                this.showToast('Report deleted');
                var card = document.querySelector('[data-video-id="' + videoId + '"]');
                if (card) {
                    card.style.transition = 'opacity 0.3s ease';
                    card.style.opacity = '0';
                    setTimeout(function () { card.remove(); }, 300);
                }
            } catch (err) {
                this.showToast('Delete failed: ' + err.message, 'error');
                this.closeModal();
            }
        }

        // ---- Regenerate ----

        showRegenerateModal() {
            this.closeAdminMenu();

            var existingSlugs = {};
            if (this._readerVariants) {
                for (var i = 0; i < this._readerVariants.length; i++) {
                    existingSlugs[this._readerVariants[i].variant] = true;
                }
            }

            // Separate text and audio variants
            var textVariants = [];
            var audioVariants = [];
            for (var v = 0; v < REPROCESS_VARIANTS.length; v++) {
                if (REPROCESS_VARIANTS[v].kind === 'audio') {
                    audioVariants.push(REPROCESS_VARIANTS[v]);
                } else {
                    textVariants.push(REPROCESS_VARIANTS[v]);
                }
            }
            var generatedCount = 0;
            for (var slug in existingSlugs) {
                if (Object.prototype.hasOwnProperty.call(existingSlugs, slug)) generatedCount++;
            }
            var missingCount = REPROCESS_VARIANTS.length - generatedCount;

            var title = '';
            var titleEl = document.querySelector('.ed-reader__title');
            if (titleEl) title = titleEl.textContent || '';

            var html = '<div class="ed-modal__header ed-modal__header--spread">' +
                '<div>' +
                    '<div class="ed-modal__eyebrow">Admin action</div>' +
                    '<h2 class="ed-modal__title">Regenerate Summary</h2>' +
                    '<p class="ed-modal__subtitle">Click the outputs you want to refresh for <strong>' + escapeHtml(title || 'this report') + '</strong>. Existing versions can be regenerated in place.</p>' +
                '</div>' +
                '<button class="ed-modal__close" data-action="modal-cancel" aria-label="Close">&times;</button>' +
            '</div>' +
            '<div class="ed-modal__body">';
            html += '<div class="ed-regen-summary">' +
                '<div class="ed-regen-summary__pill">' + generatedCount + ' generated</div>' +
                '<div class="ed-regen-summary__pill ed-regen-summary__pill--muted">' + missingCount + ' missing</div>' +
            '</div>';
            html += '<div class="ed-regen-direct">';
            html += '<div class="ed-regen-group">';
            html += '<div class="ed-regen-group__label">Text summaries</div>';
            html += '<div class="ed-regen-grid">';
            for (var tt = 0; tt < textVariants.length; tt++) {
                html += this._renderRegenCard(textVariants[tt], !!existingSlugs[textVariants[tt].id]);
            }
            html += '</div></div>';

            html += '<div class="ed-regen-group">';
            html += '<div class="ed-regen-group__label">Audio outputs</div>';
            html += '<div class="ed-regen-grid">';
            for (var aa = 0; aa < audioVariants.length; aa++) {
                html += this._renderRegenCard(audioVariants[aa], !!existingSlugs[audioVariants[aa].id]);
            }
            html += '</div></div></div>';

            html += '</div>' +
                '<div class="ed-modal__footer">' +
                    '<div class="ed-modal__footer-note">Existing outputs can be regenerated without deleting the current version first.</div>' +
                    '<button class="ed-btn ed-btn--ghost" data-action="modal-cancel">Cancel</button>' +
                    '<button class="ed-btn ed-btn--primary" data-action="confirm-regenerate">Generate selected outputs</button>' +
                '</div>';

            this.showModal(html, 'ed-modal--compact ed-modal--admin');
            this._syncRegenSelectionState();
        }

        _renderRegenCard(variant, exists) {
            var cls = 'ed-regen-card' + (exists ? ' ed-regen-card--exists' : '');
            var html = '<label class="' + cls + '" data-regen-card>' +
                '<input type="checkbox" class="ed-regen-card__check" value="' + escapeHtml(variant.id) + '" data-kind="' + variant.kind + '">' +
                '<div class="ed-regen-card__surface">' +
                    '<div class="ed-regen-card__top">' +
                        '<div class="ed-regen-card__info">' +
                            '<span class="ed-regen-card__label">' + escapeHtml(variant.label) + '</span>' +
                            '<span class="ed-regen-card__hint">' + escapeHtml(variant.hint || '') + '</span>' +
                        '</div>' +
                        '<span class="ed-regen-card__marker">&#10003;</span>' +
                    '</div>' +
                    '<div class="ed-regen-card__meta">' +
                        (exists ? '<span class="ed-regen-card__badge">Already generated</span>' : '<span class="ed-regen-card__subtle">Not yet generated</span>') +
                    '</div>';

            if (variant.proficiency) {
                html += '<div class="ed-regen-card__proficiency" hidden>' +
                    '<button type="button" class="ed-proficiency-btn ed-proficiency-btn--active" data-proficiency="intermediate">Intermediate</button>' +
                    '<button type="button" class="ed-proficiency-btn" data-proficiency="beginner">Beginner</button>' +
                    '<button type="button" class="ed-proficiency-btn" data-proficiency="advanced">Advanced</button>' +
                '</div>';
            }

            html += '</div></label>';
            return html;
        }

        _syncRegenSelectionState() {
            var cards = document.querySelectorAll('[data-regen-card]');
            for (var i = 0; i < cards.length; i++) {
                var check = cards[i].querySelector('.ed-regen-card__check');
                var selected = !!(check && check.checked);
                cards[i].classList.toggle('ed-regen-card--selected', selected);
                var prof = cards[i].querySelector('.ed-regen-card__proficiency');
                if (prof) prof.hidden = !selected;
            }
            this._updateRegenCta();
        }

        _updateRegenCta() {
            var checked = document.querySelectorAll('.ed-regen-card__check:checked');
            var cta = document.querySelector('[data-action="confirm-regenerate"]');
            if (cta) {
                cta.textContent = checked.length ? this._getRegenActionLabel(checked) : 'Generate selected outputs';
                cta.disabled = !checked.length;
            }
        }

        _getRegenActionLabel(checkedNodes) {
            var existing = 0;
            for (var i = 0; i < checkedNodes.length; i++) {
                var card = checkedNodes[i].closest('[data-regen-card]');
                if (card && card.classList.contains('ed-regen-card--exists')) existing++;
            }
            var count = checkedNodes.length;
            if (existing === 0) return 'Generate ' + count + ' output' + (count === 1 ? '' : 's');
            if (existing === count) return 'Regenerate ' + count + ' output' + (count === 1 ? '' : 's');
            return 'Update ' + count + ' output' + (count === 1 ? '' : 's');
        }


        async executeRegenerate() {
            var videoId = this._activeReaderId;
            if (!videoId) return;

            var self = this;
            this.requireAdminToken(function (token) { self._doRegenerate(token); });
        }

        async _doRegenerate(token) {
            var checkboxes = document.querySelectorAll('.ed-regen-card__check:checked');
            if (!checkboxes.length) { this.showToast('Select at least one variant', 'error'); return; }

            var summaryTypes = [];
            var regenerateAudio = false;
            for (var i = 0; i < checkboxes.length; i++) {
                var kind = checkboxes[i].dataset.kind;
                var val = checkboxes[i].value;
                if (kind === 'audio') {
                    regenerateAudio = true;
                    var card = checkboxes[i].closest('[data-regen-card]');
                    var profBtn = card ? card.querySelector('.ed-proficiency-btn--active') : null;
                    if (profBtn && (val === 'audio-fr' || val === 'audio-es')) {
                        summaryTypes.push(val + ':' + profBtn.dataset.proficiency);
                    } else {
                        summaryTypes.push(val);
                    }
                } else {
                    summaryTypes.push(val);
                }
            }

            var btn = document.querySelector('[data-action="confirm-regenerate"]');
            if (btn) { btn.disabled = true; btn.textContent = 'Regenerating...'; }

            try {
                var resp = await fetch('/api/reprocess', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Reprocess-Token': token
                    },
                    body: JSON.stringify({
                        video_id: this._activeReaderId,
                        regenerate_audio: regenerateAudio,
                        summary_types: summaryTypes
                    })
                });
                if (!resp.ok) throw new Error('Regenerate failed (' + resp.status + ')');
                this.closeModal();
                this.showToast('Regeneration started');
            } catch (err) {
                this.showToast('Regenerate failed: ' + err.message, 'error');
                this.closeModal();
            }
        }

        // ---- Manage Images ----

        showImagesModal() {
            this.closeAdminMenu();
            if (!this._readerData) {
                this.showToast('No report data loaded', 'error');
                return;
            }
            this._imageMode = 'ai1';
            this._renderImagesModal();
        }

        _getImageAnalysis() {
            var analysis = (this._readerData && this._readerData.analysis) || {};
            var allVars = Array.isArray(analysis.summary_image_variants) ? analysis.summary_image_variants : [];
            var mode = this._imageMode || 'ai1';

            // Derive AI1 variants (non-AI2 entries)
            var a1Variants = allVars.filter(function (v) { return !isAi2Variant(v); })
                .sort(function (a, b) {
                    var ca = (a.created_at || '') + '';
                    var cb = (b.created_at || '') + '';
                    return ca < cb ? 1 : ca > cb ? -1 : 0;
                });

            // Derive AI2 variants from shared array
            var ai2Urls = getAi2VariantUrls(analysis);
            var urlToPrompt = {};
            var urlToCreated = {};
            allVars.forEach(function (v) {
                if (v.url) {
                    var nu = normalizeAssetUrl(v.url);
                    urlToPrompt[nu] = v.prompt || '';
                    if (v.created_at) urlToCreated[nu] = String(v.created_at);
                }
            });
            var a2Variants = ai2Urls
                .map(function (u) {
                    return { url: u, image_mode: 'ai2', prompt: urlToPrompt[normalizeAssetUrl(u)] || '', created_at: urlToCreated[normalizeAssetUrl(u)] || '' };
                })
                .sort(function (a, b) {
                    var ca = (a.created_at || '') + '';
                    var cb = (b.created_at || '') + '';
                    return ca < cb ? 1 : ca > cb ? -1 : 0;
                });

            // Selected URLs (normalized for comparison)
            var a1Selected = normalizeAssetUrl(analysis.summary_image_selected_url || this._readerData.summary_image_url || '');
            var a2Selected = normalizeAssetUrl(analysis.summary_image_ai2_url || '');

            // Prompt defaults
            var a1Default = analysis.summary_image_prompt || '';
            if (!a1Default) {
                for (var i = allVars.length - 1; i >= 0; i--) {
                    if (!isAi2Variant(allVars[i]) && allVars[i].prompt) { a1Default = allVars[i].prompt; break; }
                }
                if (!a1Default) a1Default = analysis.summary_image_prompt_last_used || '';
            }
            var a2Default = analysis.summary_image_ai2_prompt || analysis.summary_image_ai2_prompt_last_used || '';
            if (!a2Default) {
                for (var j = allVars.length - 1; j >= 0; j--) {
                    if (isAi2Variant(allVars[j]) && allVars[j].prompt) { a2Default = allVars[j].prompt; break; }
                }
            }

            // Original prompts
            var a1Original = analysis.summary_image_prompt_original || '';
            var a2Original = analysis.summary_image_ai2_prompt_original || '';

            // Has AI2 data?
            var hasAi2 = !!(analysis.summary_image_ai2_url || analysis.summary_image_ai2_prompt || a2Variants.length);

            return {
                analysis: analysis,
                allVars: allVars,
                mode: mode,
                hasAi2: hasAi2,
                a1Variants: a1Variants,
                a2Variants: a2Variants,
                a1Selected: a1Selected,
                a2Selected: a2Selected,
                a1Default: a1Default,
                a2Default: a2Default,
                a1Original: a1Original,
                a2Original: a2Original
            };
        }

        _renderImageVariantRow(variant, selectedUrl, mode) {
            var vUrl = normalizeAssetUrl(variant.url || '');
            var isSel = vUrl && urlPath(vUrl) === urlPath(selectedUrl);
            var when = timeAgo(variant.created_at);
            var preview = (variant.prompt || '').trim();
            if (preview.length > 150) preview = preview.slice(0, 147) + '...';
            var thumbHtml = isSel
                ? '<div class="ed-img-row__thumb ed-img-row__thumb--current">' +
                    '<img src="' + escapeHtml(vUrl) + '" alt="" loading="lazy" onerror="this.style.display=\'none\'">' +
                    '<span class="ed-img-row__thumb-badge">Current</span>' +
                '</div>'
                : '<button class="ed-img-row__thumb ed-img-row__thumb-btn" type="button" data-action="select-image-variant" data-url="' + escapeHtml(vUrl) + '" aria-label="Make this the current image">' +
                    '<img src="' + escapeHtml(vUrl) + '" alt="" loading="lazy" onerror="this.style.display=\'none\'">' +
                    '<span class="ed-img-row__thumb-badge">Make current</span>' +
                '</button>';

            return '<article class="ed-img-row' + (isSel ? ' ed-img-row--selected' : '') + '" data-variant-url="' + escapeHtml(vUrl) + '">' +
                thumbHtml +
                '<div class="ed-img-row__body">' +
                    '<div class="ed-img-row__top">' +
                        '<div class="ed-img-row__meta">' +
                            '<span class="ed-img-row__time">' + escapeHtml(when || 'Recently generated') + '</span>' +
                            (isSel ? '<span class="ed-img-row__selected-badge">Selected</span>' : '') +
                        '</div>' +
                        '<div class="ed-img-row__prompt">' + escapeHtml(preview || 'Saved without a custom prompt.') + '</div>' +
                    '</div>' +
                    '<div class="ed-img-row__actions">' +
                        '<button class="ed-btn ed-btn--ghost ed-btn--sm" data-action="use-variant-prompt" data-url="' + escapeHtml(vUrl) + '">Use this prompt</button>' +
                        (isSel ? '<span class="ed-img-row__current">Current image</span>' : '<button class="ed-btn ed-btn--secondary ed-btn--sm" data-action="select-image-variant" data-url="' + escapeHtml(vUrl) + '">Select image</button>') +
                        '<button class="ed-btn ed-btn--ghost ed-btn--sm ed-btn--danger-ghost" data-action="confirm-delete-image" data-url="' + escapeHtml(vUrl) + '">Delete</button>' +
                    '</div>' +
                '</div>' +
            '</article>';
        }

        _renderPendingImageRow(pending) {
            var preview = (pending && pending.prompt ? pending.prompt.trim() : '');
            if (preview.length > 150) preview = preview.slice(0, 147) + '...';

            return '<article class="ed-img-row ed-img-row--pending">' +
                '<div class="ed-img-row__thumb ed-img-row__thumb--pending">' +
                    '<div class="ed-img-row__thumb-skeleton"></div>' +
                '</div>' +
                '<div class="ed-img-row__body">' +
                    '<div class="ed-img-row__top">' +
                        '<div class="ed-img-row__meta">' +
                            '<span class="ed-img-row__time">Generating now</span>' +
                            '<span class="ed-img-row__selected-badge ed-img-row__selected-badge--pending">Pending</span>' +
                        '</div>' +
                        '<div class="ed-img-row__prompt">' + escapeHtml(preview || 'Generating a new image variant from the current prompt.') + '</div>' +
                    '</div>' +
                    '<div class="ed-img-row__actions">' +
                        '<span class="ed-img-row__current">Waiting for new variant</span>' +
                    '</div>' +
                '</div>' +
            '</article>';
        }

        _renderImagesModal() {
            var data = this._getImageAnalysis();
            var mode = data.mode;
            var variants = mode === 'ai2' ? data.a2Variants : data.a1Variants;
            var selectedUrl = mode === 'ai2' ? data.a2Selected : data.a1Selected;
            var defaultPrompt = mode === 'ai2' ? data.a2Default : data.a1Default;
            var originalPrompt = mode === 'ai2' ? data.a2Original : data.a1Original;
            var modeLabel = mode === 'ai2' ? 'AI2' : 'AI1';
            var pending = this._pendingImageGeneration && this._pendingImageGeneration.mode === mode ? this._pendingImageGeneration : null;
            if (pending) {
                var resolved = variants.some(function (variant) {
                    if (!variant || !variant.created_at) return false;
                    var created = Date.parse(variant.created_at);
                    return !Number.isNaN(created) && created >= (pending.startedAt - 2000);
                });
                if (resolved) {
                    this._pendingImageGeneration = null;
                    pending = null;
                }
            }
            var pendingCount = pending ? 1 : 0;
            var countLabel = (variants.length + pendingCount) ? (variants.length + pendingCount) + ' saved variant' + ((variants.length + pendingCount) === 1 ? '' : 's') : 'No saved variants';

            var html = '<div class="ed-modal__header ed-modal__header--spread">' +
                '<div>' +
                    '<div class="ed-modal__eyebrow">Admin action</div>' +
                    '<h2 class="ed-modal__title">Manage Images</h2>' +
                    '<p class="ed-modal__subtitle">Refine prompts, choose the active image, and clean up older variants without leaving the reader.</p>' +
                '</div>' +
                '<button class="ed-modal__close" data-action="modal-cancel" aria-label="Close">&times;</button>' +
            '</div>' +
            '<div class="ed-modal__body ed-images-modal">';

            html += '<div class="ed-images-toolbar">';
            if (data.hasAi2) {
                html += '<div class="ed-images-mode-switch">' +
                    '<button class="ed-images-mode-btn' + (mode === 'ai1' ? ' ed-images-mode-btn--active' : '') +
                    '" data-action="switch-image-mode" data-mode="ai1">AI1</button>' +
                    '<button class="ed-images-mode-btn' + (mode === 'ai2' ? ' ed-images-mode-btn--active' : '') +
                    '" data-action="switch-image-mode" data-mode="ai2">AI2</button>' +
                '</div>';
            } else {
                html += '<div class="ed-images-mode-pill">' + modeLabel + ' workspace</div>';
            }
            html += '<button class="ed-btn ed-btn--ghost ed-btn--sm ed-btn--danger-ghost" data-action="confirm-delete-all-images">Delete all AI images...</button>' +
            '</div>';

            html += '<div class="ed-images-layout' + (variants.length <= 1 ? ' ed-images-layout--sparse' : '') + '">';
            html += '<section class="ed-images-compose">' +
                '<div class="ed-images-panel__header">' +
                    '<div>' +
                        '<div class="ed-images-panel__eyebrow">' + modeLabel + ' prompt</div>' +
                        '<h3 class="ed-images-panel__title">Create a new variant</h3>' +
                    '</div>' +
                '</div>' +
                '<div class="ed-images-flow-note">Edit the prompt, generate a fresh variant, then choose the image you want to keep.</div>' +
                '<textarea class="ed-images-prompt__textarea" rows="5" data-prompt-input>' + escapeHtml(defaultPrompt) + '</textarea>';

            if (originalPrompt) {
                html += '<div class="ed-images-prompt__default">Default: ' + escapeHtml(originalPrompt) + '</div>';
            }

            html += '<div class="ed-images-prompt__hint">Use a saved prompt as a starting point, or restore the original baseline before generating a new variant.</div>';
            html += '<div class="ed-images-prompt__hint">Click a library row to reuse its prompt. Click the image itself to make that variant current.</div>';
            html += '<div class="ed-images-prompt__actions">' +
                '<button class="ed-btn ed-btn--primary" data-action="save-image-prompt">' + (pending ? 'Generating...' : 'Generate new variant') + '</button>' +
                '<button class="ed-btn ed-btn--secondary" data-action="use-default-prompt">Reset to default</button>' +
            '</div>' +
            (selectedUrl ? '<div class="ed-images-prompt__hint">The library highlights the image currently shown in the reader.</div>' : '') +
            '</section>';

            html += '<section class="ed-images-library">' +
                '<div class="ed-images-panel__header">' +
                    '<div>' +
                        '<div class="ed-images-panel__eyebrow">' + modeLabel + ' library</div>' +
                        '<h3 class="ed-images-panel__title">' + countLabel + '</h3>' +
                    '</div>' +
                '</div>';

            if (pending) {
                html += '<div class="ed-images-status">' +
                    '<div class="ed-images-status__title">Generation requested</div>' +
                    '<div class="ed-images-status__text">A new ' + modeLabel + ' variant is on the way. The pending row below will resolve into a real image once generation finishes.</div>' +
                '</div>';
            }

            if (variants.length > 0 || pending) {
                html += '<div class="ed-images-rows">';
                if (pending) {
                    html += this._renderPendingImageRow(pending);
                }
                for (var i = 0; i < variants.length; i++) {
                    html += this._renderImageVariantRow(variants[i], selectedUrl, mode);
                }
                html += '</div>';
            } else {
                html += '<div class="ed-images-empty">' +
                    '<div class="ed-images-empty__title">No ' + modeLabel + ' variants yet</div>' +
                    '<div class="ed-images-empty__text">Save a prompt above to generate the first image for this mode.</div>' +
                '</div>';
            }

            html += '</section></div></div>' +
                '<div class="ed-modal__footer">' +
                    '<button class="ed-btn ed-btn--ghost" data-action="modal-cancel">Close</button>' +
                '</div>';

            this.showModal(html, 'ed-modal--wide ed-modal--images ed-modal--admin');
        }

        _loadVariantPromptByUrl(url) {
            if (!url) return false;
            var data = this._getImageAnalysis();
            var variants = data.mode === 'ai2' ? data.a2Variants : data.a1Variants;
            var normalizedTarget = normalizeAssetUrl(url);
            var match = null;
            for (var i = 0; i < variants.length; i++) {
                if (normalizeAssetUrl(variants[i].url) === normalizedTarget) { match = variants[i]; break; }
            }
            if (match && match.prompt) {
                var textarea = document.querySelector('[data-prompt-input]');
                if (textarea) {
                    textarea.value = match.prompt;
                    textarea.focus();
                    textarea.setSelectionRange(0, textarea.value.length);
                }
                return true;
            }
            return false;
        }

        switchImageMode(btn) {
            this._imageMode = btn.dataset.mode || 'ai1';
            this._renderImagesModal();
        }

        useVariantPrompt(btn) {
            var url = btn ? btn.dataset.url : '';
            this._loadVariantPromptByUrl(url);
        }

        useDefaultPrompt() {
            var data = this._getImageAnalysis();
            var original = data.mode === 'ai2' ? (data.a2Original || data.a2Default) : (data.a1Original || data.a1Default);
            if (original) {
                var textarea = document.querySelector('[data-prompt-input]');
                if (textarea) textarea.value = original;
            }
        }

        async executeSetImagePrompt() {
            var videoId = this._activeReaderId;
            if (!videoId) return;

            var self = this;
            this.requireAdminToken(function (token) { self._doSetImagePrompt(token); });
        }

        async _doSetImagePrompt(token) {
            var textarea = document.querySelector('[data-prompt-input]');
            var newPrompt = textarea ? textarea.value.trim() : '';
            if (!newPrompt) { this.showToast('Enter a prompt', 'error'); return; }

            var mode = this._imageMode || 'ai1';
            var btn = document.querySelector('[data-action="save-image-prompt"]');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Generating...';
            }
            try {
                var resp = await fetch('/api/set-image-prompt', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                    body: JSON.stringify({ video_id: this._activeReaderId, prompt: newPrompt, mode: mode })
                });
                if (!resp.ok) throw new Error('Failed (' + resp.status + ')');
                this._pendingImageGeneration = { mode: mode, prompt: newPrompt, startedAt: Date.now() };
                this.showToast('Image generation started');
                this._renderImagesModal();
            } catch (err) {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = 'Generate new variant';
                }
                this.showToast('Failed: ' + err.message, 'error');
            }
        }

        async executeSelectImageVariant(btn) {
            var videoId = this._activeReaderId;
            var url = btn ? btn.dataset.url : '';
            if (!videoId || !url) return;

            var self = this;
            this.requireAdminToken(function (token) { self._doSelectImage(token, url); });
        }

        async _doSelectImage(token, url) {
            var mode = this._imageMode || 'ai1';
            try {
                var resp = await fetch('/api/select-image-variant', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                    body: JSON.stringify({ video_id: this._activeReaderId, url: url, mode: mode })
                });
                if (!resp.ok) throw new Error('Failed (' + resp.status + ')');
                this.showToast('Image selected');
                // Update local data — AI1 must update BOTH fields
                if (this._readerData && this._readerData.analysis) {
                    if (mode === 'ai2') {
                        this._readerData.analysis.summary_image_ai2_url = url;
                    } else {
                        this._readerData.analysis.summary_image_selected_url = url;
                        this._readerData.summary_image_url = url;
                    }
                }
                if (this._pendingImageGeneration && this._pendingImageGeneration.mode === mode) {
                    this._pendingImageGeneration = null;
                }
                this._renderImagesModal();
            } catch (err) {
                this.showToast('Failed: ' + err.message, 'error');
            }
        }

        showDeleteImageConfirm(btn) {
            var url = btn ? btn.dataset.url : '';
            if (!url) return;
            this._pendingDeleteUrl = url;
            this.showConfirm(
                'Delete image variant',
                '<p>Permanently delete this image variant?</p>',
                'do-delete-image',
                'Delete'
            );
        }

        async executeDeleteImageVariant() {
            var videoId = this._activeReaderId;
            var url = this._pendingDeleteUrl;
            if (!videoId || !url) return;

            var self = this;
            this.requireAdminToken(function (token) { self._doDeleteImage(token, url); });
        }

        async _doDeleteImage(token, url) {
            try {
                var resp = await fetch('/api/delete-image-variant', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                    body: JSON.stringify({ video_id: this._activeReaderId, url: url })
                });
                if (!resp.ok) throw new Error('Failed (' + resp.status + ')');
                this.showToast('Variant deleted');

                // Clear selected pointer if deleting the selected image
                var mode = this._imageMode || 'ai1';
                if (this._readerData && this._readerData.analysis) {
                    var a = this._readerData.analysis;
                    var normalizedTarget = urlPath(normalizeAssetUrl(url));
                    a.summary_image_variants = (a.summary_image_variants || []).filter(function (variant) {
                        return urlPath(normalizeAssetUrl(variant && variant.url)) !== normalizedTarget;
                    });
                    if (mode === 'ai1' && urlPath(normalizeAssetUrl(a.summary_image_selected_url)) === urlPath(normalizeAssetUrl(url))) {
                        a.summary_image_selected_url = '';
                    }
                    if (mode === 'ai1' && urlPath(normalizeAssetUrl(this._readerData.summary_image_url)) === urlPath(normalizeAssetUrl(url))) {
                        this._readerData.summary_image_url = '';
                    }
                    if (mode === 'ai2' && urlPath(normalizeAssetUrl(a.summary_image_ai2_url)) === urlPath(normalizeAssetUrl(url))) {
                        a.summary_image_ai2_url = '';
                    }
                }

                this.closeModal();
                this._renderImagesModal();
            } catch (err) {
                this.showToast('Failed: ' + err.message, 'error');
                this.closeModal();
            }
        }

        showDeleteAllImagesConfirm() {
            this.showConfirm(
                'Delete all AI images',
                '<p>This will permanently delete all AI-generated images (AI1 and AI2) for this report. This cannot be undone.</p>',
                'do-delete-all-images',
                'Delete all'
            );
        }

        async executeDeleteAllImages() {
            var videoId = this._activeReaderId;
            if (!videoId) return;

            var self = this;
            this.requireAdminToken(function (token) { self._doDeleteAllImages(token); });
        }

        async _doDeleteAllImages(token) {
            try {
                var resp = await fetch('/api/delete-all-ai-images', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                    body: JSON.stringify({ video_id: this._activeReaderId, modes: ['ai1', 'ai2'] })
                });
                if (!resp.ok) throw new Error('Failed (' + resp.status + ')');
                this.showToast('All AI images deleted');
                if (this._readerData && this._readerData.analysis) {
                    this._readerData.analysis.summary_image_variants = [];
                    this._readerData.analysis.summary_image_ai2_url = '';
                    this._readerData.analysis.summary_image_selected_url = '';
                    this._readerData.summary_image_url = '';
                }
                this._pendingImageGeneration = null;
                this.closeModal();
                this._renderImagesModal();
            } catch (err) {
                this.showToast('Failed: ' + err.message, 'error');
                this.closeModal();
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
        // Apply saved theme
        if (_theme !== 'default') {
            document.documentElement.setAttribute('data-ed-theme', _theme);
        }
        var app = new EditorialDashboard();
        app.readStateFromURL();
        app.bindEvents();
        app.renderTopbar();
        await app.loadFilters();
        app.renderTopbar();
        await app.loadContent();
        app.connectEventSource();
        window.__editorialApp = app;
    }
})();
