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
  };
  const barangayLayerById = new Map();

  document.addEventListener('DOMContentLoaded', () => {
    setupLocationSelector();
    initChart();
    initMap();
    bindApplyThresholdsButton();
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
          state.chart.update();
        } else {
          // Fallback: reload
          loadTrendsChart();
        }
      });
    }

    // Initial loads
    refreshAll();

    // Periodic refreshes
    setInterval(updateSensorValues, 60 * 1000);
    setInterval(updateAlerts, 30 * 1000);
    setInterval(updateMapData, 3 * 60 * 1000);
    // Auto-refresh trends chart every 15s
    setInterval(loadTrendsChart, 15 * 1000);

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

  function refreshAll() {
    updateSensorValues();
    updateAlerts();
    updateMapData();
    loadTrendsChart();
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
              refreshAll();
              applyThresholdsNow();
            } else {
              refreshAll();
              applyThresholdsNow();
            }
          });
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
    let url = '/api/flood-alerts/?active=true';
    if (state.municipalityId) url += `&municipality_id=${state.municipalityId}`;
    if (state.barangayId) url += `&barangay_id=${state.barangayId}`;

    fetch(url, { headers: { 'Accept': 'application/json' }})
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(async data => {
        const results = (data.results || []).sort((a,b) => b.severity_level - a.severity_level);
        let highest = results[0] || null;
        const badge = document.getElementById('alert-status-badge');
        const title = document.getElementById('alert-title');
        const msg = document.getElementById('alert-message');
        if (!badge || !title || !msg) return;

        // Always compute threshold-based severity for context
        const sev = await fetchThresholdSeverity();
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

        // Title and detailed message
        if (highest && (highest.severity_level || 0) >= thresholdLevel) {
          // Prioritize active alert title/descriptions
          title.textContent = `${levels[highest.severity_level] || 'ALERT'}: ${highest.title}`;
          const lines = [];
          if (highest.description) lines.push(escapeHtml(highest.description));
          // Add threshold context if any parameter breached
          if (sev && Array.isArray(sev.items) && sev.items.some(it => (it.level||0) > 0)) {
            lines.push('<strong>Threshold details:</strong>');
            lines.push(...sev.items
              .filter(it => (it.level || 0) > 0)
              .map(it => {
                const lbl = paramLabel(it.parameter);
                const unit = it.unit || '';
                const thr = it.thresholds || {};
                const thrMap = {1: thr.advisory, 2: thr.watch, 3: thr.warning, 4: thr.emergency, 5: thr.catastrophic};
                const ref = thrMap[it.level] != null ? thrMap[it.level] : '';
                const latest = (it.latest != null) ? Number(it.latest).toFixed(unit === '%' ? 0 : 2).replace(/\.00$/,'') : '—';
                const refText = ref !== '' ? Number(ref).toFixed(2).replace(/\.00$/,'') : '—';
                return `${lbl}: ${latest} ${unit} exceeds ${severityName(it.level)} threshold (${refText} ${unit})`;
              }));
          }
          // Append per-parameter status (all params)
          if (sev) lines.push(buildParameterStatusHTML(sev));
          msg.innerHTML = lines.length ? lines.join('<br>') : 'Active alert in effect.';
          updateAffectedAreas(highest.affected_barangays || []);
        } else if (thresholdLevel > 0 && sev) {
          // Threshold-driven status only
          const text = severityName(thresholdLevel);
          const top = (sev.items || []).sort((a,b)=>b.level-a.level)[0];
          const topLabel = top ? paramLabel(top.parameter) : 'Threshold';
          title.textContent = `${text}: ${topLabel}`;
          const lines = (sev.items || [])
            .filter(it => (it.level || 0) > 0)
            .map(it => {
              const lbl = paramLabel(it.parameter);
              const unit = it.unit || '';
              const thr = it.thresholds || {};
              const thrMap = {1: thr.advisory, 2: thr.watch, 3: thr.warning, 4: thr.emergency, 5: thr.catastrophic};
              const ref = thrMap[it.level] != null ? thrMap[it.level] : '';
              const latest = (it.latest != null) ? Number(it.latest).toFixed(unit === '%' ? 0 : 2).replace(/\.00$/,'') : '—';
              const refText = ref !== '' ? Number(ref).toFixed(2).replace(/\.00$/,'') : '—';
              return `${lbl}: ${latest} ${unit} exceeds ${severityName(it.level)} threshold (${refText} ${unit})`;
            });
          // Append per-parameter status (all params)
          lines.push(buildParameterStatusHTML(sev));
          msg.innerHTML = lines.length ? lines.join('<br>') : 'Computed from configured thresholds and latest readings.';
          updateAffectedAreas([]);
        } else {
          // No alerts and no threshold breach -> Normal
          title.textContent = 'No Active Alerts';
          msg.textContent = 'The system is monitoring environmental conditions continuously.';
          updateAffectedAreas([]);
        }
      })
      .catch(() => {
        // Leave as-is on error
      });
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

    // Add fullscreen control
    addFullscreenControl(state.map, 'flood-map');

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
    // Initial invalidate after render and next tick
    setTimeout(invalidate, 50);
    setTimeout(invalidate, 250);
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
      .then(data => {
        clearMapLayers();
        drawZones(data.zones || []);
        drawSensors(data.sensors || []);
        drawBarangays(data.barangays || []);
        if (lastUpdated) lastUpdated.textContent = new Date().toLocaleString();
        // Ensure map tiles realign after layer updates
        try { state.map && state.map.invalidateSize(true); } catch (e) {}
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
      const radius = 200 + Math.min(800, Math.sqrt(b.population || 1));
      const circle = L.circle([b.lat, b.lng], {
        radius,
        color: '#10b981',
        weight: 1,
        fillColor: '#10b981',
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
    const ctx = canvas.getContext('2d');
    state.chart = new Chart(ctx, {
      type: 'line',
      data: { labels: [], datasets: [
        { label: 'Temperature (°C)', data: [], borderColor: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.08)', cubicInterpolationMode: 'monotone', yAxisID: 'y', pointRadius: 5, pointHoverRadius: 7, borderWidth: 3, fill: false },
        { label: 'Humidity (%)', data: [], borderColor: '#0ea5e9', backgroundColor: 'rgba(14, 165, 233, 0.08)', cubicInterpolationMode: 'monotone', yAxisID: 'y', pointRadius: 5, pointHoverRadius: 7, borderWidth: 3, fill: false },
        { label: 'Rainfall (mm)', data: [], borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.08)', cubicInterpolationMode: 'monotone', yAxisID: 'y1', pointRadius: 5, pointHoverRadius: 7, borderWidth: 3, fill: false },
        { label: 'Water Level (m)', data: [], borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.08)', cubicInterpolationMode: 'monotone', yAxisID: 'y1', pointRadius: 5, pointHoverRadius: 7, borderWidth: 3, fill: false },
        { label: 'Wind Speed (km/h)', data: [], borderColor: '#a855f7', backgroundColor: 'rgba(168, 85, 247, 0.08)', cubicInterpolationMode: 'monotone', yAxisID: 'y1', pointRadius: 5, pointHoverRadius: 7, borderWidth: 3, fill: false },
      ]},
      options: {
        responsive: true,
        maintainAspectRatio: false,
        spanGaps: true,
        interaction: { mode: 'index', intersect: false },
        elements: { line: { tension: 0.4 } },
        animation: { duration: 400, easing: 'easeOutQuart' },
        plugins: {
          legend: { position: 'top', labels: { usePointStyle: true, padding: 16, boxWidth: 14, boxHeight: 8 } },
          tooltip: {
            callbacks: {
              title: items => {
                try {
                  const i = items && items.length ? items[0].dataIndex : 0;
                  const iso = (state.chart && state.chart.__isoLabels) ? state.chart.__isoLabels[i] : (items[0].label || '');
                  return formatManilaFull(iso);
                } catch (e) { return items[0].label || ''; }
              }
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              maxRotation: 0,
              autoSkip: true,
              autoSkipPadding: 10,
              callback: function(value, index, ticks) {
                const step = Math.max(1, Math.ceil(ticks.length / 8));
                return (index % step === 0) ? this.getLabelForValue(value) : '';
              }
            }
          },
          y: { type: 'linear', position: 'left', title: { display: true, text: 'Temperature (°C) / Humidity (%)' }, grid: { color: 'rgba(0,0,0,0.05)' }, suggestedMin: 0 },
          y1: { type: 'linear', position: 'right', title: { display: true, text: 'Rainfall (mm) / Water Level (m) / Wind (km/h)' }, grid: { drawOnChartArea: false }, suggestedMin: 0 }
        }
      }
    });
  }

  function loadTrendsChart() {
    if (!state.chart || state._trendsFetchInFlight) return;
    state._trendsFetchInFlight = true;

    // Loading overlay removed per request

    const queries = [
      fetchChart('temperature'),
      fetchChart('humidity'),
      fetchChart('rainfall'),
      fetchChart('water_level'),
      fetchChart('wind_speed'),
    ];
    Promise.allSettled(queries).then(results => {
      const temp = (results[0].status === 'fulfilled') ? results[0].value : { labels: [], values: [] };
      const hum  = (results[1].status === 'fulfilled') ? results[1].value : { labels: [], values: [] };
      const rain = (results[2].status === 'fulfilled') ? results[2].value : { labels: [], values: [] };
      const water= (results[3].status === 'fulfilled') ? results[3].value : { labels: [], values: [] };
      const wind = (results[4].status === 'fulfilled') ? results[4].value : { labels: [], values: [] };

      const merged = mergeSeries([
        { labels: temp.labels,  values: temp.values,  key: 't' },
        { labels: hum.labels,   values: hum.values,   key: 'h' },
        { labels: rain.labels,  values: rain.values,  key: 'r' },
        { labels: water.labels, values: water.values, key: 'wl' },
        { labels: wind.labels,  values: wind.values,  key: 'ws' },
      ]);

      // Store the original ISO labels for tooltips, but display compact Manila time on the axis
      state.chart.__isoLabels = merged.labels.slice();
      const displayLabels = merged.labels.map(formatManilaShort);

      state.chart.data.labels = displayLabels;
      // Cache raw series and apply scaling per current toggle
      state._rawSeries = merged.series;
      applyChartScaling(merged.series);
      state.chart.update();

      // Ensure any previous overlay is hidden
      clearChartOverlay();
    }).finally(() => { state._trendsFetchInFlight = false; });
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

  // Apply scaling based on state.normalize. When true, normalize each series to 0–100 keeping nulls intact.
  function applyChartScaling(series) {
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
      y.title = y.title || {}; y.title.display = true; y.title.text = 'Normalized (%)';
      y.suggestedMin = 0; y.suggestedMax = 100;
      // Hide right axis when normalized
      if (y1) y1.display = false;
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
        y.suggestedMin = Math.floor(Math.min(0, min - 1));
        y.suggestedMax = Math.ceil(max + 1);
      } else {
        y.suggestedMin = 0;
        y.suggestedMax = 100;
      }
      if (y1) {
        const rightAll = [
          rVals.length ? Math.max(...rVals) : 0,
          wlVals.length ? Math.max(...wlVals) : 0,
          wsVals.length ? Math.max(...wsVals) : 0,
        ];
        const rightMax = Math.max(...rightAll);
        y1.display = true;
        y1.suggestedMin = 0;
        y1.suggestedMax = Math.ceil((rightMax || 1) * 1.2);
        y1.title = y1.title || {}; y1.title.display = true;
        y1.title.text = 'Rainfall (mm) / Water Level (m) / Wind (km/h)';
      }
      // Reset left axis title
      y.title = y.title || {}; y.title.display = true; y.title.text = 'Temperature (°C) / Humidity (%)';
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

  function fetchChart(type) {
    // Request only the latest 10 data points for compact trend visualization
    let url = `/api/chart-data/?type=${encodeURIComponent(type)}&limit=10`;
    if (state.municipalityId) url += `&municipality_id=${state.municipalityId}`;
    if (state.barangayId) url += `&barangay_id=${state.barangayId}`;
    return fetch(url, { headers: { 'Accept': 'application/json' }})
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(d => ({ labels: d.labels || [], labelsManila: d.labels_manila || [], values: d.values || [] }));
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
