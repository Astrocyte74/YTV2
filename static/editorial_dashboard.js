/* ============================================================
   YTV2 Editorial Dashboard — Skeleton
   ============================================================ */

(function () {
    'use strict';

    // ---- Inline helpers (duplicated from classic, no imports) ----

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

    // ---- EditorialDashboard class ----

    class EditorialDashboard {
        constructor() {
            this.config = window.EDITORIAL_CONFIG || { features: {} };
            this.nasConfig = window.NAS_CONFIG || {};
            this.dashboardConfig = window.DASHBOARD_CONFIG || {};

            this.state = {
                items: [],
                page: 1,
                size: 50,
                filters: {},
                search: '',
                sort: 'newest',
                loading: false,
                error: null,
            };

            this.mounts = {
                hero: document.getElementById('ed-hero'),
                sections: document.getElementById('ed-sections'),
                rail: document.getElementById('ed-rail'),
                player: document.getElementById('ed-player'),
            };
        }

        async loadContent() {
            this.state.loading = true;
            this.renderLoading();

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
                this.state.items = data.reports || data.items || [];
                console.log('[Editorial] Loaded', this.state.items.length, 'reports');
                this.render();
            } catch (err) {
                this.state.error = err.message;
                console.error('[Editorial] loadContent failed:', err);
                this.renderError();
            } finally {
                this.state.loading = false;
            }
        }

        render() {
            if (!this.state.items.length) {
                this.renderEmpty();
                return;
            }
            // Phase 1 will implement real card rendering
            if (this.mounts.hero) {
                this.mounts.hero.innerHTML =
                    '<div class="ed-loading">Loaded ' + this.state.items.length +
                    ' reports — card rendering coming in Phase 1</div>';
            }
        }

        renderLoading() {
            if (this.mounts.hero) {
                this.mounts.hero.innerHTML = '<div class="ed-loading">Loading...</div>';
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

        bindEvents() {
            // Phase 1 will wire up search, filters, card clicks
        }
    }

    // ---- Bootstrap ----
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function init() {
        console.log('[Editorial] Initializing...');
        var app = new EditorialDashboard();
        app.bindEvents();
        app.loadContent();
        window.__editorialApp = app; // for debugging
    }
})();
