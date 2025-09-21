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
  };
  const barangayLayerById = new Map();

  document.addEventListener('DOMContentLoaded', () => {
    setupLocationSelector();
    initChart();
    initMap();

    // Initial loads
    refreshAll();

    // Periodic refreshes
    setInterval(updateSensorValues, 60 * 1000);
    setInterval(updateAlerts, 30 * 1000);
    setInterval(updateMapData, 3 * 60 * 1000);
  });

  function refreshAll() {
    updateSensorValues();
    updateAlerts();
    updateMapData();
    loadTrendsChart();
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
            } else {
              refreshAll();
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
      })
      .catch(() => {
        setValue('temperature-value', null, '°C');
        setValue('humidity-value', null, '%');
        setValue('rainfall-value', null, 'mm');
        setValue('water-level-value', null, 'm');
        setValue('wind-speed-value', null, 'km/h');
      });
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

  // ---------------- Alerts ----------------
  function updateAlerts() {
    let url = '/api/flood-alerts/?active=true';
    if (state.municipalityId) url += `&municipality_id=${state.municipalityId}`;
    if (state.barangayId) url += `&barangay_id=${state.barangayId}`;

    fetch(url, { headers: { 'Accept': 'application/json' }})
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(async data => {
        const results = (data.results || []).sort((a,b) => b.severity_level - a.severity_level);
        let highest = results[0];
        const badge = document.getElementById('alert-status-badge');
        const title = document.getElementById('alert-title');
        const msg = document.getElementById('alert-message');
        if (!badge || !title || !msg) return;

        if (!highest) {
          // Fallback: compute from configured thresholds and latest sensor data
          const sev = await fetchThresholdSeverity();
          if (sev && sev.level > 0) {
            const text = severityName(sev.level);
            badge.textContent = text;
            badge.classList.remove('status-normal','status-warning','status-danger');
            if (sev.level >= 4) badge.classList.add('status-danger');
            else if (sev.level >= 2) badge.classList.add('status-warning');
            else badge.classList.add('status-normal');

            // Title uses the highest offending parameter
            const top = (sev.items || []).sort((a,b)=>b.level-a.level)[0];
            const topLabel = top ? paramLabel(top.parameter) : 'Threshold';
            title.textContent = `${text}: ${topLabel}`;

            // Detailed message per parameter exceeding thresholds
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
            msg.innerHTML = lines.length ? lines.join('<br>') : 'Computed from configured thresholds and latest readings.';
            updateAffectedAreas([]);
            return;
          }

          // No alerts and no threshold breach -> Normal
          badge.textContent = 'Normal';
          badge.classList.remove('status-warning','status-danger');
          badge.classList.add('status-normal');
          title.textContent = 'No Active Alerts';
          msg.textContent = 'The system is monitoring environmental conditions continuously.';
          updateAffectedAreas([]);
          return;
        }
        const levels = {1:'ADVISORY',2:'WATCH',3:'WARNING',4:'EMERGENCY',5:'CATASTROPHIC'};
        title.textContent = `${levels[highest.severity_level] || 'ALERT'}: ${highest.title}`;
        msg.textContent = highest.description || '';
        badge.textContent = levels[highest.severity_level] || 'Alert';
        badge.classList.remove('status-normal','status-warning','status-danger');
        if (highest.severity_level >= 4) badge.classList.add('status-danger');
        else if (highest.severity_level >= 2) badge.classList.add('status-warning');
        else badge.classList.add('status-normal');

        updateAffectedAreas(highest.affected_barangays || []);
      })
      .catch(() => {
        // Leave as-is on error
      });
  }

  async function fetchThresholdSeverity() {
    try {
      const params = [];
      params.push('parameter=rainfall,water_level,temperature,humidity');
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
        { label: 'Temperature (°C)', data: [], borderColor: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.08)', cubicInterpolationMode: 'monotone', yAxisID: 'y', pointRadius: 4, pointHoverRadius: 6, borderWidth: 3, fill: false },
        { label: 'Rainfall (mm)', data: [], borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.08)', cubicInterpolationMode: 'monotone', yAxisID: 'y1', pointRadius: 4, pointHoverRadius: 6, borderWidth: 3, fill: false },
        { label: 'Water Level (m)', data: [], borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.08)', cubicInterpolationMode: 'monotone', yAxisID: 'y1', pointRadius: 4, pointHoverRadius: 6, borderWidth: 3, fill: false },
      ]},
      options: {
        responsive: true,
        maintainAspectRatio: false,
        spanGaps: true,
        interaction: { mode: 'index', intersect: false },
        elements: { line: { tension: 0.4 } },
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
          y: { type: 'linear', position: 'left', title: { display: true, text: 'Temperature (°C)' }, grid: { color: 'rgba(0,0,0,0.05)' } },
          y1: { type: 'linear', position: 'right', title: { display: true, text: 'Rainfall (mm) / Water Level (m)' }, grid: { drawOnChartArea: false } }
        }
      }
    });
  }

  function loadTrendsChart() {
    if (!state.chart) return;

    const queries = [
      fetchChart('temperature'),
      fetchChart('rainfall'),
      fetchChart('water_level'),
    ];
    Promise.allSettled(queries).then(results => {
      const temp = (results[0].status === 'fulfilled') ? results[0].value : { labels: [], values: [] };
      const rain = (results[1].status === 'fulfilled') ? results[1].value : { labels: [], values: [] };
      const water = (results[2].status === 'fulfilled') ? results[2].value : { labels: [], values: [] };

      const merged = mergeSeries([
        { labels: temp.labels, values: temp.values, key: 't' },
        { labels: rain.labels, values: rain.values, key: 'r' },
        { labels: water.labels, values: water.values, key: 'w' },
      ]);

      // Store the original ISO labels for tooltips, but display compact Manila time on the axis
      state.chart.__isoLabels = merged.labels.slice();
      const displayLabels = merged.labels.map(formatManilaShort);

      state.chart.data.labels = displayLabels;
      state.chart.data.datasets[0].data = merged.series.t;
      state.chart.data.datasets[1].data = merged.series.r;
      state.chart.data.datasets[2].data = merged.series.w;

      // Dynamically adjust axis ranges to mirror a smooth, centered layout
      const tVals = (merged.series.t || []).filter(v => v != null);
      const rVals = (merged.series.r || []).filter(v => v != null);
      const wVals = (merged.series.w || []).filter(v => v != null);
      const y = state.chart.options.scales.y;
      const y1 = state.chart.options.scales.y1;
      if (tVals.length) {
        const tMin = Math.min(...tVals), tMax = Math.max(...tVals);
        y.suggestedMin = Math.floor(tMin - 1);
        y.suggestedMax = Math.ceil(tMax + 1);
      }
      const rightMax = Math.max(rVals.length ? Math.max(...rVals) : 0, wVals.length ? Math.max(...wVals) : 0);
      y1.suggestedMin = 0;
      y1.suggestedMax = Math.ceil((rightMax || 1) * 1.2);

      state.chart.update();
    });
  }

  function fetchChart(type) {
    let url = `/api/chart-data/?type=${encodeURIComponent(type)}&days=1`;
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
    const map = { rainfall: 'Rainfall', water_level: 'Water Level', temperature: 'Temperature', humidity: 'Humidity' };
    return map[key] || (key ? (key.charAt(0).toUpperCase() + key.slice(1)) : 'Parameter');
  }
})();
