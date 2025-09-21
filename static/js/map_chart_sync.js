// map_chart_sync.js
// Ensures Leaflet map invalidates size when visible/resized and sets Chart.js canvases
// to match the map pixel height for a pixel-perfect side-by-side layout.
(function(window, document) {
    'use strict';

    // Simple debounce utility
    function debounce(fn, wait) {
        let t;
        return function() {
            const args = arguments;
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), wait);
        };
    }

    // Get map element height in pixels (returns null if not present)
    function getMapHeight() {
        const mapEl = document.getElementById('flood-map');
        if (!mapEl) return null;
        return mapEl.getBoundingClientRect().height;
    }

    // Resize Chart.js charts to match given height
    function setChartsHeightTo(heightPx) {
        if (!heightPx) return;
        const canvases = document.querySelectorAll('.chart-canvas');
        canvases.forEach(canvas => {
            // Set canvas style height so Chart.js will respect it on resize
            canvas.style.height = heightPx + 'px';
            // If Chart instance exists, call resize
            try {
                const chart = Chart.getChart(canvas.id);
                if (chart) {
                    // Update internal sizes and redraw
                    chart.resize();
                } else if (canvas && canvas.parentElement) {
                    // If Chart not found, set the canvas height attribute and let CSS do layout
                    canvas.setAttribute('height', Math.round(heightPx));
                }
            } catch (e) {
                // Chart may not be loaded on pages without charts
                console.debug('[map_chart_sync] Chart resize skipped:', e.message || e);
            }
        });
    }

    // Invalidate Leaflet map size and sync charts
    function syncMapAndCharts() {
        // Invalidate map size if floodMap exists
        const map = window.floodMap;
        if (map && typeof map.invalidateSize === 'function') {
            try {
                // A small timeout helps when the container has just become visible
                setTimeout(() => {
                    map.invalidateSize({animate: false});
                }, 50);
            } catch (e) {
                console.warn('[map_chart_sync] invalidateSize error', e);
            }
        }

        const h = getMapHeight();
        if (h) setChartsHeightTo(h);
    }

    // Debounced version to avoid thrashing on rapid resizes
    const debouncedSync = debounce(syncMapAndCharts, 120);

    // Hooks: window resize and Bootstrap tab shown (charts are inside tabs)
    window.addEventListener('resize', debouncedSync);

    // Listen for Bootstrap tab shown events to sync when chart tab becomes visible
    document.addEventListener('shown.bs.tab', function(e) {
        // Delay slightly to ensure tab content is painted
        setTimeout(syncMapAndCharts, 80);
    });

    // Also run once DOM is ready (after other scripts initialize map and charts)
    document.addEventListener('DOMContentLoaded', function() {
        // Run after a short delay so map.js and charts.js have a chance to initialize
        setTimeout(syncMapAndCharts, 200);
    });

    // Expose a manual sync function so other code can call it after dynamic layout changes
    window.syncMapAndCharts = syncMapAndCharts;

})(window, document);
