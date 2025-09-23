// modern_dashboard.js
// Powers the modern dashboard UI with live, database-driven data using existing API endpoints

(function() {
  const state = {
    municipalityId: null,
    barangayId: null,
    map: null,
    mapLayers: {
      zones: null,
      sensors: null,
      barangays: null,
    },
    chart: null,
    normalize: false, // when true, normalize all lines to 0–100 for alignment
    _rawSeries: null, // keep last fetched raw series to re-apply normalization without refetch
    _trendsFetchInFlight: false, // guard against overlapping fetches
    _alertsReqToken: 0, // monotonic token to ensure latest alert response wins
    trendsRange: 'latest',
  };
  const barangayLayerById = new Map();

  document.addEventListener('DOMContentLoaded', () => {
    setupLocationSelector();
    initChart();
    initMap();
    bindApplyThresholdsButton();
    setupTrendsRangeControls();
    // Ensure any previous chart overlay from older versions is removed
    try { clearChartOverlay(); } catch (e) {}

    // Bind align-lines toggle if present
    const alignToggle = document.getElementById('align-lines-toggle');
    if (alignToggle) {
      state.normalize = !!alignToggle.checked;
      alignToggle.addEventListener('change', () => {
        state.normalize = !!alignToggle.checked;
        // Re-apply scaling using the cached raw series
        if (state.chart && state._rawSeries && Array.isArray(state.chart.data.labels)) {
          applyChartScaling(state._rawSeries);
          try {
        state.chart.update();
      } catch (e) {
        recreateChart([], { t:[], h:[], r:[], wl:[], ws:[] });
      }
        } else {
          // Fallback: reload
          loadTrendsChart();
        }
      });
    }

    // Initial loads
    refreshAll();

    // Periodic refreshes (guard to prevent double interval setup on hot-reloads)
    if (!state._intervalsSet) {
      setInterval(updateSensorValues, 60 * 1000);
      setInterval(updateAlerts, 30 * 1000);
      setInterval(updateMapData, 3 * 60 * 1000);
      // Auto-refresh trends chart every 10s
      setInterval(loadTrendsChart, 10 * 1000);
      state._intervalsSet = true;
    }
    // When the tab becomes visible again, refresh immediately
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        loadTrendsChart();
      }
    });

    // Responsive: on window resize, resize chart and re-apply scaling
    window.addEventListener('resize', () => {
      if (state.chart) {
        if (state._rawSeries) applyChartScaling(state._rawSeries);
        try { state.chart.resize(); } catch(e) {}
      }
    });
    // Responsive: observe container resize
    const chartContainer = document.querySelector('.chart-container-modern');
    if (window.ResizeObserver && chartContainer) {
      try {
        const ro = new ResizeObserver(() => {
          if (state.chart) {
            if (state._rawSeries) applyChartScaling(state._rawSeries);
            try { state.chart.resize(); } catch(e) {}
          }
        });
        ro.observe(chartContainer);
        state._chartResizeObserver = ro;
      } catch (e) { /* ignore */ }
    }
  });

  // ===== Helpers defined at IIFE scope (not inside DOMContentLoaded/handlers) =====

  async function fetchHeatmapPoints() {
    try {
      const params = [];
      if (state.municipalityId) params.push(`municipality_id=${state.municipalityId}`);
      if (state.barangayId) params.push(`barangay_id=${state.barangayId}`);
      const url = `/api/heatmap/${params.length ? ('?' + params.join('&')) : ''}`;
      const res = await fetch(url, { headers: { 'Accept': 'application/json' }});
      if (!res.ok) return null;
      return await res.json();
    } catch (e) { return null; }
  }

  function bindHeatmapToggleUI() {
    const cb = document.getElementById('heatmap-toggle');
    if (!cb) return;
    // initialize checkbox state
    cb.checked = !!state.heatEnabled;
    cb.addEventListener('change', () => {
      const enable = !!cb.checked;
      const proceed = () => {
        state.heatEnabled = enable;
        updateHeatLayer(state._heatPoints || []);
      };
      if (enable && (!window.L || !L.heatLayer)) {
        const scriptId = 'leaflet-heat-plugin';
        if (!document.getElementById(scriptId)) {
          const s = document.createElement('script');
          s.id = scriptId; s.src = 'https://unpkg.com/leaflet.heat/dist/leaflet-heat.js';
          s.onload = proceed; s.onerror = proceed;
          document.head.appendChild(s);
        } else {
          setTimeout(proceed, 200);
        }
      } else {
        proceed();
      }
    });
  }

  // Convert API data to heatmap points [lat, lng, intensity]
  function buildHeatPoints(data) {
    const pts = [];
    const barangays = Array.isArray(data.barangays) ? data.barangays : [];
    barangays.forEach(b => {
      if (!b.lat || !b.lng) return;
      // Severity-based intensity: 0–5 -> 0.0–1.0
      const sev = (typeof b.severity === 'number') ? b.severity
        : (String(b.risk_level||'').toLowerCase()==='high'?5:String(b.risk_level||'').toLowerCase()==='medium'?3:String(b.risk_level||'').toLowerCase()==='low'?1:0);
      const popFactor = Math.min(1.5, Math.sqrt(Number(b.population||1)) / 1000); // light population weighting
      const intensity = Math.max(0, Math.min(1, (sev/5) * (0.7 + 0.3*popFactor)));
      if (intensity > 0) pts.push([b.lat, b.lng, intensity]);
    });
    // Optionally include sensors as additional heat hints when they have high readings
    const sensors = Array.isArray(data.sensors) ? data.sensors : [];
    sensors.forEach(s => {
      if (!s.lat || !s.lng) return;
      const v = (s.latest_reading && typeof s.latest_reading.value === 'number') ? s.latest_reading.value : null;
      if (v == null) return;
      // Normalize sensor risk proxy (heuristic): higher values -> more heat
      const intensity = Math.max(0, Math.min(1, v / 100));
      if (intensity > 0.2) pts.push([s.lat, s.lng, intensity * 0.6]);
    });
    return pts;
  }

  // Add a simple heatmap toggle control
  function addHeatToggleControl(map) {
    if (!window.L) return;
    if (!document.getElementById('flood-heat-style')) {
      const st = document.createElement('style');
      st.id = 'flood-heat-style';
      st.textContent = `.leaflet-control-heat a{background:#fff;border:1px solid #dcdcdc;border-radius:4px;display:inline-block;width:28px;height:28px;line-height:28px;text-align:center;font-size:16px;color:#333;box-shadow:0 1px 3px rgba(0,0,0,.2);} .leaflet-control-heat a.active{background:#e0f2fe;border-color:#7dd3fc;color:#0369a1}`;
      document.head.appendChild(st);
    }
    const HeatCtrl = L.Control.extend({
      options: { position: 'topleft' },
      onAdd: function() {
        const c = L.DomUtil.create('div', 'leaflet-control leaflet-bar leaflet-control-heat');
        const a = L.DomUtil.create('a', '', c);
        a.href = '#'; a.title = 'Toggle heatmap'; a.innerHTML = '🔥';
        // Make absolutely sure it's visible
        c.style.zIndex = '1000';
        c.style.display = 'block';
        c.style.marginTop = '4px';
        if (state.heatEnabled) a.classList.add('active');
        L.DomEvent.on(a, 'click', L.DomEvent.stop)
          .on(a, 'click', () => {
            // Lazy load plugin if not present
            const proceed = () => {
              state.heatEnabled = !state.heatEnabled;
              if (state.heatEnabled) a.classList.add('active'); else a.classList.remove('active');
              updateHeatLayer(state._heatPoints || []);
              // sync sidebar checkbox
              const cb = document.getElementById('heatmap-toggle');
              if (cb) cb.checked = !!state.heatEnabled;
            };
            if (!window.L || !L.heatLayer) {
              const scriptId = 'leaflet-heat-plugin';
              if (!document.getElementById(scriptId)) {
                const s = document.createElement('script');
                s.id = scriptId; s.src = 'https://unpkg.com/leaflet.heat/dist/leaflet-heat.js';
                s.onload = proceed; s.onerror = proceed;
                document.head.appendChild(s);
              } else {
                // If already requested, wait a beat and proceed
                setTimeout(proceed, 200);
              }
            } else {
              proceed();
            }
          });
        return c;
      }
    });
    map.addControl(new HeatCtrl());
  }

  // Create or update the heat layer
  function updateHeatLayer(points) {
    if (!window.L || !L.heatLayer) return; // plugin not loaded
    if (!state.map) return;
    if (!state.heatEnabled) {
      if (state.mapLayers.heat) { state.map.removeLayer(state.mapLayers.heat); state.mapLayers.heat = null; }
      return;
    }
    const options = {
      radius: 20,
      blur: 15,
      maxZoom: 18,
      gradient: { 0.0: '#10b981', 0.4: '#84cc16', 0.6: '#f59e0b', 0.8: '#ef4444', 1.0: '#991b1b' }
    };
    if (state.mapLayers.heat) {
      state.mapLayers.heat.setLatLngs(points || []);
    } else {
      state.mapLayers.heat = L.heatLayer(points || [], options).addTo(state.map);
    }
  }
  

  // ---------------- Current Location card updater ----------------
  function updateCurrentLocationCard() {
    try {
      const muniEl = document.getElementById('current-muni');
      const brgyEl = document.getElementById('current-brgy');
      const noteEl = document.getElementById('current-location-note');
      const muniSel = document.getElementById('location-select');
      const brgySel = document.getElementById('barangay-select');
      if (!muniEl || !brgyEl) return; // card not present
      const muniName = (muniSel && muniSel.selectedIndex > -1) ? muniSel.options[muniSel.selectedIndex].text : 'All Municipalities';
      const brgyName = (brgySel && brgySel.selectedIndex > 0) ? brgySel.options[brgySel.selectedIndex].text : 'All Barangays';
      muniEl.textContent = muniName || 'All Municipalities';
      brgyEl.textContent = brgyName || 'All Barangays';
      if (noteEl) {
        if (state.barangayId || state.municipalityId) {
          noteEl.textContent = 'Monitoring environmental conditions for the selected location.';
        } else {
          noteEl.textContent = 'Monitoring environmental conditions continuously.';
        }
      }
    } catch (e) { /* ignore */ }
  }

  function refreshAll() {
    updateSensorValues();
    updateAlerts();
    updateMapData();
    loadTrendsChart();
  }

  // Bind Latest / 1W / 1M / 1Y controls and update state.trendsRange
  function setupTrendsRangeControls() {
    const group = document.getElementById('trends-range');
    if (!group) return;
    const buttons = Array.from(group.querySelectorAll('button[data-range]'));
    const setActive = (val) => {
      buttons.forEach(b => b.classList.toggle('active', b.getAttribute('data-range') === val));
    };
    // Initialize selection
    const initial = (state.trendsRange || 'latest');
    setActive(initial);
    // Click bindings
    buttons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const r = btn.getAttribute('data-range') || 'latest';
        state.trendsRange = r;
        setActive(r);
        // Update the small description under the header
        const desc = document.getElementById('trends-desc');
        if (desc) {
          if (r === 'latest') desc.textContent = 'Showing latest 10 readings per parameter';
          else if (r === '1w') desc.textContent = 'Showing readings from the last 1 week';
          else if (r === '1m') desc.textContent = 'Showing readings from the last 1 month';
          else if (r === '1y') desc.textContent = 'Showing readings from the last 1 year';
        }
        loadTrendsChart();
      });
    });
  }

  // ---------------- Apply Thresholds (Server-side evaluation) ----------------
  function bindApplyThresholdsButton() {
    const btn = document.getElementById('apply-thresholds-btn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      try {
        btn.disabled = true;
        btn.textContent = 'Applying...';
        await applyThresholdsNow();
      } catch (e) {
        console.error('Error applying thresholds:', e);
        alert('Unable to apply thresholds. Please make sure you are logged in and try again.');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Apply Thresholds';
      }
    });
  }

  async function applyThresholdsNow() {
    try {
      const body = buildApplyThresholdsBody();
      const res = await fetch('/api/apply-thresholds/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify(body),
        credentials: 'same-origin',
      });
      if (!res.ok) {
        // Silently ignore 401/403 (not logged in) for automatic attempts
        if (res.status === 401 || res.status === 403) return;
        const txt = await res.text().catch(() => '');
        throw new Error(`Failed to apply thresholds (${res.status}): ${txt || res.statusText}`);
      }
      // On success, refresh alerts UI
      updateAlerts();
    } catch (e) {
      // Quietly log for automatic path
      console.warn('[Apply Thresholds] Auto-apply failed:', e.message || e);
    }
  }

  function buildApplyThresholdsBody() {
    const body = { dry_run: false };
    if (state.barangayId) {
      body.process_scope = 'barangay';
      body.barangay_id = state.barangayId;
    } else if (state.municipalityId) {
      body.process_scope = 'municipality';
      body.municipality_id = state.municipalityId;
    } else {
      body.process_scope = 'all';
    }
    return body;
  }

  function getCSRFToken() {
    // Standard Django CSRF cookie name is 'csrftoken'
    const name = 'csrftoken=';
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < cookies.length; i++) {
      const c = cookies[i].trim();
      if (c.startsWith(name)) return decodeURIComponent(c.substring(name.length));
    }
    return '';
  }

  // ---------------- Location selector ----------------
  function setupLocationSelector() {
    const muniSel = document.getElementById('location-select');
    const brgySel = document.getElementById('barangay-select');
    if (!muniSel) return;

    // Populate municipalities
    fetch('/api/municipalities/?limit=200')
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(data => {
        const results = data.results || [];
        // Clear existing non-default options
        muniSel.querySelectorAll('option:not([selected])').forEach(o => o.remove());
        results.sort((a,b)=>a.name.localeCompare(b.name)).forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = m.name;
          muniSel.appendChild(opt);
        });
        // Restore persisted selection
        const savedMuni = sessionStorage.getItem('dashboard_municipality_id');
        const savedBrgy = sessionStorage.getItem('dashboard_barangay_id');
        if (savedMuni) {
          muniSel.value = savedMuni;
          state.municipalityId = savedMuni;
          populateBarangays(savedMuni).then(() => {
            if (savedBrgy && brgySel) {
              brgySel.value = savedBrgy;
              state.barangayId = savedBrgy;
              brgySel.disabled = false;
              updateCurrentLocationCard();
              refreshAll();
              applyThresholdsNow();
            } else {
              updateCurrentLocationCard();
              refreshAll();
              applyThresholdsNow();
            }
          });
        } else {
          // No saved selection; still reflect defaults in the card
          updateCurrentLocationCard();
        }
      })
      .catch(() => {});

    // On municipality change, load barangays
    muniSel.addEventListener('change', () => {
      const val = muniSel.value;
      state.municipalityId = val || null;
      sessionStorage.setItem('dashboard_municipality_id', state.municipalityId || '');
      state.barangayId = null;
      if (brgySel) {
        brgySel.innerHTML = '<option value="" selected>All Barangays</option>';
        brgySel.disabled = !state.municipalityId;
      }
      updateCurrentLocationCard();
      // Reset Alert Status UI and invalidate any in-flight alert requests
      const badge = document.getElementById('alert-status-badge');
      const title = document.getElementById('alert-title');
      const msg = document.getElementById('alert-message');
      if (badge) { badge.textContent = 'Normal'; badge.classList.remove('status-warning','status-danger'); badge.classList.add('status-normal'); }
      if (title) title.textContent = 'Loading status…';
      if (msg) msg.textContent = 'Fetching latest advisory for the selected location.';
      const list = document.getElementById('param-status-list');
      if (list) list.innerHTML = '';
      state._alertsReqToken++;
      if (state.municipalityId) {
        populateBarangays(state.municipalityId).then(() => refreshAll());
        // Automatically apply thresholds for the new scope (municipality-wide for all barangays)
        applyThresholdsNow();
      } else {
        refreshAll();
      }
    });

    // On barangay change, just set barangayId and refresh
    if (brgySel) {
      brgySel.addEventListener('change', () => {
        state.barangayId = brgySel.value || null;
        sessionStorage.setItem('dashboard_barangay_id', state.barangayId || '');
        updateCurrentLocationCard();
        // Reset Alert Status UI immediately to avoid stale badge while loading
        const badge = document.getElementById('alert-status-badge');
        const title = document.getElementById('alert-title');
        const msg = document.getElementById('alert-message');
        if (badge) { badge.textContent = 'Normal'; badge.classList.remove('status-warning','status-danger'); badge.classList.add('status-normal'); }
        if (title) title.textContent = 'Loading status…';
        if (msg) msg.textContent = 'Fetching latest advisory for the selected barangay.';
        const list = document.getElementById('param-status-list');
        if (list) list.innerHTML = '';
        // Bump token to invalidate in-flight requests for previous selection
        state._alertsReqToken++;
        refreshAll();
        // Automatically apply thresholds for selected barangay
        applyThresholdsNow();
      });
    }
  }

  function populateBarangays(municipalityId) {
    const brgySel = document.getElementById('barangay-select');
    if (!brgySel || !municipalityId) return Promise.resolve();
    brgySel.disabled = true;
    return fetch(`/api/all-barangays/?municipality_id=${encodeURIComponent(municipalityId)}`)
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(d => {
        const items = d.barangays || [];
        brgySel.innerHTML = '<option value="" selected>All Barangays</option>';
        items.sort((a,b)=>a.name.localeCompare(b.name)).forEach(b => {
          const opt = document.createElement('option');
          opt.value = b.id;
          opt.textContent = b.name;
          brgySel.appendChild(opt);
        });
        brgySel.disabled = false;
      })
      .catch(() => { brgySel.disabled = false; });
  }

  // ---------------- Sensors (Weather Conditions) ----------------
  function updateSensorValues() {
    let url = '/api/sensor-data/?limit=5';
    if (state.municipalityId) url += `&municipality_id=${state.municipalityId}`;
    if (state.barangayId) url += `&barangay_id=${state.barangayId}`;

    fetch(url, { headers: { 'Accept': 'application/json' }})
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(data => {
        const readings = data.results || [];
        const latest = {};
        readings.forEach(rdg => {
          const t = rdg.sensor_type;
          if (!latest[t] || new Date(rdg.timestamp) > new Date(latest[t].timestamp)) {
            latest[t] = rdg;
          }
        });
        setValue('temperature-value', latest.temperature?.value, '°C');
        setValue('humidity-value', latest.humidity?.value, '%');
        setValue('rainfall-value', latest.rainfall?.value, 'mm');
        setValue('water-level-value', latest.water_level?.value, 'm');
        setValue('wind-speed-value', latest.wind_speed?.value, 'km/h');
        const ts = new Date();
        const lastUpdated = document.getElementById('map-last-updated');
        if (lastUpdated) lastUpdated.textContent = ts.toLocaleString();
        updateWeatherSeverityStyles();
      })
      .catch(() => {
        setValue('temperature-value', null, '°C');
        setValue('humidity-value', null, '%');
        setValue('rainfall-value', null, 'mm');
        setValue('water-level-value', null, 'm');
        setValue('wind-speed-value', null, 'km/h');
      });
  }

  // Build a compact HTML block listing each parameter's status, showing 'Normal' when not breached.
  function buildParameterStatusHTML(sev) {
    try {
      const map = {};
      (sev.items || []).forEach(it => { map[it.parameter] = it; });
      const order = [
        {key:'temperature', label:'Temperature'},
        {key:'humidity', label:'Humidity'},
        {key:'rainfall', label:'Rainfall'},
        {key:'water_level', label:'Water Level'},
        {key:'wind_speed', label:'Wind Speed'}
      ];
      const badge = lvl => {
        const n = Number(lvl)||0;
        if (n>=5) return 'CATASTROPHIC';
        if (n>=4) return 'EMERGENCY';
        if (n>=3) return 'WARNING';
        if (n>=2) return 'WATCH';
        if (n>=1) return 'ADVISORY';
        return 'Normal';
      };
      const row = it => {
        const unit = it.unit || '';
        const lvl = Number(it.level)||0;
        const thr = it.thresholds || {};
        const thrMap = {1: thr.advisory, 2: thr.watch, 3: thr.warning, 4: thr.emergency, 5: thr.catastrophic};
        const ref = thrMap[lvl] != null ? thrMap[lvl] : '';
        const latest = (it.latest != null) ? Number(it.latest).toFixed(unit === '%' ? 0 : 2).replace(/\.00$/,'') : '—';
        const refText = ref !== '' ? Number(ref).toFixed(2).replace(/\.00$/,'') : '';
        const statusText = badge(lvl);
        const color = (lvl>=4)?'#dc2626':(lvl>=3)?'#d97706':(lvl>=1)?'#0ea5e9':'#16a34a';
        const extra = (lvl>0 && refText!=='') ? ` (>= ${refText} ${unit})` : '';
        return `<div style="display:flex; justify-content:space-between; gap:10px; padding:4px 0;">
          <span>${paramLabel(it.parameter)}</span>
          <span style="white-space:nowrap; color:${color}; font-weight:600;">${statusText}</span>
          <span style="white-space:nowrap; color:var(--gray)">Latest: ${latest} ${unit}${extra}</span>
        </div>`;
      };
      const html = order.map(o => row(map[o.key] || { parameter:o.key, unit:unitFor(o.key), level:0, latest:null, thresholds:{} })).join('');
      return `<div style="margin-top:8px; border-top:1px dashed #e5e7eb; padding-top:6px;"><strong>Parameter status</strong>${html}</div>`;
    } catch (e) {
      return '';
    }
  }

  function unitFor(key){
    const u={temperature:'°C',humidity:'%',rainfall:'mm',water_level:'m',wind_speed:'km/h'}; return u[key]||'';
  }

  function setValue(id, value, suffix) {
    const el = document.getElementById(id);
    if (!el) return;
    if (value === null || value === undefined || isNaN(value)) {
      el.textContent = '--';
      return;
    }
    const v = Number(value);
    // Format: temperature int, rainfall one decimal, water level one decimal, wind speed int
    let text = v;
    if (id.includes('rainfall') || id.includes('water-level')) text = v.toFixed(1);
    else text = Math.round(v);
    el.textContent = `${text}${suffix}`;
  }

  // Apply severity styles to Weather Conditions based on threshold endpoint
  async function updateWeatherSeverityStyles() {
    try {
      const sev = await fetchThresholdSeverity();
      if (!sev || !sev.items) return;
      const levelByParam = {};
      sev.items.forEach(it => { levelByParam[it.parameter] = it.level || 0; });
      // Apply text color to values
      applySeverityStyle('temperature-value', levelByParam.temperature || 0);
      applySeverityStyle('humidity-value', levelByParam.humidity || 0);
      applySeverityStyle('rainfall-value', levelByParam.rainfall || 0);
      applySeverityStyle('water-level-value', levelByParam.water_level || 0);
      applySeverityStyle('wind-speed-value', levelByParam.wind_speed || 0);
      // Decorate container cards with severity classes
      setSeverityClass('temperature-value', levelByParam.temperature || 0);
      setSeverityClass('humidity-value', levelByParam.humidity || 0);
      setSeverityClass('rainfall-value', levelByParam.rainfall || 0);
      setSeverityClass('water-level-value', levelByParam.water_level || 0);
      setSeverityClass('wind-speed-value', levelByParam.wind_speed || 0);

      // Update status chips and extra text using returned items
      sev.items.forEach(it => {
        const key = it.parameter; // rainfall | water_level | temperature | humidity
        const idBase = paramIdBase(key); // e.g., 'water-level'
        const latest = it.latest;
        const unit = it.unit || '';
        setStatusChip(`${idBase}-status`, it.level || 0);
        setExtraText(`${idBase}-extra`, latest, unit);
      });
    } catch (e) { /* ignore */ }
  }

  function applySeverityStyle(id, level) {
    const el = document.getElementById(id);
    if (!el) return;
    let color = '#16a34a'; // normal
    if (level >= 4) color = '#dc2626'; // danger
    else if (level >= 2) color = '#d97706'; // warning
    el.style.color = color;
  }

  // Add/remove .sev-* classes on the container .weather-item for modern styles
  function setSeverityClass(valueElementId, level) {
    const el = document.getElementById(valueElementId);
    if (!el) return;
    // Find the nearest .weather-item container
    let container = el.closest ? el.closest('.weather-item') : el.parentElement;
    if (!container) return;
    // Remove existing sev-* classes
    for (let i = 0; i <= 5; i++) {
      container.classList.remove(`sev-${i}`);
    }
    // Clamp level between 0 and 5 and apply
    const lvl = Math.max(0, Math.min(5, Number(level) || 0));
    container.classList.add(`sev-${lvl}`);
  }

  function paramIdBase(key) {
    if (!key) return '';
    // Convert API parameter keys like 'water_level' and 'wind_speed' to DOM id base 'water-level', 'wind-speed'
    return String(key).replace(/_/g, '-');
  }

  function setStatusChip(chipId, level) {
    const el = document.getElementById(chipId);
    if (!el) return;
    // Reset classes
    el.classList.remove('normal','info','warning','danger');
    // Choose label and class
    const lvl = Number(level) || 0;
    let cls = 'normal';
    if (lvl >= 4) cls = 'danger';
    else if (lvl >= 3) cls = 'warning';
    else if (lvl >= 1) cls = 'info';
    el.classList.add(cls);
    el.textContent = (lvl === 0) ? 'Normal' : severityName(lvl);
  }

  function setExtraText(extraId, latest, unit) {
    const el = document.getElementById(extraId);
    if (!el) return;
    if (latest === null || latest === undefined || isNaN(latest)) {
      el.textContent = '';
      return;
    }
    const val = Number(latest);
    const fixed = (unit === 'mm' || unit === 'm') ? val.toFixed(1) : val.toFixed(0);
    el.textContent = `Latest: ${fixed} ${unit}`.trim();
  }

  // ---------------- Alerts ----------------
  function updateAlerts() {
    const token = ++state._alertsReqToken; // capture a new token for this invocation
    let url = '/api/flood-alerts/?active=true';
    if (state.municipalityId) url += `&municipality_id=${state.municipalityId}`;
    if (state.barangayId) url += `&barangay_id=${state.barangayId}`;

    fetch(url, { headers: { 'Accept': 'application/json' }})
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(async data => {
        // Ensure this response belongs to the latest request
        if (token !== state._alertsReqToken) return; // stale response; ignore
        let results = (data.results || []);
        // If a barangay is selected, only consider alerts that affect that barangay
        if (state.barangayId) {
          const selId = String(state.barangayId);
          results = results.filter(a => Array.isArray(a.affected_barangays) && a.affected_barangays.map(String).includes(selId));
        }
        results = results.sort((a,b) => b.severity_level - a.severity_level);
        let highest = results[0] || null;
        const badge = document.getElementById('alert-status-badge');
        const title = document.getElementById('alert-title');
        const msg = document.getElementById('alert-message');
        if (!badge || !title || !msg) return;

        // Always compute threshold-based severity for context
        const sev = await fetchThresholdSeverity();
        // If selection changed while awaiting thresholds, drop this update
        if (token !== state._alertsReqToken) return;
        const thresholdLevel = (sev && typeof sev.level === 'number') ? sev.level : 0;
        const combinedLevel = Math.max(highest ? (highest.severity_level || 0) : 0, thresholdLevel);

        // Badge color and text from combinedLevel
        const levels = {1:'ADVISORY',2:'WATCH',3:'WARNING',4:'EMERGENCY',5:'CATASTROPHIC'};
        const levelText = combinedLevel > 0 ? (levels[combinedLevel] || severityName(combinedLevel)) : 'Normal';
        badge.textContent = levelText;
        badge.classList.remove('status-normal','status-warning','status-danger');
        if (combinedLevel >= 4) badge.classList.add('status-danger');
        else if (combinedLevel >= 2) badge.classList.add('status-warning');
        else badge.classList.add('status-normal');

        // Resolve display location text from selectors
        const muniSel = document.getElementById('location-select');
        const brgySel = document.getElementById('barangay-select');
        const muniName = (muniSel && muniSel.selectedIndex > -1) ? muniSel.options[muniSel.selectedIndex].text : '';
        const brgyName = (brgySel && brgySel.selectedIndex > -1) ? brgySel.options[brgySel.selectedIndex].text : '';
        const locText = state.barangayId ? brgyName : (state.municipalityId ? muniName : 'All Locations');

        // Title and concise message with compact threshold details (full list remains below)
        if (highest && (highest.severity_level || 0) >= thresholdLevel) {
          // Prioritize active alert severity, but display current selection name
          title.textContent = `${levels[highest.severity_level] || 'ALERT'}: Automated Alert for ${locText}`;
          const lines = [];
          // Use a location-aware description instead of the stored alert description,
          // which may reference a different barangay.
          const desc = (state.barangayId || state.municipalityId)
            ? `The system is monitoring environmental conditions in ${escapeHtml(locText)}.`
            : 'The system is monitoring environmental conditions continuously.';
          lines.push(desc);
          if (sev && Array.isArray(sev.items)) {
            const top = sev.items.filter(it => (it.level||0)>0).sort((a,b)=> (b.level||0)-(a.level||0)).slice(0,3);
            if (top.length) {
              lines.push(buildThresholdDetails(top));
            }
          }
          msg.innerHTML = lines.join('<br>');
          updateAffectedAreas(highest.affected_barangays || []);
        } else if (thresholdLevel > 0 && sev) {
          // Threshold-driven status only
          const text = severityName(thresholdLevel);
          const top = (sev.items || []).sort((a,b)=>b.level-a.level)[0];
          const topLabel = top ? paramLabel(top.parameter) : 'Threshold';
          title.textContent = `${text}: ${topLabel} for ${locText}`;
          const lines = ['Conditions exceed configured thresholds.'];
          const topItems = (sev.items || []).filter(it => (it.level||0)>0).sort((a,b)=> (b.level||0)-(a.level||0)).slice(0,3);
          if (topItems.length) lines.push(buildThresholdDetails(topItems));
          msg.innerHTML = lines.join('<br>');
          updateAffectedAreas([]);
        } else {
          // No alerts and no threshold breach -> Normal
          title.textContent = 'No Active Alerts';
          msg.textContent = 'The system is monitoring environmental conditions continuously.';
          updateAffectedAreas([]);
        }

        // Render parameter status list using compact endpoint
        try {
          const p = await fetchParameterStatus();
          if (token !== state._alertsReqToken) return;
          renderParamStatusList(p && p.items ? p.items : []);
          // If we couldn't add compact details earlier (sev may have failed), try to append from parameter-status
          try {
            const msgEl = document.getElementById('alert-message');
            if (msgEl && p && Array.isArray(p.items) && msgEl.innerHTML.indexOf('<ul') === -1) {
              const mapped = p.items
                .filter(x => (x.level || 0) > 0)
                .map(x => ({
                  parameter: x.parameter || x.name || '',
                  unit: x.unit || '',
                  latest: (x.latest != null) ? x.latest : (x.value != null ? x.value : (x.latest_value != null ? x.latest_value : null)),
                  level: x.level || 0,
                  thresholds: x.thresholds || {}
                }));
              if (mapped.length) {
                msgEl.innerHTML += '<br>' + buildThresholdDetails(mapped.slice(0,3));
              }
            }
          } catch (e) { /* ignore */ }
        } catch (e) {
          // ignore
        }
      })
      .catch(() => {
        // Leave as-is on error
      });
  }

  // Build a compact HTML list of top breached thresholds
  function buildThresholdDetails(items) {
    const sevLabel = lvl => (lvl>=5?'CATASTROPHIC':lvl>=4?'EMERGENCY':lvl>=3?'WARNING':lvl>=2?'WATCH':lvl>=1?'ADVISORY':'NORMAL');
    const rows = items.map(it => {
      const lbl = paramLabel(it.parameter);
      const unit = it.unit || '';
      const thr = it.thresholds || {};
      const thrMap = {1: thr.advisory, 2: thr.watch, 3: thr.warning, 4: thr.emergency, 5: thr.catastrophic};
      const ref = thrMap[it.level] != null ? thrMap[it.level] : '';
      const latest = (it.latest != null) ? Number(it.latest).toFixed(unit === '%' ? 0 : 2).replace(/\.00$/, '') : '—';
      const refText = ref !== '' ? Number(ref).toFixed(unit === '%' ? 0 : 2).replace(/\.00$/, '') : '—';
      return `<li><strong>${lbl}:</strong> ${latest} ${unit} > <em>${sevLabel(it.level)}</em> (${refText} ${unit})`;
    });
    return `<ul style="margin:6px 0 0 18px; padding:0; color:#334155; font-size:13px; line-height:1.35;">${rows.join('')}</ul>`;
  }

  async function fetchParameterStatus() {
    try {
      const params = [];
      // Request a compact per-parameter status for the current selection
      if (state.municipalityId) params.push(`municipality_id=${state.municipalityId}`);
      if (state.barangayId) params.push(`barangay_id=${state.barangayId}`);
      const url = `/api/parameter-status/${params.length ? ('?' + params.join('&')) : ''}`;
      const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  async function fetchThresholdSeverity() {
    try {
      const params = [];
      params.push('parameter=rainfall,water_level,temperature,humidity,wind_speed');
      if (state.municipalityId) params.push(`municipality_id=${state.municipalityId}`);
      if (state.barangayId) params.push(`barangay_id=${state.barangayId}`);
      const url = `/api/threshold-visualization/?${params.join('&')}`;
      const res = await fetch(url, { headers: { 'Accept': 'application/json' }});
      if (!res.ok) return null;
      const data = await res.json();
      const items = (data.data || []).map(it => ({
        parameter: it.parameter,
        unit: it.unit,
        latest: it.latest ? it.latest.value : null,
        level: it.severity ? (it.severity.level || 0) : 0,
        thresholds: it.thresholds || {}
      }));
      const maxLevel = items.reduce((m, it) => Math.max(m, it.level || 0), 0);
      return { level: maxLevel, items };
    } catch (e) { return null; }
  }

  function updateAffectedAreas(affectedBarangayIds) {
    const tbody = document.getElementById('affected-areas-body');
    if (!tbody) return;

    if (!affectedBarangayIds || affectedBarangayIds.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" style="color: var(--gray)">No barangays currently affected by floods.</td></tr>';
      return;
    }

    // Fetch barangay details and render rows
    let url = '/api/barangays/?limit=500';
    if (state.municipalityId) url += `&municipality_id=${state.municipalityId}`;
    if (state.barangayId) url += `&id=${state.barangayId}`;

    fetch(url, { headers: { 'Accept': 'application/json' }})
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(data => {
        const barangays = (data.results || []).filter(b => affectedBarangayIds.includes(b.id));
        if (barangays.length === 0) {
          tbody.innerHTML = '<tr><td colspan="3" style="color: var(--gray)">No barangays currently affected by floods.</td></tr>';
          return;
        }
        tbody.innerHTML = barangays.map(b => {
          const riskClass = 'status-normal'; // Could be mapped from severity in map-data if available
          return `<tr>
            <td>${escapeHtml(b.name || '—')}</td>
            <td>${Number(b.population || 0).toLocaleString()}</td>
            <td><span class="status-badge ${riskClass}">Low</span></td>
          </tr>`;
        }).join('');
      })
      .catch(() => {
        tbody.innerHTML = '<tr><td colspan="3">Unable to load affected areas at this time.</td></tr>';
      });
  }

  // ---------------- Map ----------------
  function initMap() {
    const container = document.getElementById('flood-map');
    if (!container || !window.L) return;
    state.map = L.map('flood-map').setView([12.8797, 121.7740], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(state.map);

    state.mapLayers.zones = L.layerGroup().addTo(state.map);
    state.mapLayers.sensors = L.layerGroup().addTo(state.map);
    state.mapLayers.barangays = L.layerGroup().addTo(state.map);
    state.mapLayers.heat = null; // heat layer holder
    state.heatEnabled = state.heatEnabled || false;

    // Add heat toggle control first (so it appears above other controls)
    addHeatToggleControl(state.map);
    // Then add fullscreen control
    addFullscreenControl(state.map, 'flood-map');
    // Bind sidebar heatmap toggle
    bindHeatmapToggleUI();

    // ESC to exit fullscreen
    window.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') {
        const el = document.getElementById('flood-map');
        if (el && el.dataset.fullscreen === '1') {
          toggleMapFullscreen('flood-map', state.map);
        }
      }
    });

    // Debounced/observed resize handling to fix tile alignment in grids
    const invalidate = () => { try { state.map && state.map.invalidateSize(true); } catch (e) {} };
    // Initial invalidate passes after render to avoid fractional height gaps
    setTimeout(invalidate, 50);
    setTimeout(invalidate, 250);
    setTimeout(invalidate, 600);
    setTimeout(invalidate, 1000);
    // Window resize
    let resizeTimer = null;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(invalidate, 120);
    });
    // Container resize
    if (window.ResizeObserver) {
      try {
        const ro = new ResizeObserver(() => {
          clearTimeout(resizeTimer);
          resizeTimer = setTimeout(invalidate, 60);
        });
        ro.observe(container);
        state._mapResizeObserver = ro;
      } catch (e) { /* ignore */ }
    }
  }

  function updateMapData() {
    if (!state.map) return;
    let url = '/api/map-data/';
    const params = [];
    if (state.municipalityId) params.push(`municipality_id=${state.municipalityId}`);
    if (state.barangayId) params.push(`barangay_id=${state.barangayId}`);
    if (params.length) url += '?' + params.join('&');

    const lastUpdated = document.getElementById('map-last-updated');
    if (lastUpdated) lastUpdated.textContent = 'Loading data...';

    fetch(url, { headers: { 'Accept': 'application/json' }})
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(async data => {
        clearMapLayers();
        drawZones(data.zones || []);
        drawSensors(data.sensors || []);
        drawBarangays(data.barangays || []);
        renderLocationsList(data.barangays || []);
        // Prefer server-computed heatmap points, fallback to client-built
        try {
          const hp = await fetchHeatmapPoints();
          if (hp && Array.isArray(hp.points)) {
            state._heatPoints = hp.points;
          } else {
            state._heatPoints = buildHeatPoints(data);
          }
          updateHeatLayer(state._heatPoints || []);
        } catch (e) {
          // fallback
          try { state._heatPoints = buildHeatPoints(data); updateHeatLayer(state._heatPoints || []); } catch(_) {}
        }
        if (lastUpdated) lastUpdated.textContent = new Date().toLocaleString();
        // Ensure map tiles realign after layer updates
        try {
          state.map && state.map.invalidateSize(true);
          // a couple of delayed passes to remove any hairline gaps
          setTimeout(() => { try { state.map && state.map.invalidateSize(true); } catch (e) {} }, 120);
          setTimeout(() => { try { state.map && state.map.invalidateSize(true); } catch (e) {} }, 300);
        } catch (e) {}
      })
      .catch(() => {
        if (lastUpdated) lastUpdated.textContent = 'Unable to load map data';
      });
  }

  function clearMapLayers() {
    Object.values(state.mapLayers).forEach(layer => layer && layer.clearLayers());
    barangayLayerById.clear();
  }

  function drawZones(zones) {
    zones.forEach(z => {
      try {
        const gj = typeof z.geojson === 'string' ? JSON.parse(z.geojson) : z.geojson;
        if (gj) {
          L.geoJSON(gj, {
            style: feature => ({
              color: zoneColor(z.risk_level || z.severity || 'low'),
              weight: 2,
              fillOpacity: 0.2,
            })
          }).addTo(state.mapLayers.zones);
        }
      } catch (e) { /* ignore malformed */ }
    });
  }

  function drawSensors(sensors) {
    sensors.forEach(s => {
      if (!s.lat || !s.lng) return;
      const marker = L.circleMarker([s.lat, s.lng], {
        radius: 6,
        color: '#0d6efd',
        fillColor: '#0d6efd',
        fillOpacity: 0.8
      });
      const valueText = (s.latest_reading && s.latest_reading.value != null) ? s.latest_reading.value : '—';
      marker.bindPopup(
        `<strong>${escapeHtml(s.name || 'Sensor')}</strong><br>` +
        `Type: ${escapeHtml((s.type || '').toString())}<br>` +
        `Value: ${escapeHtml(valueText.toString())}`
      );
      marker.addTo(state.mapLayers.sensors);
    });
  }

  function drawBarangays(items) {
    const coords = [];
    barangayLayerById.clear();
    items.forEach(b => {
      if (!b.lat || !b.lng) return;
      coords.push([b.lat, b.lng]);
      // Severity-aware styling if API provides severity/risk_level
      const sevNum = (typeof b.severity === 'number') ? b.severity
                    : (String(b.risk_level||'').toLowerCase()==='high' ? 5
                      : String(b.risk_level||'').toLowerCase()==='medium' ? 3
                      : String(b.risk_level||'').toLowerCase()==='low' ? 1 : 0);
      const color = (sevNum>=4) ? '#ef4444' : (sevNum>=3) ? '#f59e0b' : '#10b981';
      const radius = 200 + Math.min(800, Math.sqrt(b.population || 1));
      const circle = L.circle([b.lat, b.lng], {
        radius,
        color,
        weight: 1,
        fillColor: color,
        fillOpacity: 0.15
      });
      circle.bindPopup(`<strong>${escapeHtml(b.name || 'Barangay')}</strong><br>Population: ${Number(b.population||0).toLocaleString()}`);
      circle.addTo(state.mapLayers.barangays);

      // Keep reference by id for focusing and interaction
      if (b.id != null) {
        barangayLayerById.set(String(b.id), circle);
      }

      // Clicking a barangay circle updates the dropdown and filters dashboard
      circle.on('click', () => {
        const brgySel = document.getElementById('barangay-select');
        if (b.id != null) {
          state.barangayId = String(b.id);
          if (brgySel) brgySel.value = String(b.id);
          sessionStorage.setItem('dashboard_barangay_id', state.barangayId || '');
          refreshAll();
          // Automatically apply thresholds when selecting via map
          applyThresholdsNow();
        }
      });
    });

    // If a specific barangay is selected, zoom tighter and open popup
    if (state.barangayId && barangayLayerById.has(String(state.barangayId))) {
      const layer = barangayLayerById.get(String(state.barangayId));
      const ll = layer.getLatLng();
      state.map.setView(ll, 15);
      layer.openPopup();
      // Brief highlight pulse
      const pulse = L.circleMarker(ll, { radius: 18, color: '#0d6efd', fillColor: '#0d6efd', fillOpacity: 0.3, weight: 2 });
      pulse.addTo(state.mapLayers.barangays);
      setTimeout(() => { state.mapLayers.barangays.removeLayer(pulse); }, 1500);
    } else if (state.barangayId && coords.length === 1) {
      state.map.setView(coords[0], 15);
    } else if (coords.length > 0) {
      state.map.fitBounds(coords, { padding: [20, 20] });
    }
  }

  function zoneColor(level) {
    const l = (typeof level === 'string') ? level.toLowerCase() : level;
    if (l === 'high' || l === 3) return '#ef4444';
    if (l === 'medium' || l === 2) return '#f59e0b';
    return '#10b981';
  }

  // ---------------- Trends chart ----------------
  function initChart() {
    const canvas = document.getElementById('trends-chart');
    if (!canvas || !window.Chart) return;
    // If an old chart exists (e.g., from hot reload), destroy it first
    try { if (state.chart && state.chart.destroy) state.chart.destroy(); } catch (_) {}
    state.chart = new Chart(canvas, {
      type: 'line',
      data: { labels: [], datasets: [
        // Left axis (Temp/Humidity)
        themedDataset('Temperature (°C)', 'rgba(239,68,68,1)', 'y'),
        themedDataset('Humidity (%)',     'rgba(14,165,233,1)', 'y'),
        // Right axis (Rain/Water/Wind)
        themedDataset('Rainfall (mm)',    'rgba(59,130,246,1)', 'y1'),
        themedDataset('Water Level (m)',  'rgba(16,185,129,1)', 'y1'),
        themedDataset('Wind Speed (km/h)','rgba(168,85,247,1)', 'y1'),
      ]},
      options: {
        responsive: true,
        maintainAspectRatio: false,
        spanGaps: true,
        interaction: { mode: 'index', intersect: false },
        parsing: false,
        elements: {
          line: { tension: 0.2, borderWidth: 2 },
          point: { radius: 4, hoverRadius: 6, borderWidth: 2, backgroundColor: '#ffffff' }
        },
        animation: { duration: 0 },
        transitions: { active: { animation: { duration: 0 } }, resize: { animation: { duration: 0 } } },
        plugins: {
          legend: { position: 'top' },
          tooltip: { enabled: true },
          // Explicitly disable zoom/pan to avoid scriptable recursion from plugin defaults
          zoom: { pan: { enabled: false }, zoom: { wheel: { enabled: false }, pinch: { enabled: false }, drag: { enabled: false } } }
        },
        scales: {
          x: { type: 'category', grid: { display: false } },
          y: {
            type: 'linear', position: 'left',
            title: { display: true, text: 'Temperature (°C) / Humidity (%)' }
          },
          y1: {
            type: 'linear', position: 'right',
            title: { display: true, text: 'Rainfall (mm) / Water Level (m) / Wind (km/h)' },
            grid: { drawOnChartArea: false }
          }
        }
      }
    });

    // Helper to create themed dataset with outlined points
    function themedDataset(label, color, axis) {
      return {
        label,
        data: [],
        borderColor: color,
        backgroundColor: 'transparent',
        cubicInterpolationMode: 'monotone',
        yAxisID: axis,
        parsing: false,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBorderColor: color,
        pointBackgroundColor: '#ffffff',
        pointBorderWidth: 2,
        borderWidth: 2,
        fill: false
      };
    }
  }

  function loadTrendsChart() {
    // Ensure chart exists
    if (!state.chart) { try { initChart(); } catch(e) {} }
    if (!state.chart || state._trendsFetchInFlight) return;
    state._trendsFetchInFlight = true;
    // Optimistically set a starting timestamp so the UI doesn't show '—'
    try {
      const el = document.getElementById('trends-updated-at');
      if (el && (!el.textContent || /—\s*$/.test(el.textContent))) {
        el.textContent = `Last updated: ${formatManilaFull(new Date().toISOString())}`;
      }
    } catch (e) { /* ignore */ }

    // Loading overlay removed per request

    const runOnce = (includeBarangayScope) => {
      const queries = [
        fetchChart('temperature', { includeBarangay: includeBarangayScope }),
        fetchChart('humidity', { includeBarangay: includeBarangayScope }),
        fetchChart('rainfall', { includeBarangay: includeBarangayScope }),
        fetchChart('water_level', { includeBarangay: includeBarangayScope }),
        fetchChart('wind_speed', { includeBarangay: includeBarangayScope }),
      ];
      return Promise.allSettled(queries);
    };

    runOnce(true).then(results => {
      const temp = (results[0].status === 'fulfilled') ? results[0].value : { labels: [], values: [] };
      const hum  = (results[1].status === 'fulfilled') ? results[1].value : { labels: [], values: [] };
      const rain = (results[2].status === 'fulfilled') ? results[2].value : { labels: [], values: [] };
      const water= (results[3].status === 'fulfilled') ? results[3].value : { labels: [], values: [] };
      const wind = (results[4].status === 'fulfilled') ? results[4].value : { labels: [], values: [] };

      // Determine the latest timestamp across all series (consider ISO and Manila labels)
      const allLabelArrays = [
        temp.labels, temp.labelsManila,
        hum.labels, hum.labelsManila,
        rain.labels, rain.labelsManila,
        water.labels, water.labelsManila,
        wind.labels, wind.labelsManila,
      ].filter(Boolean);
      let latestIso = null;
      const toDate = (s) => {
        if (!s) return null;
        // If string lacks timezone, assume UTC by appending 'Z'
        const str = (typeof s === 'string' && !/Z|\+\d{2}:?\d{2}$/.test(s)) ? `${s}Z` : s;
        const d = new Date(str);
        return isNaN(d.getTime()) ? null : d;
      };
      try {
        for (const arr of allLabelArrays) {
          for (const ts of arr) {
            const d = toDate(ts);
            if (!d) continue;
            if (!latestIso || d > new Date(latestIso)) latestIso = d.toISOString();
          }
        }
      } catch (e) { /* ignore */ }

      let merged = mergeSeries([
        { labels: temp.labels,  values: temp.values,  key: 't' },
        { labels: hum.labels,   values: hum.values,   key: 'h' },
        { labels: rain.labels,  values: rain.values,  key: 'r' },
        { labels: water.labels, values: water.values, key: 'wl' },
        { labels: wind.labels,  values: wind.values,  key: 'ws' },
      ]);

      // Early exit: if nothing came back, show a friendly overlay and reset chart
      const anyData = (() => {
        const s = merged.series || {};
        const keys = ['t','h','r','wl','ws'];
        for (const k of keys) {
          const arr = s[k] || [];
          if (arr.some(v => typeof v === 'number' && !isNaN(v))) return true;
        }
        return false;
      })();

      if (!merged.labels.length || !anyData) {
        // If barangay is selected, retry once without barangay_id (fallback to municipality-level data)
        if (state.barangayId) {
          return runOnce(false).then(results2 => {
            const t2 = (results2[0].status === 'fulfilled') ? results2[0].value : { labels: [], values: [] };
            const h2 = (results2[1].status === 'fulfilled') ? results2[1].value : { labels: [], values: [] };
            const r2 = (results2[2].status === 'fulfilled') ? results2[2].value : { labels: [], values: [] };
            const wL2= (results2[3].status === 'fulfilled') ? results2[3].value : { labels: [], values: [] };
            const wS2= (results2[4].status === 'fulfilled') ? results2[4].value : { labels: [], values: [] };
            const merged2 = mergeSeries([
              { labels: t2.labels,  values: t2.values,  key: 't' },
              { labels: h2.labels,  values: h2.values,  key: 'h' },
              { labels: r2.labels,  values: r2.values,  key: 'r' },
              { labels: wL2.labels, values: wL2.values, key: 'wl' },
              { labels: wS2.labels, values: wS2.values, key: 'ws' },
            ]);
            const anyData2 = (() => {
              const s = merged2.series || {};
              const keys = ['t','h','r','wl','ws'];
              for (const k of keys) {
                const arr = s[k] || [];
                if (arr.some(v => typeof v === 'number' && !isNaN(v))) return true;
              }
              return false;
            })();
            if (!merged2.labels.length || !anyData2) {
              // If municipality is selected, final retry without municipality filter
              if (state.municipalityId) {
                const runNoMuni = () => Promise.allSettled([
                  fetchChart('temperature', { includeBarangay: false, includeMunicipality: false }),
                  fetchChart('humidity',    { includeBarangay: false, includeMunicipality: false }),
                  fetchChart('rainfall',    { includeBarangay: false, includeMunicipality: false }),
                  fetchChart('water_level', { includeBarangay: false, includeMunicipality: false }),
                  fetchChart('wind_speed',  { includeBarangay: false, includeMunicipality: false }),
                ]);
                return runNoMuni().then(results3 => {
                  const t3 = (results3[0].status === 'fulfilled') ? results3[0].value : { labels: [], values: [] };
                  const h3 = (results3[1].status === 'fulfilled') ? results3[1].value : { labels: [], values: [] };
                  const r3 = (results3[2].status === 'fulfilled') ? results3[2].value : { labels: [], values: [] };
                  const wL3= (results3[3].status === 'fulfilled') ? results3[3].value : { labels: [], values: [] };
                  const wS3= (results3[4].status === 'fulfilled') ? results3[4].value : { labels: [], values: [] };
                  const merged3 = mergeSeries([
                    { labels: t3.labels,  values: t3.values,  key: 't' },
                    { labels: h3.labels,  values: h3.values,  key: 'h' },
                    { labels: r3.labels,  values: r3.values,  key: 'r' },
                    { labels: wL3.labels, values: wL3.values, key: 'wl' },
                    { labels: wS3.labels, values: wS3.values, key: 'ws' },
                  ]);
                  const anyData3 = (() => {
                    const s = merged3.series || {}; const keys = ['t','h','r','wl','ws'];
                    for (const k of keys) { const arr = s[k] || []; if (arr.some(v => typeof v === 'number' && !isNaN(v))) return true; }
                    return false;
                  })();
                  if (!merged3.labels.length || !anyData3) { showTrendsNoData(); return; }
                  renderTrendsFromMerged(merged3, /*annotateFallback=*/true);
                });
              }
              // Still no data; show empty state
              showTrendsNoData();
              return;
            }
            // Render with fallback and annotate scope
            renderTrendsFromMerged(merged2, /*annotateFallback=*/true);
          });
        }
        // No barangay selected -> if municipality is selected, try without municipality filter
        if (state.municipalityId) {
          const runNoMuni = () => Promise.allSettled([
            fetchChart('temperature', { includeMunicipality: false }),
            fetchChart('humidity',    { includeMunicipality: false }),
            fetchChart('rainfall',    { includeMunicipality: false }),
            fetchChart('water_level', { includeMunicipality: false }),
            fetchChart('wind_speed',  { includeMunicipality: false }),
          ]);
          return runNoMuni().then(results3 => {
            const t3 = (results3[0].status === 'fulfilled') ? results3[0].value : { labels: [], values: [] };
            const h3 = (results3[1].status === 'fulfilled') ? results3[1].value : { labels: [], values: [] };
            const r3 = (results3[2].status === 'fulfilled') ? results3[2].value : { labels: [], values: [] };
            const wL3= (results3[3].status === 'fulfilled') ? results3[3].value : { labels: [], values: [] };
            const wS3= (results3[4].status === 'fulfilled') ? results3[4].value : { labels: [], values: [] };
            const merged3 = mergeSeries([
              { labels: t3.labels,  values: t3.values,  key: 't' },
              { labels: h3.labels,  values: h3.values,  key: 'h' },
              { labels: r3.labels,  values: r3.values,  key: 'r' },
              { labels: wL3.labels, values: wL3.values, key: 'wl' },
              { labels: wS3.labels, values: wS3.values, key: 'ws' },
            ]);
            const anyData3 = (() => {
              const s = merged3.series || {}; const keys = ['t','h','r','wl','ws'];
              for (const k of keys) { const arr = s[k] || []; if (arr.some(v => typeof v === 'number' && !isNaN(v))) return true; }
              return false;
            })();
            if (!merged3.labels.length || !anyData3) { showTrendsNoData(); return; }
            renderTrendsFromMerged(merged3, /*annotateFallback=*/true);
          });
        }
        // No municipality either -> show empty overlay
        showTrendsNoData();
        return;
      }

      // Store the original ISO labels for tooltips, but display compact Manila time on the axis
      renderTrendsFromMerged(merged, /*annotateFallback=*/false);
    }).finally(() => {
      state._trendsFetchInFlight = false;
      try {
        const el = document.getElementById('trends-updated-at');
        if (el && (!el.textContent || /—\s*$/.test(el.textContent))) {
          el.textContent = `Last updated: ${formatManilaFull(new Date().toISOString())}`;
        }
      } catch (e) { /* ignore */ }
    });
  }

  function showTrendsNoData() {
    try {
      if (!state.chart) { try { initChart(); } catch(e) {} if (!state.chart) return; }
      state.chart.data.labels = [];
      state.chart.data.datasets.forEach(ds => { ds.data = []; });
      const y = state.chart.options && state.chart.options.scales ? state.chart.options.scales.y : null;
      const y1 = state.chart.options && state.chart.options.scales ? state.chart.options.scales.y1 : null;
      if (y) { y.suggestedMin = 0; y.suggestedMax = 100; }
      if (y1) { y1.suggestedMin = 0; y1.suggestedMax = 10; }
      try { state.chart.update(); } catch (e) { recreateChart([], { t:[], h:[], r:[], wl:[], ws:[] }); }
      const scopeMsg = state.barangayId ? 'No data for selected barangay. Auto-checking municipality data…' : 'No data available for the selected location.';
      setChartOverlay(scopeMsg);
      const el = document.getElementById('trends-updated-at');
      if (el) el.textContent = 'Last updated: —';
    } catch (e) { /* ignore */ }
  }

  // If Chart.js encounters plugin/scriptable recursion, rebuild with a minimal config
  function recreateChart(labels, series) {
    try {
      const now = Date.now();
      if (state._lastRecreateAt && (now - state._lastRecreateAt) < 2000) return;
      state._lastRecreateAt = now;
      const canvas = document.getElementById('trends-chart');
      if (!canvas || !window.Chart) return;
      const ctx = canvas.getContext && canvas.getContext('2d');
      if (!ctx) return; // cannot draw (not in DOM or no 2D context)
      // Destroy existing
      try {
        if (state.chart && state.chart.destroy) {
          const old = state.chart; state.chart = null; old.destroy();
        }
      } catch (_) {}
      // Build minimal datasets
      const L = Array.isArray(labels) ? labels.length : 0;
      const clamp = (arr) => (Array.isArray(arr) ? arr.slice(0, L) : new Array(L).fill(null));
      const ds = [
        { label: 'Temperature (°C)', data: clamp(series.t),  borderColor: 'rgba(239,68,68,1)', backgroundColor: 'transparent', yAxisID: 'y' },
        { label: 'Humidity (%)',     data: clamp(series.h),  borderColor: 'rgba(14,165,233,1)', backgroundColor: 'transparent', yAxisID: 'y' },
        { label: 'Rainfall (mm)',    data: clamp(series.r),  borderColor: 'rgba(59,130,246,1)', backgroundColor: 'transparent', yAxisID: 'y1' },
        { label: 'Water Level (m)',  data: clamp(series.wl), borderColor: 'rgba(16,185,129,1)', backgroundColor: 'transparent', yAxisID: 'y1' },
        { label: 'Wind Speed (km/h)',data: clamp(series.ws), borderColor: 'rgba(168,85,247,1)', backgroundColor: 'transparent', yAxisID: 'y1' },
      ];
      state.chart = new Chart(ctx, {
        type: 'line',
        data: { labels: labels || [], datasets: ds },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          parsing: false,
          animation: { duration: 0 },
          plugins: { legend: { position: 'top' }, tooltip: { enabled: true } },
          scales: { x: { type: 'category' }, y: { type: 'linear', position: 'left' }, y1: { type: 'linear', position: 'right', grid: { drawOnChartArea: false } } }
        }
      });
      // Recompute axis ranges
      try { applyChartScaling(series); } catch (_) {}
      try { state.chart.update(); } catch (_) {}
    } catch (_) { /* swallow */ }
  }

  function renderTrendsFromMerged(merged, annotateFallback) {
    // Optionally filter by selected range on the client side
    const filtered = filterMergedByRange(merged, state.trendsRange);
    // If chart is not present, try to (re)initialize and bail out for this tick
    if (!state.chart) { try { initChart(); } catch(e) {} return; }
    // Store the original ISO labels for tooltips, but display compact Manila time on the axis
    state.chart.__isoLabels = (filtered.labels || []).slice();
    const displayLabels = (filtered.labels || []).map(formatManilaShort);
    state.chart.data.labels = displayLabels;
    // Cache raw series and apply scaling per current toggle
    state._rawSeries = filtered.series;
    applyChartScaling(filtered.series);
    try {
      state.chart.update();
    } catch (e) {
      // As a fallback, recreate a minimal chart on next tick to ensure canvas is ready
      try { console.warn('[Trends] chart.update failed, recreating chart:', e && e.message ? e.message : e); } catch(_) {}
      const labelsSafe = Array.isArray(state.chart.data.labels) ? state.chart.data.labels.slice() : [];
      setTimeout(() => recreateChart(labelsSafe, filtered.series), 0);
      return;
    }

    // Update 'Last updated'
    try {
      const el = document.getElementById('trends-updated-at');
      if (el) {
        const lastIso = (filtered.labels && filtered.labels.length)
          ? filtered.labels[filtered.labels.length - 1]
          : new Date().toISOString();
        const when = formatManilaFull(lastIso);
        el.textContent = annotateFallback ? `Last updated: ${when} (municipality scope)` : `Last updated: ${when}`;
      }
    } catch (e) { /* ignore */ }

    // Clear overlays
    clearChartOverlay();
  }

  // ------- Chart overlay helpers (loading / no data) -------
  function ensureChartOverlayHost() {
    const container = document.querySelector('.chart-container-modern');
    if (!container) return null;
    let host = container.querySelector('.chart-overlay-host');
    if (!host) {
      host = document.createElement('div');
      host.className = 'chart-overlay-host';
      Object.assign(host.style, {
        position: 'absolute', inset: '0', display: 'flex', alignItems: 'center', justifyContent: 'center',
        pointerEvents: 'none', color: 'var(--gray)', fontSize: '14px',
      });
      // Ensure parent is positioned
      const cs = window.getComputedStyle(container);
      if (cs.position === 'static') container.style.position = 'relative';
      container.appendChild(host);
    }
    return host;
  }

  function setChartOverlay(text) {
    const host = ensureChartOverlayHost();
    if (!host) return;
    host.textContent = text || '';
    host.style.display = 'flex';
  }

  function clearChartOverlay() {
    const container = document.querySelector('.chart-container-modern');
    const host = container ? container.querySelector('.chart-overlay-host') : null;
    if (host) host.remove();
  }

  // Filter merged series by a range key ('latest' | '1w' | '1m' | '1y').
  // Keeps label alignment and nulls across all series.
  function filterMergedByRange(merged, rangeKey) {
    try {
      const out = { labels: [], series: { t:[], h:[], r:[], wl:[], ws:[] } };
      const labels = Array.isArray(merged.labels) ? merged.labels : [];
      const series = merged.series || {};
      const mapDays = { '1w':7, '1m':30, '1y':365 };
      if (!labels.length || rangeKey === 'latest' || !mapDays[rangeKey]) {
        return { labels: labels.slice(), series: {
          t: (series.t||[]).slice(),
          h: (series.h||[]).slice(),
          r: (series.r||[]).slice(),
          wl:(series.wl||[]).slice(),
          ws:(series.ws||[]).slice(),
        }};
      }
      const lastIso = labels[labels.length - 1];
      const lastDate = new Date(lastIso);
      if (isNaN(lastDate.getTime())) {
        return { labels: labels.slice(), series: {
          t: (series.t||[]).slice(), h:(series.h||[]).slice(), r:(series.r||[]).slice(), wl:(series.wl||[]).slice(), ws:(series.ws||[]).slice()
        }};
      }
      const days = mapDays[rangeKey];
      const cutoffMs = lastDate.getTime() - days * 24 * 60 * 60 * 1000;
      for (let i = 0; i < labels.length; i++) {
        const d = new Date(labels[i]);
        if (!isNaN(d.getTime()) && d.getTime() >= cutoffMs) {
          out.labels.push(labels[i]);
          out.series.t.push((series.t||[])[i] ?? null);
          out.series.h.push((series.h||[])[i] ?? null);
          out.series.r.push((series.r||[])[i] ?? null);
          out.series.wl.push((series.wl||[])[i] ?? null);
          out.series.ws.push((series.ws||[])[i] ?? null);
        }
      }
      return out;
    } catch (e) {
      return merged;
    }
  }

  // Apply scaling based on state.normalize. When true, normalize each series to 0–100 keeping nulls intact.
  function applyChartScaling(series) {
    try {
      if (!state.chart || !state.chart.options || !state.chart.options.scales) return;
      const y = state.chart.options.scales.y;
      const y1 = state.chart.options.scales.y1;
      if (state.normalize) {
      const tN  = normalizeArray(series.t);
      const hN  = normalizeArray(series.h);
      const rN  = normalizeArray(series.r);
      const wlN = normalizeArray(series.wl);
      const wsN = normalizeArray(series.ws);
      state.chart.data.datasets[0].data = tN;
      state.chart.data.datasets[1].data = hN;
      state.chart.data.datasets[2].data = rN;
      state.chart.data.datasets[3].data = wlN;
      state.chart.data.datasets[4].data = wsN;
      // Single axis 0–100 for all
      if (y) { y.suggestedMin = 0; y.suggestedMax = 100; }
      // Do not toggle axis display dynamically to avoid scriptable recursion
      } else {
      // Restore raw data
      state.chart.data.datasets[0].data = series.t;
      state.chart.data.datasets[1].data = series.h;
      state.chart.data.datasets[2].data = series.r;
      state.chart.data.datasets[3].data = series.wl;
      state.chart.data.datasets[4].data = series.ws;
      // Compute dynamic axis bounds as before
      const tVals  = (series.t  || []).filter(v => v != null);
      const hVals  = (series.h  || []).filter(v => v != null);
      const rVals  = (series.r  || []).filter(v => v != null);
      const wlVals = (series.wl || []).filter(v => v != null);
      const wsVals = (series.ws || []).filter(v => v != null);
      const leftAll = [...tVals, ...hVals];
      if (leftAll.length) {
        const min = Math.min(...leftAll);
        const max = Math.max(...leftAll);
        if (y) { y.suggestedMin = Math.floor(Math.min(0, min - 1)); y.suggestedMax = Math.ceil(max + 1); }
      } else {
        if (y) { y.suggestedMin = 0; y.suggestedMax = 100; }
      }
      if (y1) {
        const rightAll = [
          rVals.length ? Math.max(...rVals) : 0,
          wlVals.length ? Math.max(...wlVals) : 0,
          wsVals.length ? Math.max(...wsVals) : 0,
        ];
        const rightMax = Math.max(...rightAll);
        y1.suggestedMin = 0;
        y1.suggestedMax = Math.ceil((rightMax || 1) * 1.2);
      }
    }
    } catch (e) {
      // Recreate chart on any failure
      recreateChart(state.chart?.data?.labels || [], series);
    }
  }

  function normalizeArray(arr) {
    if (!Array.isArray(arr) || arr.length === 0) return [];
    const nums = arr.filter(v => typeof v === 'number');
    if (!nums.length) return arr.map(() => null);
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    const range = max - min;
    if (range === 0) {
      // All equal; map non-null values to 50 so the line is visible and aligned
      return arr.map(v => (v == null ? null : 50));
    }
    return arr.map(v => (v == null ? null : ((v - min) / range) * 100));
  }

  function fetchChart(type, opts = {}) {
    // Map UI range to backend params
    const range = state.trendsRange || 'latest';
    const rangeToDays = (r) => r === '1w' ? 7 : r === '1m' ? 30 : r === '1y' ? 365 : null;
    const days = rangeToDays(range);
    // Build URL: use limit for 'latest', use days otherwise
    let url = `/api/chart-data/?type=${encodeURIComponent(type)}&ts=${Date.now()}`;
    if (days) {
      url += `&days=${days}`;
    } else {
      url += `&limit=10`;
    }
    const includeMunicipality = opts.includeMunicipality !== false;
    if (includeMunicipality && state.municipalityId) url += `&municipality_id=${state.municipalityId}`;
    const includeBarangay = opts.includeBarangay !== false;
    if (includeBarangay && state.barangayId) url += `&barangay_id=${state.barangayId}`;
    try { console.debug('[Trends] GET', url); } catch(e) {}

    const doFetch = (u) => fetch(u, { headers: { 'Accept': 'application/json' }})
      .then(r => {
        if (!r.ok) {
          const err = new Error(`chart-data HTTP ${r.status}`);
          err.status = r.status; err.url = u;
          throw err;
        }
        return r.json();
      })
      .then(d => {
        // Some endpoints provide labels_manila only. Fallback to that when labels are empty.
        let labels = Array.isArray(d.labels) ? d.labels.slice() : [];
        const labelsManila = Array.isArray(d.labels_manila) ? d.labels_manila.slice() : [];
        if (!labels.length && labelsManila.length) labels = labelsManila.slice();
        let values = Array.isArray(d.values) ? d.values.slice() : [];
        // Coerce to numbers; keep nulls for non-numeric entries
        values = values.map(v => {
          const n = typeof v === 'number' ? v : parseFloat(v);
          return Number.isFinite(n) ? n : null;
        });
        // Ensure labels and values have the same length
        const n = Math.min(labels.length, values.length);
        return { labels: labels.slice(0, n), labelsManila: labelsManila.slice(0, Math.min(labelsManila.length, n)), values: values.slice(0, n) };
      });

    // First attempt with the chosen strategy; if it yields no data and we used limit, retry with days=1 as a fallback
    return doFetch(url)
      .then(result => {
        if ((!result.labels || result.labels.length === 0) && !days) {
          // Retry with a simple 1-day window which the backend also supports
          const retryUrl = url.replace(/&limit=10/, '') + '&days=1';
          try { console.debug('[Trends] retrying with days=1', retryUrl); } catch(e) {}
          return doFetch(retryUrl);
        }
        return result;
      })
      .catch(err => {
        try { console.warn('[Trends] chart-data fetch failed:', err && err.message ? err.message : err); } catch(e) {}
        return { labels: [], labelsManila: [], values: [] };
      });
  }

  function mergeSeries(arr) {
    const labelSet = new Set();
    arr.forEach(s => (s.labels || []).forEach(l => labelSet.add(l)));
    const labels = Array.from(labelSet).sort((a,b) => new Date(a) - new Date(b));
    const series = {};
    arr.forEach(s => {
      const map = new Map();
      (s.labels || []).forEach((l, i) => map.set(l, s.values[i]));
      series[s.key] = labels.map(l => (map.has(l) ? map.get(l) : null));
    });
    return { labels, series };
  }

  // ---------------- Utils ----------------
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Fullscreen helpers for Flood Risk Map
  function addFullscreenControl(map, containerId) {
    if (!window.L || !map) return;
    // Inject minimal styles once
    if (!document.getElementById('flood-fullscreen-style')) {
      const css = `
      .leaflet-control-fullscreen a{background:#fff;border:1px solid #dcdcdc;border-radius:4px;display:inline-block;width:28px;height:28px;line-height:28px;text-align:center;font-size:16px;color:#333;box-shadow:0 1px 3px rgba(0,0,0,.2);}
      .leaflet-control-fullscreen a:hover{background:#f5f5f5}
      `;
      const st = document.createElement('style');
      st.id = 'flood-fullscreen-style';
      st.textContent = css;
      document.head.appendChild(st);
    }

    const FullC = L.Control.extend({
      options: { position: 'topleft' },
      onAdd: function() {
        const c = L.DomUtil.create('div', 'leaflet-control leaflet-control-fullscreen');
        const a = L.DomUtil.create('a', '', c);
        a.href = '#'; a.title = 'Toggle full screen'; a.innerHTML = '⤢';
        L.DomEvent.on(a, 'click', L.DomEvent.stop)
          .on(a, 'click', () => toggleMapFullscreen(containerId, map));
        return c;
      },
      onRemove: function() {}
    });
    map.addControl(new FullC());
  }

  function toggleMapFullscreen(containerId, map) {
    const el = document.getElementById(containerId);
    if (!el) return;
    const isFs = el.dataset.fullscreen === '1';
    if (!isFs) {
      // Enter fullscreen-like mode via fixed positioning
      el.dataset.fullscreen = '1';
      el.dataset.prevStyle = el.getAttribute('style') || '';
      el.style.position = 'fixed';
      el.style.top = '0';
      el.style.left = '0';
      el.style.width = '100vw';
      el.style.height = '100vh';
      el.style.zIndex = '10000';
      el.style.background = '#fff';
    } else {
      // Exit fullscreen
      el.dataset.fullscreen = '0';
      const prev = el.dataset.prevStyle || '';
      if (prev) el.setAttribute('style', prev); else el.removeAttribute('style');
    }
    setTimeout(() => map && map.invalidateSize(true), 60);
  }

  // Formatters for Manila-localized labels
  function formatManilaShort(iso) {
    try {
      if (!iso) return '';
      const d = new Date(iso);
      // Short: HH:mm in Asia/Manila
      return d.toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Manila' });
    } catch (e) { return iso; }
  }
  function formatManilaFull(iso) {
    try {
      if (!iso) return '';
      const d = new Date(iso);
      // Full: e.g., 21 Sep 2025, 13:45 Manila Time
      const date = d.toLocaleDateString('en-PH', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Asia/Manila' });
      const time = d.toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Manila' });
      return `${date} ${time}`;
    } catch (e) { return iso; }
  }

  // Severity and label helpers
  function severityName(level) {
    const levels = {1:'ADVISORY',2:'WATCH',3:'WARNING',4:'EMERGENCY',5:'CATASTROPHIC'};
    return levels[level] || 'ALERT';
  }
  function paramLabel(key) {
    const map = { rainfall: 'Rainfall', water_level: 'Water Level', temperature: 'Temperature', humidity: 'Humidity', wind_speed: 'Wind Speed' };
    return map[key] || (key ? (key.charAt(0).toUpperCase() + key.slice(1)) : 'Parameter');
  }
})();
