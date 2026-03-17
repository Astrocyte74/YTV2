(() => {
  // Simple telemetry logging
  const isMobile = window.innerWidth <= 768;
  console.log('[V2 Telemetry] v2_rendered', { ua_is_mobile: isMobile, viewport: `${window.innerWidth}x${window.innerHeight}` });

  const $ = (id) => document.getElementById(id);

  const VARIANT_META = {
    'comprehensive': { label: 'Comprehensive', icon: '📝', kind: 'text' },
    'bullet-points': { label: 'Key Points', icon: '🎯', kind: 'text' },
    'key-insights': { label: 'Insights', icon: '💡', kind: 'text' },
    'deep-research': { label: 'Deep Research', icon: '🔎', kind: 'research' },
    'audio': { label: 'Audio (EN)', icon: '🎙️', kind: 'audio' },
    'audio-fr': { label: 'Audio (FR)', icon: '🎙️🇫🇷', kind: 'audio' },
    'audio-es': { label: 'Audio (ES)', icon: '🎙️🇪🇸', kind: 'audio' }
  };

  const normalizeVariantId = (value) => {
    if (!value) return '';
    return String(value).toLowerCase().replace(/_/g, '-');
  };

  const prettifyVariantId = (value) => {
    if (!value) return '';
    const normalized = normalizeVariantId(value);
    return normalized.replace(/[-_]+/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());
  };

  const formatSummaryText = (text) => {
    if (!text || typeof text !== 'string') return '';
    const trimmed = text.replace(/\r\n?/g, '\n').trim();
    if (!trimmed) return '';

    // Check for markdown tables
    const tableRegex = /^\|.+\|[\r\n]+\|[-:| ]+\|[\r\n]+(\|.+\|[\r\n]*)+/gm;
    if (tableRegex.test(trimmed)) {
      return formatMarkdownWithTables(trimmed);
    }

    // basic bullet detection
    const lines = trimmed.split(/\n+/);
    const htmlLines = lines.map((line) => {
      if (/^\s*[-*•]/.test(line)) {
        return `<li>${line.replace(/^\s*[-*•]\s*/, '')}</li>`;
      }
      return `<p>${line}</p>`;
    });
    if (htmlLines.every((line) => line.startsWith('<li>'))) {
      return `<ul>${htmlLines.join('')}</ul>`;
    }
    return htmlLines.join('\n');
  };

  const formatMarkdownWithTables = (text) => {
    // Split into table and non-table sections
    const parts = [];
    let lastIndex = 0;
    const tableBlockRegex = /(\|.+\|[\r\n]+\|[-:| ]+\|[\r\n]+(?:\|.+\|[\r\n]*)+)/g;
    let match;

    while ((match = tableBlockRegex.exec(text)) !== null) {
      // Add text before table
      if (match.index > lastIndex) {
        const before = text.slice(lastIndex, match.index).trim();
        if (before) parts.push({ type: 'text', content: before });
      }
      // Add table
      parts.push({ type: 'table', content: match[1].trim() });
      lastIndex = match.index + match[0].length;
    }
    // Add remaining text
    if (lastIndex < text.length) {
      const after = text.slice(lastIndex).trim();
      if (after) parts.push({ type: 'text', content: after });
    }

    return parts.map(part => {
      if (part.type === 'table') {
        return formatTable(part.content);
      }
      return formatTextBlock(part.content);
    }).join('\n');
  };

  const formatTable = (tableText) => {
    const lines = tableText.split(/[\r\n]+/).filter(l => l.trim());
    if (lines.length < 2) return '';

    const parseRow = (line) => {
      return line.split('|')
        .map(cell => cell.trim())
        .filter((_, i, arr) => i > 0 && i < arr.length - 1); // Remove first/last empty cells
    };

    const headerCells = parseRow(lines[0]);
    const bodyLines = lines.slice(2); // Skip header and separator

    const headerHtml = headerCells.map(cell => `<th>${cell}</th>`).join('');
    const bodyHtml = bodyLines.map(line => {
      const cells = parseRow(line);
      return `<tr>${cells.map(cell => `<td>${cell}</td>`).join('')}</tr>`;
    }).join('');

    return `<table class="deep-research-table"><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`;
  };

  const formatTextBlock = (text) => {
    const lines = text.split(/\n+/);
    const htmlLines = lines.map((line) => {
      if (/^\s*[-*•]/.test(line)) {
        return `<li>${line.replace(/^\s*[-*•]\s*/, '')}</li>`;
      }
      if (/^#{1,6}\s/.test(line)) {
        const level = line.match(/^(#{1,6})\s/)[1].length;
        const content = line.replace(/^#{1,6}\s+/, '');
        return `<h${level}>${content}</h${level}>`;
      }
      return `<p>${line}</p>`;
    });
    if (htmlLines.every((line) => line.startsWith('<li>'))) {
      return `<ul>${htmlLines.join('')}</ul>`;
    }
    return htmlLines.join('\n');
  };

  const escapeHtml = (value) => {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  };

  const initReportMetaTabs = () => {
    const metas = document.querySelectorAll('[data-report-meta]');
    if (!metas.length) return;
    const setTabState = (btn, active) => {
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
      btn.classList.toggle('bg-slate-100', active);
      btn.classList.toggle('text-slate-700', active);
      btn.classList.toggle('dark:bg-slate-800', active);
      btn.classList.toggle('dark:text-slate-200', active);
      btn.classList.toggle('bg-white', !active);
      btn.classList.toggle('text-slate-600', !active);
      btn.classList.toggle('dark:bg-slate-900', !active);
      btn.classList.toggle('dark:text-slate-300', !active);
    };

    metas.forEach((metaRoot) => {
      const tabs = Array.from(metaRoot.querySelectorAll('[data-report-meta-tab]'));
      const panels = Array.from(metaRoot.querySelectorAll('[data-report-meta-panel]'));
      if (!tabs.length || !panels.length) return;
      const activate = (tabId) => {
        const wanted = String(tabId || '');
        tabs.forEach((btn) => {
          const active = btn.getAttribute('data-report-meta-tab') === wanted;
          setTabState(btn, active);
        });
        panels.forEach((panel) => {
          const active = panel.getAttribute('data-report-meta-panel') === wanted;
          panel.classList.toggle('hidden', !active);
        });
      };
      tabs.forEach((btn) => {
        btn.addEventListener('click', (event) => {
          event.preventDefault();
          event.stopPropagation();
          activate(btn.getAttribute('data-report-meta-tab'));
        });
      });
      const initiallyPressed = tabs.find((btn) => btn.getAttribute('aria-pressed') === 'true');
      activate(initiallyPressed?.getAttribute('data-report-meta-tab') || tabs[0].getAttribute('data-report-meta-tab'));
    });
  };

  const initSummaryVariants = () => {
    const variantData = Array.isArray(window.SUMMARY_VARIANT_DATA) ? window.SUMMARY_VARIANT_DATA : [];
    const defaultVariant = normalizeVariantId(window.SUMMARY_DEFAULT_VARIANT || 'comprehensive');
    const controls = $("summaryVariantControls");
    const summaryBody = $("summaryBody");
    if (!controls || !summaryBody) return;

    const variants = new Map();
    const audioSource = (() => {
      if (!player) return '';
      const currentSrc = player.currentSrc || '';
      if (currentSrc) return currentSrc;
      const sourceEl = player.querySelector('source');
      return sourceEl ? sourceEl.src : '';
    })();

    const addVariant = (payload = {}) => {
      if (!payload) return;
      const normalized = normalizeVariantId(payload.id || payload.variant || payload.summary_type || payload.type);
      if (!normalized) return;
      if (variants.has(normalized)) return;

      const meta = VARIANT_META[normalized] || { label: prettifyVariantId(normalized), icon: '📝', kind: 'text' };
      const kind = meta.kind || 'text';

      const explicitHtml = payload.html ? String(payload.html) : (payload.content && payload.content.html ? String(payload.content.html) : '');
      const fallbackText = payload.text || payload.content?.text || '';
      const contentHtml = explicitHtml || (kind === 'text' ? formatSummaryText(fallbackText || '') : '');

      if (kind === 'text' && !contentHtml) return;

      variants.set(normalized, {
        id: normalized,
        label: payload.label || meta.label || prettifyVariantId(normalized),
        icon: meta.icon || '📝',
        kind,
        html: contentHtml,
        audioSrc: kind === 'audio' ? (payload.audio_src || payload.audioUrl || audioSource) : null
      });
    };

    variantData.forEach((item) => {
      if (!item || typeof item !== 'object') return;
      addVariant(item);
    });

    if (!variants.size) {
      addVariant({ id: defaultVariant || 'comprehensive', html: summaryBody.innerHTML });
    }

    if (!variants.has(defaultVariant)) {
      addVariant({ id: defaultVariant || 'comprehensive', html: summaryBody.innerHTML });
    }

    if (variants.size <= 1) {
      controls.style.display = 'none';
      return;
    }

    controls.style.display = '';
    controls.innerHTML = Array.from(variants.values()).map((variant) => {
      return `<button type="button" data-variant="${variant.id}"
                class="inline-flex items-center gap-2 rounded-full border border-white/50 bg-white/80 px-3.5 py-1.5 text-sm font-medium text-slate-600 shadow-sm transition hover:bg-white dark:border-slate-700/70 dark:bg-slate-900/60 dark:text-slate-200">
                <span class="text-base">${variant.icon}</span>
                <span>${variant.label}</span>
              </button>`;
    }).join('');

    const setActive = (variantId) => {
      const variant = variants.get(variantId);
      if (!variant) return;

      if (variant.kind === 'audio') {
        summaryBody.innerHTML = renderReportAudioVariant(variant);
        attachReportAudioHandlers(summaryBody, variant);
      } else {
        summaryBody.innerHTML = variant.html;
      }

      controls.querySelectorAll('[data-variant]').forEach((btn) => {
        const active = btn.dataset.variant === variantId;
        btn.classList.toggle('bg-gradient-to-r', active);
        btn.classList.toggle('from-audio-500', active);
        btn.classList.toggle('to-indigo-500', active);
        btn.classList.toggle('text-white', active);
        btn.classList.toggle('shadow-lg', active);
        btn.classList.toggle('border-transparent', active);
        btn.classList.toggle('bg-white/80', !active);
        btn.classList.toggle('dark:bg-slate-900/60', !active);
        btn.classList.toggle('text-slate-600', !active);
        btn.classList.toggle('dark:text-slate-200', !active);
      });

      controls.dataset.currentVariant = variantId;
      refreshAudioVariantState();
      try {
        window.dispatchEvent(new CustomEvent('ytv2:report-variant-changed', {
          detail: { variantId, kind: variant.kind || 'text' }
        }));
      } catch (_) {}
    };

    controls.querySelectorAll('[data-variant]').forEach((btn) => {
      btn.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        setActive(btn.dataset.variant);
      });
    });

    const requestedVariant = getRequestedReportVariantId();
    const initialVariant = variants.has(requestedVariant)
      ? requestedVariant
      : (variants.has(defaultVariant) ? defaultVariant : variants.keys().next().value);
    setActive(initialVariant);
  };

  const REPORT_CONTEXT = (window.REPORT_CONTEXT && typeof window.REPORT_CONTEXT === 'object') ? window.REPORT_CONTEXT : {};

  const getReportVideoId = () => {
    const explicit = String(REPORT_CONTEXT.video_id || '').trim();
    if (explicit) return explicit;
    return String(reprocessBtn?.dataset.videoId || '').trim();
  };

  const getActiveReportVariantId = () => {
    const controls = $('summaryVariantControls');
    return String(controls?.dataset.currentVariant || window.SUMMARY_DEFAULT_VARIANT || 'comprehensive').trim().toLowerCase();
  };

  const getRequestedReportVariantId = () => {
    try {
      const params = new URLSearchParams(window.location.search || '');
      return normalizeVariantId(params.get('variant') || '');
    } catch (_) {
      return '';
    }
  };

  const getActiveReportVariantKind = () => {
    const current = getActiveReportVariantId();
    return VARIANT_META[current]?.kind || 'text';
  };

  const htmlToPlainText = (html) => {
    if (!html) return '';
    const div = document.createElement('div');
    div.innerHTML = String(html);
    div.querySelectorAll('[data-deep-research-launcher]').forEach((node) => node.remove());
    return (div.textContent || '')
      .replace(/\r\n?/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .replace(/[ \t]+\n/g, '\n')
      .trim();
  };

  const getCurrentSummaryTextForResearch = () => {
    const summaryBody = $('summaryBody');
    if (!summaryBody) return '';
    const clone = summaryBody.cloneNode(true);
    clone.querySelectorAll('[data-deep-research-launcher]').forEach((node) => node.remove());
    return (clone.textContent || '')
      .replace(/\r\n?/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .replace(/[ \t]+\n/g, '\n')
      .trim();
  };

  const buildReportSourceContext = () => {
    const videoId = getReportVideoId();
    const sourceUrl = String(REPORT_CONTEXT.source_url || '').trim();
    const sourceType = String(REPORT_CONTEXT.content_source || '').trim().toLowerCase() || (videoId ? 'youtube' : 'web');
    const title = String(REPORT_CONTEXT.title || document.querySelector('h1')?.textContent || document.title || '').trim();
    const context = {
      title,
      type: sourceType || 'web',
    };
    if (sourceUrl) context.url = sourceUrl;
    else if (videoId) context.url = `https://www.youtube.com/watch?v=${videoId}`;
    return context;
  };

  const promptForReportAdminToken = () => {
    const entered = window.prompt('Enter the dashboard admin token');
    const trimmed = (entered || '').trim();
    if (!trimmed) return '';
    setReprocessToken(trimmed);
    updateReprocessTokenUi();
    return trimmed;
  };

  const buildDeepResearchReturnUrl = () => {
    const url = new URL(window.location.href);
    url.searchParams.set('variant', 'deep-research');
    const videoId = getReportVideoId();
    if (videoId) url.searchParams.set('video_id', videoId);
    return url.toString();
  };

  const updateReportDeepResearchLaunchers = () => {
    const activeKind = getActiveReportVariantKind();
    const shouldShow = activeKind === 'text';
    document.querySelectorAll('[data-deep-research-launcher]').forEach((launcher) => {
      launcher.classList.toggle('hidden', !shouldShow);
    });
  };

  const openReportDeepResearchModal = async () => {
    const videoId = getReportVideoId();
    if (!videoId) {
      window.alert('Deep Research is only available for persisted summaries.');
      return;
    }

    let token = getReprocessToken();
    if (!token) {
      token = promptForReportAdminToken();
    }
    if (!token) return;

    const summaryText = getCurrentSummaryTextForResearch();
    if (!summaryText) {
      window.alert('No summary text is available for Deep Research.');
      return;
    }

    const sourceContext = buildReportSourceContext();
    const overlay = document.createElement('div');
    overlay.className = 'deep-research-modal';
    overlay.innerHTML = `
      <div class="deep-research-modal__backdrop" data-close></div>
      <div class="deep-research-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="deepResearchTitle">
        <div class="deep-research-modal__header">
          <div>
            <div class="deep-research-modal__eyebrow">Deep Research</div>
            <h3 id="deepResearchTitle" class="deep-research-modal__title">Choose your research questions</h3>
            <p class="deep-research-modal__subtitle">Pick up to 3 questions. You can use the suggestions, add your own custom question, or combine both.</p>
          </div>
          <button type="button" class="deep-research-modal__close" data-close aria-label="Close">✕</button>
        </div>
        <div class="deep-research-modal__body">
          <div class="deep-research-modal__status" data-status>Loading suggested questions…</div>
          <div class="deep-research-modal__suggestions" data-suggestions></div>
          <label class="deep-research-modal__label" for="deepResearchCustomQuestion">Custom question</label>
          <textarea id="deepResearchCustomQuestion" class="deep-research-modal__textarea" rows="3" placeholder="Ask your own follow-up question..."></textarea>
          <div class="deep-research-modal__help">The run uses the current summary variant as context and stores the result as a Deep Research variant.</div>
        </div>
        <div class="deep-research-modal__footer">
          <div class="deep-research-modal__error" data-error></div>
          <div class="deep-research-modal__actions">
            <button type="button" class="deep-research-modal__ghost" data-close>Cancel</button>
            <button type="button" class="deep-research-modal__primary" data-run disabled>Run Deep Research</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    const suggestionsHost = overlay.querySelector('[data-suggestions]');
    const statusEl = overlay.querySelector('[data-status]');
    const errorEl = overlay.querySelector('[data-error]');
    const runBtn = overlay.querySelector('[data-run]');
    const customInput = overlay.querySelector('#deepResearchCustomQuestion');
    const close = () => {
      try { document.body.removeChild(overlay); } catch (_) {}
    };

    const state = {
      suggestions: [],
      selected: new Set(),
      loading: true,
      running: false,
    };

    const sync = () => {
      const customQuestion = String(customInput?.value || '').trim();
      const totalSelected = state.selected.size + (customQuestion ? 1 : 0);
      if (errorEl && totalSelected <= 3 && state.running === false) {
        errorEl.textContent = '';
      }
      if (runBtn) {
        runBtn.disabled = state.loading || state.running || totalSelected === 0 || totalSelected > 3;
      }
    };

    const renderSuggestions = () => {
      if (!suggestionsHost) return;
      if (!state.suggestions.length) {
        suggestionsHost.innerHTML = `
          <div class="deep-research-modal__empty">
            No suggested questions were available for this summary. You can still run Deep Research with your own custom question below.
          </div>
        `;
        return;
      }
      suggestionsHost.innerHTML = state.suggestions.map((suggestion) => {
        const checked = state.selected.has(suggestion.id) ? 'checked' : '';
        return `
          <label class="deep-research-modal__option">
            <input type="checkbox" class="deep-research-modal__checkbox" data-suggestion-id="${escapeHtml(suggestion.id)}" ${checked}>
            <span class="deep-research-modal__option-copy">
              <span class="deep-research-modal__option-question">${escapeHtml(suggestion.question || suggestion.label || '')}</span>
              <span class="deep-research-modal__option-reason">${escapeHtml(suggestion.reason || '')}</span>
            </span>
          </label>
        `;
      }).join('');
      suggestionsHost.querySelectorAll('[data-suggestion-id]').forEach((input) => {
        input.addEventListener('change', () => {
          const suggestionId = String(input.getAttribute('data-suggestion-id') || '');
          if (!suggestionId) return;
          if (input.checked) state.selected.add(suggestionId);
          else state.selected.delete(suggestionId);
          sync();
        });
      });
    };

    overlay.querySelectorAll('[data-close]').forEach((btn) => {
      btn.addEventListener('click', (event) => {
        event.preventDefault();
        close();
      });
    });
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) close();
    });
    overlay.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') close();
    });
    customInput?.addEventListener('input', sync);

    try {
      const resp = await fetch('/api/research/follow-up/suggestions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          video_id: videoId,
          summary: summaryText,
          preferred_variant: getActiveReportVariantId(),
          source_context: sourceContext,
          max_suggestions: 4,
        }),
      });
      const payload = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(payload?.detail || payload?.error || `Suggestions failed (${resp.status})`);
      }
      state.suggestions = Array.isArray(payload?.suggestions) ? payload.suggestions : [];
      state.suggestions.filter((item) => item && item.default_selected).forEach((item) => state.selected.add(item.id));
      if (statusEl) statusEl.textContent = state.suggestions.length
        ? 'Suggested questions'
        : 'No suggestions available';
      state.loading = false;
      renderSuggestions();
      sync();
    } catch (error) {
      state.loading = false;
      if (statusEl) statusEl.textContent = 'Suggested questions unavailable';
      if (errorEl) errorEl.textContent = error?.message || 'Unable to load Deep Research suggestions.';
      renderSuggestions();
      sync();
    }

    runBtn?.addEventListener('click', async () => {
      const selectedSuggestions = state.suggestions.filter((item) => state.selected.has(item.id));
      const customQuestion = String(customInput?.value || '').trim();
      const approvedQuestions = [];
      const questionProvenance = [];

      selectedSuggestions.forEach((item) => {
        const question = String(item.question || item.label || '').trim();
        if (!question) return;
        approvedQuestions.push(question);
        questionProvenance.push(String(item.provenance || 'suggested'));
      });
      if (customQuestion) {
        approvedQuestions.push(customQuestion);
        questionProvenance.push('custom');
      }

      const dedupedQuestions = [];
      const dedupedProvenance = [];
      const seen = new Set();
      approvedQuestions.forEach((question, index) => {
        const key = question.toLowerCase();
        if (seen.has(key)) return;
        seen.add(key);
        dedupedQuestions.push(question);
        dedupedProvenance.push(questionProvenance[index] || 'suggested');
      });

      if (!dedupedQuestions.length) {
        if (errorEl) errorEl.textContent = 'Select a suggested question or enter a custom one.';
        sync();
        return;
      }
      if (dedupedQuestions.length > 3) {
        if (errorEl) errorEl.textContent = 'Choose at most 3 questions total.';
        sync();
        return;
      }

      state.running = true;
      if (runBtn) {
        runBtn.disabled = true;
        runBtn.textContent = 'Running…';
      }
      if (errorEl) errorEl.textContent = '';
      if (statusEl) statusEl.textContent = 'Running Deep Research…';

      try {
        const resp = await fetch('/api/research/follow-up/run', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            video_id: videoId,
            summary: summaryText,
            preferred_variant: getActiveReportVariantId(),
            source_context: sourceContext,
            approved_questions: dedupedQuestions,
            question_provenance: dedupedProvenance,
            provider_mode: 'auto',
            depth: 'balanced',
          }),
        });
        const payload = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          throw new Error(payload?.detail || payload?.error || `Deep Research failed (${resp.status})`);
        }
        if (statusEl) statusEl.textContent = 'Deep Research ready. Opening report…';
        window.location.assign(buildDeepResearchReturnUrl());
      } catch (error) {
        state.running = false;
        if (runBtn) {
          runBtn.disabled = false;
          runBtn.textContent = 'Run Deep Research';
        }
        if (statusEl) statusEl.textContent = 'Deep Research failed';
        if (errorEl) errorEl.textContent = error?.message || 'Unable to run Deep Research.';
        sync();
      }
    });
  };

  const player = $("player");
  const playPause = $("playPause");
  const seek = $("seek");
  const timeMeta = $("timeMeta");
  const rateBtn = $("rateBtn");
  
  // Debug: Check if elements are found
  if (!player) console.error('Audio player element not found');
  if (!playPause) console.error('Play/pause button not found');
  if (!seek) console.error('Seek slider not found');

  const sticky = $("stickyBar");
  const mPlayPause = $("mPlayPause");
  const mTimeMeta = $("mTimeMeta");
  const mSeek = $("mSeek");
  const mRateBtn = $("mRateBtn");
	  const closeSticky = $("closeSticky");

	  const copyBtn = $("copyLinkBtn");
	  const reprocessBtn = $("reprocessBtn");
	  const reportReprocessModal = $("reportReprocessModal");
	  const reportReprocessText = $("reportReprocessText");
	  const reportReprocessVariantGrid = $("reportReprocessVariantGrid");
	  const reportReprocessLanguageLevel = $("reportReprocessLanguageLevel");
	  const reportReprocessCancel = $("reportReprocessCancel");
	  const reportReprocessStart = $("reportReprocessStart");
	  const reportReprocessStatus = $("reportReprocessStatus");
	  const reportReprocessTokenToggle = $("reportReprocessTokenToggle");
	  const reportReprocessTokenRow = $("reportReprocessTokenRow");
	  const reportReprocessTokenInput = $("reportReprocessTokenInput");
	  const reportReprocessTokenSave = $("reportReprocessTokenSave");
	  const reportReprocessTokenClear = $("reportReprocessTokenClear");
	  const reportReprocessTokenStatus = $("reportReprocessTokenStatus");

	  const REPROCESS_VARIANTS = [
	    { id: 'comprehensive', label: 'Comprehensive', icon: '📝', kind: 'text' },
	    { id: 'bullet-points', label: 'Key Points', icon: '🎯', kind: 'text' },
	    { id: 'key-insights', label: 'Insights', icon: '💡', kind: 'text' },
	    { id: 'audio', label: 'Audio (EN)', icon: '🎙️', kind: 'audio' },
	    { id: 'audio-fr', label: 'Audio français', icon: '🎙️🇫🇷', kind: 'audio', proficiency: true },
	    { id: 'audio-es', label: 'Audio español', icon: '🎙️🇪🇸', kind: 'audio', proficiency: true }
	  ];

	  const PROFICIENCY_LEVELS = [
	    { level: 'beginner', label: 'Beginner', icon: '🟢' },
	    { level: 'intermediate', label: 'Intermediate', icon: '🟡' },
	    { level: 'advanced', label: 'Advanced', icon: '🔵' }
	  ];

	  const normalizeReprocessVariantId = (id) => {
	    const raw = (id ?? '').toString().trim().toLowerCase();
	    if (!raw) return '';
	    const baseOnly = raw.includes(':') ? raw.split(':')[0].trim() : raw;
	    let norm = baseOnly.replace(/\s+/g, '-').replace(/_/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
	    const alias = {
	      'summary': 'comprehensive',
	      'full': 'comprehensive',
	      'keypoints': 'bullet-points',
	      'key-points': 'bullet-points',
	      'keypoints-summary': 'bullet-points',
	      'insights': 'key-insights',
	      'keyinsights': 'key-insights',
	      'audio-en': 'audio'
	    };
	    if (alias[norm]) return alias[norm];
	    if (norm.startsWith('audio-fr-')) return 'audio-fr';
	    if (norm.startsWith('audio-es-')) return 'audio-es';
	    if (norm.startsWith('audio-en-')) return 'audio';
	    return norm;
	  };

	  const REPROCESS_TOKEN_KEY = 'ytv2.reprocessToken';
	  const getReprocessToken = () => {
	    try { return localStorage.getItem(REPROCESS_TOKEN_KEY) || ''; } catch { return ''; }
	  };
	  const setReprocessToken = (token) => {
	    try {
	      if (!token) localStorage.removeItem(REPROCESS_TOKEN_KEY);
	      else localStorage.setItem(REPROCESS_TOKEN_KEY, token);
	    } catch {}
	  };

	  const reprocessState = {
	    open: false,
	    videoId: '',
	    title: '',
	    existing: {},
	    selected: new Set(),
	    audioLevels: { 'audio-fr': 'intermediate', 'audio-es': 'intermediate' }
	  };

	  const resolveExistingOutputs = () => {
	    const existing = {};
	    const add = (id, info = {}) => {
	      const norm = normalizeReprocessVariantId(id);
	      if (!norm) return;
	      existing[norm] = { ...(existing[norm] || {}), ...info, exists: true };
	    };

	    const variantData = Array.isArray(window.SUMMARY_VARIANT_DATA) ? window.SUMMARY_VARIANT_DATA : [];
	    variantData.forEach((v) => {
	      const base = normalizeReprocessVariantId(v?.variant || v?.id || v?.summary_type || v?.type);
	      if (!base) return;
	      let level = '';
	      const raw = (v?.variant || v?.summary_type || '').toString().trim().toLowerCase();
	      if (raw.includes(':')) level = raw.split(':')[1]?.trim() || '';
	      if ((v?.summary_type || '').toString().includes(':')) {
	        const parts = String(v.summary_type).toLowerCase().split(':');
	        if (parts[1]) level = parts[1].trim();
	      }
	      const kind = (v?.kind || (base.startsWith('audio') ? 'audio' : 'text')) || 'text';
	      add(base, { kind, level: level || undefined });
	    });

	    // If an audio file is present on the page, treat audio(EN) as existing.
	    try {
	      const src = resolveAudioSource('');
	      if (src) add('audio', { kind: 'audio' });
	    } catch {}

	    return existing;
	  };

	  const setReprocessStatus = (text) => {
	    if (!reportReprocessStatus) return;
	    reportReprocessStatus.textContent = text || '';
	  };

	  const updateReprocessTokenUi = () => {
	    const token = getReprocessToken();
	    if (reportReprocessTokenStatus) {
	      reportReprocessTokenStatus.textContent = token
	        ? 'Token is saved locally in this browser.'
	        : 'No token saved yet.';
	    }
	    if (reportReprocessTokenInput && document.activeElement !== reportReprocessTokenInput) {
	      reportReprocessTokenInput.value = '';
	    }
	    if (reportReprocessStart) {
	      reportReprocessStart.disabled = reprocessState.selected.size === 0 || !token;
	    }
	  };

	  const renderReprocessLanguageControls = () => {
	    if (!reportReprocessLanguageLevel) return;
	    const selected = reprocessState.selected;
	    const needs = ['audio-fr', 'audio-es'].filter((id) => selected.has(id));
	    if (!needs.length) {
	      reportReprocessLanguageLevel.innerHTML = '';
	      reportReprocessLanguageLevel.classList.add('hidden');
	      return;
	    }
	    const row = (id, label) => {
	      const current = reprocessState.audioLevels[id] || 'intermediate';
	      const chips = PROFICIENCY_LEVELS.map((lvl) => {
	        const active = current === lvl.level;
	        return `<button type="button" data-audio-level="${id}:${lvl.level}"
	          class="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold transition
	          ${active ? 'bg-sky-500/90 text-white' : 'bg-white/5 text-slate-200 hover:bg-white/10 border border-white/10'}">
	          <span>${lvl.icon}</span><span>${lvl.label}</span>
	        </button>`;
	      }).join('');
	      return `<div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
	        <div class="text-sm font-medium text-slate-100">${label}</div>
	        <div class="flex flex-wrap gap-1.5">${chips}</div>
	      </div>`;
	    };
	    reportReprocessLanguageLevel.innerHTML = `
	      <div class="space-y-3">
	        <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">Audio proficiency</div>
	        ${needs.includes('audio-fr') ? row('audio-fr', 'Audio français level') : ''}
	        ${needs.includes('audio-es') ? row('audio-es', 'Audio español level') : ''}
	      </div>
	    `;
	    reportReprocessLanguageLevel.classList.remove('hidden');
	    reportReprocessLanguageLevel.querySelectorAll('[data-audio-level]').forEach((btn) => {
	      btn.addEventListener('click', (event) => {
	        event.preventDefault();
	        const parts = String(btn.dataset.audioLevel || '').split(':');
	        const variantId = parts[0];
	        const level = parts[1];
	        if (!variantId || !level) return;
	        reprocessState.audioLevels[variantId] = level;
	        renderReprocessLanguageControls();
	      });
	    });
	  };

	  const renderReprocessVariantGrid = () => {
	    if (!reportReprocessVariantGrid) return;
	    const existing = reprocessState.existing || {};
	    const selected = reprocessState.selected;
	    const card = (variant) => {
	      const isSelected = selected.has(variant.id);
	      const isDone = Boolean(existing[variant.id]?.exists);
	      const badge = isSelected
	        ? `<span class="ml-auto inline-flex items-center rounded-full bg-sky-500/90 px-2 py-1 text-xs font-semibold text-white">Regenerate</span>`
	        : isDone
	          ? `<span class="ml-auto inline-flex items-center rounded-full bg-emerald-500/20 px-2 py-1 text-xs font-semibold text-emerald-200 border border-emerald-400/20">Done</span>`
	          : '';
	      const sub = isDone && !isSelected ? `<div class="mt-0.5 text-xs text-slate-400">Already generated</div>` : '';
	      return `
	        <button type="button" data-reprocess-variant="${variant.id}"
	          class="group flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition
	          ${isSelected ? 'border-sky-400/50 bg-sky-500/20' : 'border-white/10 bg-white/5 hover:bg-white/10'}">
	          <span class="text-lg">${variant.icon}</span>
	          <span class="min-w-0">
	            <div class="truncate text-sm font-semibold text-slate-100">${variant.label}</div>
	            ${sub}
	          </span>
	          ${badge}
	        </button>
	      `;
	    };
	    reportReprocessVariantGrid.innerHTML = REPROCESS_VARIANTS.map(card).join('');
	    reportReprocessVariantGrid.querySelectorAll('[data-reprocess-variant]').forEach((btn) => {
	      btn.addEventListener('click', (event) => {
	        event.preventDefault();
	        const id = btn.dataset.reprocessVariant;
	        if (!id) return;
	        if (reprocessState.selected.has(id)) reprocessState.selected.delete(id);
	        else reprocessState.selected.add(id);
	        setReprocessStatus('');
	        renderReprocessVariantGrid();
	        renderReprocessLanguageControls();
	        updateReprocessTokenUi();
	      });
	    });
	  };

	  const openReportReprocessModal = () => {
	    if (!reportReprocessModal || !reprocessBtn) return;
	    reprocessState.videoId = reprocessBtn.dataset.videoId || '';
	    reprocessState.title = (document.querySelector('h1')?.textContent || document.title || '').trim();
	    reprocessState.existing = resolveExistingOutputs();
	    reprocessState.selected = new Set();

	    // Seed proficiency from existing (when present)
	    try {
	      if (reprocessState.existing['audio-fr']?.level) reprocessState.audioLevels['audio-fr'] = reprocessState.existing['audio-fr'].level;
	      if (reprocessState.existing['audio-es']?.level) reprocessState.audioLevels['audio-es'] = reprocessState.existing['audio-es'].level;
	    } catch {}

	    if (reportReprocessText) {
	      reportReprocessText.textContent = `Re-run the summarizer for “${reprocessState.title || 'this video'}”?`;
	    }
	    setReprocessStatus('');
	    renderReprocessVariantGrid();
	    renderReprocessLanguageControls();
	    updateReprocessTokenUi();

	    reportReprocessModal.classList.remove('hidden');
	    reportReprocessModal.classList.add('flex');
	    reprocessState.open = true;
	  };

	  const closeReportReprocessModal = () => {
	    if (!reportReprocessModal) return;
	    reportReprocessModal.classList.add('hidden');
	    reportReprocessModal.classList.remove('flex');
	    reprocessState.open = false;
	    setReprocessStatus('');
	    if (reportReprocessTokenRow) reportReprocessTokenRow.classList.add('hidden');
	  };

	  const getSelectedSummaryTypesForReport = () => {
	    const out = [];
	    reprocessState.selected.forEach((id) => {
	      const meta = REPROCESS_VARIANTS.find((v) => v.id === id);
	      if (!meta) return;
	      if (meta.proficiency) {
	        const level = reprocessState.audioLevels[id] || 'intermediate';
	        out.push(`${id}:${level}`);
	      } else {
	        out.push(id);
	      }
	    });
	    return out;
	  };

	  const submitReportReprocess = async () => {
	    const videoId = reprocessState.videoId;
	    if (!videoId) return;
	    const token = getReprocessToken();
	    if (!token) {
	      setReprocessStatus('Admin token required.');
	      updateReprocessTokenUi();
	      if (reportReprocessTokenRow) reportReprocessTokenRow.classList.remove('hidden');
	      return;
	    }
	    const summaryTypes = getSelectedSummaryTypesForReport();
	    if (!summaryTypes.length) {
	      setReprocessStatus('Select at least one output to regenerate.');
	      updateReprocessTokenUi();
	      return;
	    }

	    if (reportReprocessStart) reportReprocessStart.disabled = true;
	    setReprocessStatus('');
	    try {
	      const payload = {
	        video_id: videoId,
	        regenerate_audio: summaryTypes.some((t) => String(t).startsWith('audio')),
	        summary_types: summaryTypes
	      };
	      const resp = await fetch('/api/reprocess', {
	        method: 'POST',
	        headers: {
	          'Content-Type': 'application/json',
	          'X-Reprocess-Token': token
	        },
	        body: JSON.stringify(payload)
	      });
	      if (!resp.ok) {
	        let text = '';
	        try {
	          const ct = resp.headers.get('content-type') || '';
	          if (ct.includes('application/json')) {
	            const j = await resp.json();
	            text = j?.message || j?.error || JSON.stringify(j);
	          } else {
	            text = await resp.text();
	          }
	        } catch {
	          try { text = await resp.text(); } catch {}
	        }
	        throw new Error(text || `HTTP ${resp.status}`);
	      }
	      closeReportReprocessModal();
	      if (reprocessBtn) {
	        const prev = reprocessBtn.textContent;
	        reprocessBtn.textContent = 'Scheduled';
	        window.setTimeout(() => {
	          reprocessBtn.textContent = prev || 'Reprocess';
	        }, 1400);
	      }
	    } catch (err) {
	      setReprocessStatus(`Reprocess failed: ${err?.message || err}`);
	    } finally {
	      if (reportReprocessStart) reportReprocessStart.disabled = reprocessState.selected.size === 0 || !getReprocessToken();
	    }
	  };

  let rates = [1, 1.25, 1.5, 1.75, 2];
  let rIdx = 0;

  // util
  const fmt = (sec) => {
    if (!isFinite(sec)) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  const updateButtons = () => {
    const icon = player.paused ? "▶" : "⏸";
    playPause.textContent = icon;
    mPlayPause.textContent = icon;
    refreshAudioVariantState();
  };

  const updateTime = () => {
    const cur = player.currentTime || 0;
    const dur = player.duration || 0;
    
    // If no duration from audio element, try to parse from template
    let displayDur = dur;
    if (!dur || dur === 0) {
      const templateDurText = document.querySelector('#timeMeta')?.textContent;
      if (templateDurText && templateDurText.includes('/')) {
        const parts = templateDurText.split('/');
        const durPart = parts[1]?.trim();
        if (durPart && durPart !== '—' && durPart !== '0:00') {
          // Parse template duration for display (don't set on audio element)
          const [min, sec] = durPart.split(':').map(n => parseInt(n) || 0);
          displayDur = min * 60 + sec;
        }
      }
    }
    
    timeMeta.textContent = `${fmt(cur)} / ${fmt(displayDur)}`;
    if (mTimeMeta) mTimeMeta.textContent = `${fmt(cur)} / ${fmt(displayDur)}`;
    
    if (displayDur > 0 && !seeking) {
      const progress = Math.round((cur / displayDur) * 100);
      seek.value = progress;
      if (mSeek) mSeek.value = progress;
    }

    // Debug logging
    if (dur === 0 && displayDur > 0) {
      console.log('[V2 Debug] Using template duration:', displayDur, 'audio duration:', dur);
    }

    refreshAudioVariantState();
  };

  // sticky visibility rules:
  //  - show once user scrolls > 240px OR playback has started
  //  - hide on explicit close
  let stickyClosed = false;
  const maybeShowSticky = () => {
    if (stickyClosed) return;
    const scrolled = window.scrollY > 240;
    const playing = !player.paused && !player.ended;
    const shouldShow = (scrolled || playing);
    const wasHidden = sticky.style.display === "none";
    sticky.style.display = shouldShow ? "block" : "none";
    
    if (shouldShow && wasHidden) {
      console.log('[V2 Telemetry] sticky_shown', { scrolled, playing });
    }
  };

  const resolveAudioSource = (fallback = '') => {
    if (player) {
      if (player.currentSrc) return player.currentSrc;
      const sourceEl = player.querySelector('source');
      if (sourceEl && sourceEl.src) return sourceEl.src;
    }
    return fallback;
  };

  const renderReportAudioVariant = (variant) => {
    const audioSrc = resolveAudioSource(variant.audioSrc || '');
    const available = Boolean(audioSrc);
    const playing = available && player && !player.paused && !player.ended;
    const status = !available
      ? 'Audio summary is not available for this report.'
      : playing
        ? 'Now playing via the audio controls above.'
        : 'Ready to play. Use the button below or the main controls to start playback.';
    const actionLabel = !available ? 'Unavailable' : (playing ? 'Pause audio' : 'Play audio');
    const buttonState = available ? '' : 'disabled aria-disabled="true"';
    const downloadMarkup = available
      ? `<a href="${audioSrc}" download
            class="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            data-report-audio-download>
            Download
         </a>`
      : '';

    return `
      <div class="rounded-xl border border-slate-200 bg-slate-50/80 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/60"
           data-report-audio-variant data-audio-available="${available ? '1' : ''}">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div class="space-y-1">
            <p class="font-semibold text-slate-800 dark:text-slate-100">${variant.label || 'Audio summary'}</p>
            <p class="text-slate-600 dark:text-slate-300" data-audio-status>${status}</p>
            <p class="text-xs text-slate-500 dark:text-slate-400">Use the primary player controls above to scrub or change speed.</p>
          </div>
          <div class="flex items-center gap-2 self-start md:self-auto">
            ${downloadMarkup}
            <button type="button" ${buttonState}
                    class="inline-flex items-center gap-2 rounded-full border border-white/40 bg-gradient-to-r from-audio-500 to-indigo-500 px-4 py-1.5 text-sm font-semibold text-white shadow-md disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-200 disabled:text-slate-500 dark:disabled:border-slate-700 dark:disabled:bg-slate-800 dark:disabled:text-slate-400"
                    data-report-audio-btn>
              ${actionLabel}
            </button>
          </div>
        </div>
      </div>
    `;
  };

  const attachReportAudioHandlers = (container, variant) => {
    const block = container.querySelector('[data-report-audio-variant]');
    if (!block) return;
    const playBtn = block.querySelector('[data-report-audio-btn]');
    if (playBtn) {
      playBtn.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!player) return;
        if (player.paused) {
          player.play().catch((err) => console.error('Audio play failed', err));
        } else {
          player.pause();
        }
      });
    }

    const downloadLink = block.querySelector('[data-report-audio-download]');
    if (downloadLink) {
      downloadLink.addEventListener('click', (event) => event.stopPropagation());
    }
  };

  const refreshAudioVariantState = () => {
    document.querySelectorAll('[data-report-audio-variant]').forEach((block) => {
      const available = block.getAttribute('data-audio-available') === '1';
      const statusEl = block.querySelector('[data-audio-status]');
      const btn = block.querySelector('[data-report-audio-btn]');
      const audioSrc = resolveAudioSource();

      if (!available || !audioSrc) {
        if (statusEl) statusEl.textContent = 'Audio summary is not available for this report.';
        if (btn) {
          btn.textContent = 'Unavailable';
          btn.disabled = true;
        }
        return;
      }

      const playing = player && !player.paused && !player.ended;
      if (statusEl) {
        statusEl.textContent = playing
          ? 'Now playing via the audio controls above.'
          : 'Ready to play. Use the button below or the main controls to start playback.';
      }
      if (btn) {
        btn.disabled = false;
        btn.textContent = playing ? 'Pause audio' : 'Play audio';
      }
      const downloadLink = block.querySelector('[data-report-audio-download]');
      if (downloadLink) downloadLink.href = audioSrc;
    });
  };

  // events
  if (playPause && player) {
    playPause.addEventListener("click", () => {
      console.log('[V2 Telemetry] play_clicked', { was_paused: player.paused });
      if (player.paused) player.play(); else player.pause();
    });
  }
  mPlayPause.addEventListener("click", () => {
    if (player.paused) player.play(); else player.pause();
  });

  // sticky player controls
  mRateBtn?.addEventListener("click", () => {
    rIdx = (rIdx + 1) % rates.length;
    player.playbackRate = rates[rIdx];
    rateBtn.textContent = `${rates[rIdx]}×`;
    mRateBtn.textContent = `${rates[rIdx]}×`;
  });

  mSeek?.addEventListener("mousedown", () => { seeking = true; });
  mSeek?.addEventListener("mouseup", () => { seeking = false; });
  mSeek?.addEventListener("touchstart", () => { seeking = true; });
  mSeek?.addEventListener("touchend", () => { seeking = false; });
  
  mSeek?.addEventListener("input", () => {
    if (seeking) {
      const dur = player.duration || 0;
      player.currentTime = (mSeek.value / 100) * dur;
    }
  });

  rateBtn?.addEventListener("click", () => {
    rIdx = (rIdx + 1) % rates.length;
    player.playbackRate = rates[rIdx];
    rateBtn.textContent = `${rates[rIdx]}×`;
  });

  let seeking = false;
  
  seek.addEventListener("mousedown", () => { seeking = true; });
  seek.addEventListener("mouseup", () => { seeking = false; });
  seek.addEventListener("touchstart", () => { seeking = true; });
  seek.addEventListener("touchend", () => { seeking = false; });
  
  seek.addEventListener("input", () => {
    if (seeking) {
      const dur = player.duration || 0;
      player.currentTime = (seek.value / 100) * dur;
    }
  });

  player.addEventListener("timeupdate", updateTime);
  player.addEventListener("loadedmetadata", updateTime);
  player.addEventListener("play", () => { updateButtons(); maybeShowSticky(); });
  player.addEventListener("pause", () => { updateButtons(); maybeShowSticky(); });
  player.addEventListener("ended", () => { updateButtons(); maybeShowSticky(); });

  window.addEventListener("scroll", maybeShowSticky);

  closeSticky.addEventListener("click", () => {
    stickyClosed = true;
    sticky.style.display = "none";
  });

	  // copy link
	  copyBtn?.addEventListener("click", async () => {
	    try {
	      await navigator.clipboard.writeText(window.location.href);
	      copyBtn.textContent = "Copied!";
	      setTimeout(() => (copyBtn.textContent = "Copy link"), 1200);
	    } catch {}
	  });

	  // Reprocess (in-place on report page)
	  reprocessBtn?.addEventListener("click", (event) => {
	    event.preventDefault();
	    event.stopPropagation();
	    openReportReprocessModal();
	  });

	  if (reportReprocessCancel) {
	    reportReprocessCancel.addEventListener('click', (event) => {
	      event.preventDefault();
	      closeReportReprocessModal();
	    });
	  }
	  if (reportReprocessStart) {
	    reportReprocessStart.addEventListener('click', (event) => {
	      event.preventDefault();
	      submitReportReprocess();
	    });
	  }
	  if (reportReprocessModal) {
	    reportReprocessModal.querySelectorAll('[data-report-reprocess-close]').forEach((el) => {
	      el.addEventListener('click', (event) => {
	        event.preventDefault();
	        closeReportReprocessModal();
	      });
	    });
	    document.addEventListener('keydown', (event) => {
	      if (!reprocessState.open) return;
	      if (event.key === 'Escape') closeReportReprocessModal();
	    });
	  }

	  if (reportReprocessTokenToggle && reportReprocessTokenRow) {
	    reportReprocessTokenToggle.addEventListener('click', (event) => {
	      event.preventDefault();
	      reportReprocessTokenRow.classList.toggle('hidden');
	      updateReprocessTokenUi();
	      if (!reportReprocessTokenRow.classList.contains('hidden') && reportReprocessTokenInput) {
	        reportReprocessTokenInput.focus();
	      }
	    });
	  }
	  if (reportReprocessTokenSave) {
	    reportReprocessTokenSave.addEventListener('click', (event) => {
	      event.preventDefault();
	      const token = (reportReprocessTokenInput?.value || '').trim();
	      if (!token) return;
	      setReprocessToken(token);
	      updateReprocessTokenUi();
	      if (reportReprocessTokenRow) reportReprocessTokenRow.classList.add('hidden');
	    });
	  }
	  if (reportReprocessTokenClear) {
	    reportReprocessTokenClear.addEventListener('click', (event) => {
	      event.preventDefault();
	      setReprocessToken('');
	      updateReprocessTokenUi();
	    });
	  }

  document.querySelectorAll('[data-deep-research-open]').forEach((btn) => {
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      openReportDeepResearchModal();
    });
  });
  window.addEventListener('ytv2:report-variant-changed', updateReportDeepResearchLaunchers);

  // Theme toggle functionality
  const themeToggle = $("themeToggle");
  const themeIcon = $("themeIcon");
  const themeText = $("themeText");
  
  const themes = {
    light: { 
      name: 'Light',
      icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>` 
    },
    dark: { 
      name: 'Dark',
      icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>` 
    },
    system: { 
      name: 'System',
      icon: `<rect x="3" y="4" width="18" height="14" rx="2"/><path d="M9 17v3h6v-3"/>` 
    }
  };
  
  let currentTheme = localStorage.getItem('ytv2.theme') || 'system';
  
  const applyTheme = (theme) => {
    const html = document.documentElement;
    
    if (theme === 'system') {
      const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (systemPrefersDark) {
        html.classList.add('dark');
      } else {
        html.classList.remove('dark');
      }
    } else if (theme === 'dark') {
      html.classList.add('dark');
    } else {
      html.classList.remove('dark');
    }
    
    // Update button appearance
    if (themeIcon && themeText) {
      themeIcon.innerHTML = themes[theme].icon;
      themeText.textContent = themes[theme].name;
    }
  };
  
  const nextTheme = (current) => {
    const order = ['system', 'light', 'dark'];
    const currentIndex = order.indexOf(current);
    return order[(currentIndex + 1) % order.length];
  };
  
  themeToggle?.addEventListener('click', () => {
    const newTheme = nextTheme(currentTheme);
    currentTheme = newTheme;
    localStorage.setItem('ytv2.theme', newTheme);
    applyTheme(newTheme);
  });
  
  // System theme change listener
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (currentTheme === 'system') {
      applyTheme('system');
    }
  });
  
  // Hide audio player if no audio file (but never hide metadata/thumbnail)
  const audioSource = player?.querySelector('source');
  const hasAudioSrc = audioSource && audioSource.src && audioSource.src.trim() !== '';
  
  console.log('[V2 Debug] Audio element check:', {
    hasPlayer: !!player,
    hasSource: !!audioSource,
    srcValue: audioSource?.src,
    hasValidSrc: hasAudioSrc
  });
  
  if (player && !hasAudioSrc) {
    // No audio source - find and hide only the specific audio player section
    const audioPlayerSection = player.closest('section');
    if (audioPlayerSection) {
      audioPlayerSection.style.display = 'none';
      console.log('[V2 Debug] No valid audio source found, hiding only audio player section');
    }
    // Also hide sticky player
    if (sticky) {
      sticky.style.display = 'none';
    }
  } else if (hasAudioSrc) {
    console.log('[V2 Debug] Valid audio source found:', audioSource.src);
  }
  
  // init
  applyTheme(currentTheme);
  updateButtons();
  updateTime();
  maybeShowSticky();
  initReportMetaTabs();
  initSummaryVariants();
  updateReportDeepResearchLaunchers();
})();
