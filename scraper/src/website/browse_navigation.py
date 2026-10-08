"""In-page wayfinding shared by the Grid and List views."""

NAV_HTML = """
            <nav id="browse-navigation" class="browse-jump-nav" aria-label="Jump to a section" tabindex="-1">
                <span class="browse-jump-label">Jump to</span>
                <ol>
                    <li><a href="#statewide-measures" data-browse-jump="statewide-measures">Statewide measures</a></li>
                    <li><a href="#local-measures" data-browse-jump="local-measures">Local measures</a></li>
                    <li><a href="#full-catalog" data-browse-jump="full-catalog" id="catalogJumpLink">Full grid</a></li>
                </ol>
            </nav>
"""

CATALOG_HTML = """
            <div class="browse-catalog-header" id="catalogHeader">
                <div>
                    <h2 id="full-catalog" class="browse-anchor" tabindex="-1">Full grid</h2>
                    <p>Search and filter the full collection of statewide and local measures, including historical elections.</p>
                </div>
                <a class="browse-return" href="#browse-navigation" data-browse-jump="browse-navigation">Back to jump links <span aria-hidden="true">↑</span></a>
            </div>
"""

STYLE = """
        :root { --browse-header-offset: 100px; }
        html { scroll-padding-top: var(--browse-header-offset); }
        .header .view-controls { flex-wrap: wrap; max-width: 100%; }
        .pagination-container .pagination-controls { flex-wrap: wrap; justify-content: center; max-width: 100%; }
        .browse-anchor, #browse-navigation, #main-content, #resultsContainer { scroll-margin-top: 16px; }
        .browse-skip-link {
            position: fixed; top: 8px; left: 8px; z-index: 10001;
            padding: 12px 18px; background: #fff; color: #172f40;
            transform: translateY(-200%); border: 2px solid #172f40;
        }
        .browse-skip-link:focus { transform: none; }
        .browse-jump-nav {
            display: flex; align-items: center; flex-wrap: wrap; gap: 4px 24px;
            padding: 12px 18px; margin-bottom: 24px;
            border: 1px solid var(--border); border-radius: 8px;
            background: var(--bg-primary);
        }
        .browse-jump-label { font-size: .8rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--text-secondary); }
        .browse-jump-nav ol { display: flex; flex-wrap: wrap; gap: 0 24px; list-style: none; margin: 0; padding: 0; }
        .browse-jump-nav a, .browse-return {
            display: inline-flex; align-items: center; gap: 6px; min-height: 44px;
            color: #244c63; text-decoration: underline; text-underline-offset: 4px;
            font-size: .9rem; font-weight: 600;
        }
        .browse-jump-nav a:hover, .browse-return:hover { color: #122b3a; text-decoration-thickness: 2px; }
        .browse-jump-nav a:focus-visible, .browse-return:focus-visible,
        .browse-anchor:focus-visible, #browse-navigation:focus-visible,
        .measure-list-item:focus-visible {
            outline: 3px solid #244c63; outline-offset: 4px; border-radius: 3px;
        }
        .browse-catalog-header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 16px; margin: 12px 0 20px; }
        .browse-catalog-header h2 { margin: 0 0 6px; font-size: 1.5rem; }
        .browse-catalog-header p { margin: 0; color: var(--text-secondary); max-width: 680px; font-size: .9rem; }
        .browse-return { flex-shrink: 0; }
        .results-list .measure-list-item { grid-template-columns: auto minmax(0, 1fr) auto; overflow-wrap: anywhere; }
        .results-list .measure-list-item > div { min-width: 0; }
        .hero-section .upcoming-statewide-heading h2,
        .upcoming-local-band .upcoming-local-band-header h2 { margin: .15rem 0 0; font-size: 1.35rem; }
        .upcoming-local-band .browse-section-title { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 16px; }
        .hero-section .hero-header { text-align: left; margin-bottom: 1.5rem; }
        .hero-section .hero-title { font-size: 1rem; font-weight: 500; color: var(--text-secondary); }
        .hero-section .hero-description { margin: 0; max-width: none; font-size: .85rem; }
        @media (max-width: 580px) {
            .browse-jump-nav { padding: 8px 14px; gap: 0 16px; margin-bottom: 16px; }
            .browse-jump-nav ol { width: 100%; gap: 0 20px; }
            .browse-catalog-header { flex-direction: column; gap: 4px; }
            .results-list .measure-list-item { grid-template-columns: auto minmax(0, 1fr); gap: 6px 12px; }
            .results-list .measure-list-item > div:last-child { grid-column: 2; text-align: left !important; }
        }
"""

SCRIPT = """
        const browseTargetIds = ['statewide-measures', 'local-measures', 'full-catalog', 'browse-navigation'];
        let measureReturnURL = null;

        function scrollToBrowseTarget(id, focusTarget = false) {
            if (!browseTargetIds.includes(id)) return;
            const target = document.getElementById(id);
            if (!target || !target.getClientRects().length) return;
            if (focusTarget) target.focus({preventScroll: true});
            // Instant scrolling avoids unnecessary motion and works with reduced-motion preferences.
            target.scrollIntoView({behavior: 'instant', block: 'start'});
        }

        function syncBrowseNavigation() {
            const label = currentView === 'list' ? 'Full list' : 'Full grid';
            document.getElementById('full-catalog').textContent = label;
            document.getElementById('catalogJumpLink').textContent = label;
            document.querySelectorAll('[data-browse-jump]').forEach(link => {
                const url = new URL(window.location.href);
                url.hash = link.dataset.browseJump;
                link.href = url.pathname + url.search + url.hash;
            });
            document.querySelectorAll('#gridView, #listView, #insightsView, #exploreView, .view-card').forEach(button => {
                const active = button.id === currentView + 'View' || button.id === currentView + 'ViewCard';
                button.classList.toggle('active', active);
                button.setAttribute('aria-pressed', String(active));
            });
        }

        function initializeBrowseNavigation() {
            const header = document.querySelector('.header');
            const updateOffset = () => document.documentElement.style.setProperty(
                '--browse-header-offset', Math.ceil(header.getBoundingClientRect().height) + 'px');
            updateOffset();
            new ResizeObserver(updateOffset).observe(header);
            document.querySelectorAll('[data-browse-jump]').forEach(link => {
                link.addEventListener('click', event => {
                    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                    event.preventDefault();
                    const url = new URL(link.href);
                    if (url.href !== window.location.href) history.pushState(null, '', url);
                    scrollToBrowseTarget(link.dataset.browseJump, event.detail === 0);
                });
            });
            syncBrowseNavigation();
        }
"""
