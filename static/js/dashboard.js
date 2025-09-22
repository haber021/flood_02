/**
 * Dashboard.js - Main dashboard functionality
 * Handles real-time data updates for sensor widgets, alerts, and dashboard refresh
 */

// Dashboard refresh interval in milliseconds (5 minutes)
const DASHBOARD_REFRESH_INTERVAL = 5 * 60 * 1000;

// Cache for threshold settings by parameter
let THRESHOLDS_MAP = null; // { parameter: {advisory, watch, warning, emergency, catastrophic, unit} }

// Load threshold settings from API and cache them
async function loadThresholds() {
    try {
        const resp = await fetch('/api/threshold-settings/', {
            headers: { 'Accept': 'application/json' }
        });
        const data = await resp.json();
        const list = Array.isArray(data) ? data : (data.results || []);
        const map = {};
        list.forEach(t => {
            map[t.parameter] = {
                advisory: t.advisory_threshold,
                watch: t.watch_threshold,
                warning: t.warning_threshold,
                emergency: t.emergency_threshold,
                catastrophic: t.catastrophic_threshold,
                unit: t.unit
            };
        });
        THRESHOLDS_MAP = map;
        console.log('[Dashboard] Threshold settings loaded');
    } catch (e) {
        console.warn('[Dashboard] Failed to load thresholds. Falling back to static gauge colors.', e);
        THRESHOLDS_MAP = null;
    }
}

// Dashboard initialization
document.addEventListener('DOMContentLoaded', function() {
    // Load thresholds first (do not block UI if it fails)
    loadThresholds();
    // Refresh thresholds periodically (every 10 minutes)
    setInterval(loadThresholds, 10 * 60 * 1000);
    // Initialize sensor gauges
    initializeGauges();
    
    // Load initial sensor data
    console.log('Starting to update sensor data...');
    try {
        updateSensorData();
        console.log('Sensor data update completed successfully');
    } catch (e) {
        console.error('Error updating sensor data:', e);
    }
    
    // Check for active alerts
    checkActiveAlerts();
    
    // Update data periodically
    setInterval(updateSensorData, 60000); // Update every minute
    setInterval(checkActiveAlerts, 30000); // Check alerts every 30 seconds
    
    // Check regularly if location has changed
    setInterval(checkLocationChange, 1000); // Check location change flag every second
    
    // Auto-refresh dashboard
    setInterval(function() {
        // Don't refresh if user is interacting with form elements
        if (!document.activeElement || 
            !['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(document.activeElement.tagName)) {
            location.reload();
        }
    }, DASHBOARD_REFRESH_INTERVAL);
});

/**
 * Initialize gauge visualizations
 */
function initializeGauges() {
    // Set up empty gauges
    updateGauge('temperature-gauge', 0, '°C', '#temp-updated');
    updateGauge('humidity-gauge', 0, '%', '#humidity-updated');
    updateGauge('rainfall-gauge', 0, 'mm', '#rainfall-updated');
    updateGauge('water-level-gauge', 0, 'm', '#water-level-updated');
    updateGauge('wind-speed-gauge', 0, 'km/h', '#wind-speed-updated');
}

/**
 * Update sensor data for all gauges and stats
 */
function updateSensorData() {
    // No longer checking for login status since API endpoints don't require authentication
    
    // Construct the URL with location parameters
    let url = '/api/sensor-data/?limit=5';
    
    // Add location parameters if available
    if (window.selectedMunicipality) {
        url += `&municipality_id=${window.selectedMunicipality.id}`;
        console.log(`[Sensor Data] Adding municipality filter: ${window.selectedMunicipality.name}`);
    }
    
    console.log(`[Sensor Data] Fetching sensor data with URL: ${url}`);
    
    if (window.selectedBarangay) {
        url += `&barangay_id=${window.selectedBarangay.id}`;
        console.log(`[Sensor Data] Adding barangay filter: ${window.selectedBarangay.name}`);
    }
    
    console.log(`[Sensor Data] Fetching latest readings with URL: ${url}`);
    
    // Fetch the latest sensor data with location filters (no authentication required)
    fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
        }
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (!data.results || data.results.length === 0) {
                console.warn('No sensor data available with location filters');
                
                // If no data with location filters, try getting global sensor data
                if (window.selectedMunicipality && !window.isRetrySensorFetch) {
                    console.log('Retrying sensor data fetch without municipality filter as fallback');
                    window.isRetrySensorFetch = true;
                    
                    // Fetch global data (without location filters)
                    fetch('/api/sensor-data/?limit=5', {
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'Accept': 'application/json'
                        }
                    })
                        .then(response => {
                            if (!response.ok) {
                                throw new Error(`HTTP error! Status: ${response.status}`);
                            }
                            return response.json();
                        })
                        .then(globalData => {
                            window.isRetrySensorFetch = false;
                            
                            if (!globalData.results || globalData.results.length === 0) {
                                console.warn('No global sensor data available');
                                
                                // Update gauges to show no data
                                ['temperature-gauge', 'humidity-gauge', 'rainfall-gauge', 'water-level-gauge', 'wind-speed-gauge'].forEach(gaugeId => {
                                    updateGauge(gaugeId, null, '', `#${gaugeId.split('-')[0]}-updated`, null);
                                });
                                
                                return;
                            }
                            
                            console.log('Using global sensor data as fallback');
                            // Use the global data instead
                            updateGaugesWithData(globalData.results);
                        })
                        .catch(error => {
                            window.isRetrySensorFetch = false;
                            console.error('Error fetching global sensor data:', error);
                            
                            // Update gauges to show error
                            ['temperature-gauge', 'humidity-gauge', 'rainfall-gauge', 'water-level-gauge', 'wind-speed-gauge'].forEach(gaugeId => {
                                updateGauge(gaugeId, null, '', `#${gaugeId.split('-')[0]}-updated`, null);
                            });
                        });
                } else {
                    // No data and no retry, update gauges to show no data
                    ['temperature-gauge', 'humidity-gauge', 'rainfall-gauge', 'water-level-gauge', 'wind-speed-gauge'].forEach(gaugeId => {
                        updateGauge(gaugeId, null, '', `#${gaugeId.split('-')[0]}-updated`, null);
                    });
                }
                return;
            }
            
            // Process received data
            console.log('[Sensor Data] Received data:', data.results);
            updateGaugesWithData(data.results);
        })
        .catch(error => {
            // Check if map-last-updated element exists before trying to update it
            const lastUpdatedElement = document.getElementById('map-last-updated');
            if (lastUpdatedElement) {
                lastUpdatedElement.textContent = 'Data unavailable';
            }
            
            // Update gauges to show error
            ['temperature-gauge', 'humidity-gauge', 'rainfall-gauge', 'water-level-gauge', 'wind-speed-gauge'].forEach(gaugeId => {
                updateGauge(gaugeId, null, '', `#${gaugeId.split('-')[0]}-updated`, null);
            });
            
            // Log the error but don't display the empty object in the console
            console.error('Error fetching sensor data:', error.message || 'Network or server error');
        });
}

/**
 * Process sensor readings and update gauge displays
 */
function updateGaugesWithData(readings) {
    if (!readings || readings.length === 0) {
        console.warn('No readings provided to updateGaugesWithData');
        return;
    }
    
    // Process each sensor type
    readings.forEach(reading => {
        const sensorType = reading.sensor_type;
        const value = reading.value;
        const timestamp = new Date(reading.timestamp);
        
        console.log(`[Sensor Data] Processing ${sensorType} reading with value ${value}`);
        
        // Update appropriate gauge based on sensor type
        switch(sensorType) {
            case 'temperature':
                console.log(`[Sensor Data] Updating temperature gauge with value ${value}°C`);
                updateGauge('temperature-gauge', value, '°C', '#temp-updated', timestamp);
                break;
            case 'humidity':
                console.log(`[Sensor Data] Updating humidity gauge with value ${value}%`);
                updateGauge('humidity-gauge', value, '%', '#humidity-updated', timestamp);
                break;
            case 'rainfall':
                console.log(`[Sensor Data] Updating rainfall gauge with value ${value}mm`);
                updateGauge('rainfall-gauge', value, 'mm', '#rainfall-updated', timestamp);
                break;
            case 'water_level':
                console.log(`[Sensor Data] Updating water level gauge with value ${value}m`);
                updateGauge('water-level-gauge', value, 'm', '#water-level-updated', timestamp);
                break;
            case 'wind_speed':
                console.log(`[Sensor Data] Updating wind speed gauge with value ${value}km/h`);
                updateGauge('wind-speed-gauge', value, 'km/h', '#wind-speed-updated', timestamp);
                break;
        }
    });
    
    // Update map last updated timestamp
    document.getElementById('map-last-updated').textContent = new Date().toLocaleString();
}

/**
 * Update a gauge with new value
 */
function updateGauge(gaugeId, value, unit, timestampElementId, timestamp = null) {
    console.log(`[Gauge] Updating gauge ${gaugeId} with value ${value}${unit}`);
    const gaugeElement = document.getElementById(gaugeId);
    if (!gaugeElement) {
        console.error(`[Gauge] Could not find gauge element with ID ${gaugeId}`);
        return;
    }
    
    // Update the gauge value
    const valueElement = gaugeElement.querySelector('.gauge-value');
    if (valueElement) {
        // Format value to 1 decimal place unless it's null/undefined
        if (value !== null && value !== undefined && !isNaN(value)) {
            console.log(`[Gauge] Setting ${gaugeId} value to ${value.toFixed(1)}${unit}`);
            valueElement.textContent = value.toFixed(1);
            // Change gauge color based on value if appropriate
            updateGaugeColor(gaugeId, value);
        } else {
            console.warn(`[Gauge] Setting ${gaugeId} to '--' (null/undefined/NaN value)`);
            valueElement.textContent = '--';
        }
    } else {
        console.error(`[Gauge] Could not find .gauge-value element within ${gaugeId}`);
    }
    
    // Update the timestamp if provided
    if (timestampElementId) {
        const timestampElement = document.querySelector(timestampElementId);
        if (timestampElement) {
            if (timestamp) {
                timestampElement.textContent = 'Last updated: ' + timestamp.toLocaleString();
            } else {
                timestampElement.textContent = 'Last updated: unavailable';
            }
        }
    }
}

/**
 * Update gauge color based on value and thresholds
 */
function updateGaugeColor(gaugeId, value) {
    // Map gaugeId to parameter name used server-side
    const paramByGauge = {
        'temperature-gauge': 'temperature',
        'humidity-gauge': 'humidity',
        'rainfall-gauge': 'rainfall',
        'water-level-gauge': 'water_level',
        'wind-speed-gauge': 'wind_speed'
    };

    const gauge = document.getElementById(gaugeId);
    if (!gauge) return;

    // Remove any previous classes
    gauge.classList.remove('gauge-normal', 'gauge-advisory', 'gauge-watch', 'gauge-warning', 'gauge-emergency', 'gauge-danger');

    // If thresholds are not loaded or value invalid, default to normal
    if (!THRESHOLDS_MAP || value === null || value === undefined || isNaN(value)) {
        gauge.classList.add('gauge-normal');
        gauge.style.setProperty('--gauge-color', '#198754'); // green
        return;
    }

    const param = paramByGauge[gaugeId];
    const t = THRESHOLDS_MAP[param];
    if (!t) {
        gauge.classList.add('gauge-normal');
        gauge.style.setProperty('--gauge-color', '#198754');
        return;
    }

    // Compute severity (0..5)
    let level = 0;
    if (value >= t.catastrophic) level = 5;
    else if (value >= t.emergency) level = 4;
    else if (value >= t.warning) level = 3;
    else if (value >= t.watch) level = 2;
    else if (value >= t.advisory) level = 1;

    // Choose color per level
    const colorByLevel = {
        0: '#198754', // green normal
        1: '#0dcaf0', // info
        2: '#0dcaf0', // info (watch)
        3: '#ffc107', // warning
        4: '#dc3545', // danger
        5: '#dc3545'  // danger
    };
    const classByLevel = {
        0: 'gauge-normal',
        1: 'gauge-advisory',
        2: 'gauge-watch',
        3: 'gauge-warning',
        4: 'gauge-emergency',
        5: 'gauge-danger'
    };

    gauge.classList.add(classByLevel[level]);
    gauge.style.setProperty('--gauge-color', colorByLevel[level]);
}

/**
 * Check for active alerts and update the dashboard
 */
function checkActiveAlerts() {
    // Construct the URL with location parameters
    let url = '/api/flood-alerts/?active=true';
    
    // Add location parameters if available
    if (window.selectedMunicipality) {
        url += `&municipality_id=${window.selectedMunicipality.id}`;
        console.log(`[Alerts] Adding municipality filter: ${window.selectedMunicipality.name}`);
    }
    
    if (window.selectedBarangay) {
        url += `&barangay_id=${window.selectedBarangay.id}`;
        console.log(`[Alerts] Adding barangay filter: ${window.selectedBarangay.name}`);
    }
    
    console.log(`[Alerts] Fetching alerts with URL: ${url}`);
    
    fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
        }
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // If no results with municipality filter, try getting global data
            if ((!data.results || data.results.length === 0) && 
                window.selectedMunicipality && 
                !window.isRetryAlertsFetch) {
                console.log('No alerts found with location filters, trying global alerts as fallback');
                window.isRetryAlertsFetch = true;
                
                // Fetch global alerts (without location filters)
                fetch('/api/flood-alerts/?active=true', {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }
                })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! Status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(globalData => {
                        window.isRetryAlertsFetch = false;
                        processAlertsData(globalData);
                    })
                    .catch(error => {
                        window.isRetryAlertsFetch = false;
                        console.error('Error fetching global alerts:', error);
                    });
                return;
            }
            
            // Process the alerts data
            processAlertsData(data);
        })
        .catch(error => {
            console.error('Error checking alerts:', error);
            
            // Update alert status to normal as a fallback
            if (typeof updateAlertStatus === 'function') {
                updateAlertStatus(null);
            }
        });
}

/**
 * Process alerts data and update UI
 */
function processAlertsData(data) {
    const alertsContainer = document.getElementById('alerts-list');
    const noAlertsElement = document.getElementById('no-alerts');
    
    // Affected barangays elements
    const affectedBarangaysContainer = document.getElementById('affected-barangays-list');
    const noAffectedBarangaysElement = document.getElementById('no-affected-barangays');
    
    if (data.results && data.results.length > 0) {
        // We have active alerts
        alertsContainer.classList.remove('d-none');
        if (noAlertsElement) {
            noAlertsElement.classList.add('d-none');
        }
        
        // Sort alerts by severity (highest first)
        const alerts = data.results.sort((a, b) => b.severity_level - a.severity_level);
        
        // Update alerts list
        let alertsHtml = '';
        let affectedBarangaysSet = new Set(); // Track unique affected barangays
        
        // Map to store barangay details for later use
        let barangayDetails = {};
        
        alerts.forEach(alert => {
            // Determine alert color based on severity
            let alertClass = 'alert-info';
            let severityText = 'Advisory';
            
            switch (alert.severity_level) {
                case 5:
                    alertClass = 'alert-danger';
                    severityText = 'CATASTROPHIC';
                    break;
                case 4:
                    alertClass = 'alert-danger';
                    severityText = 'EMERGENCY';
                    break;
                case 3:
                    alertClass = 'alert-warning';
                    severityText = 'WARNING';
                    break;
                case 2:
                    alertClass = 'alert-warning';
                    severityText = 'WATCH';
                    break;
                case 1:
                    alertClass = 'alert-info';
                    severityText = 'ADVISORY';
                    break;
            }
            
            // Format the date
            const issuedDate = new Date(alert.issued_at).toLocaleString();
            
            // Add affected barangays to set and store alert severity
            if (alert.affected_barangays && alert.affected_barangays.length > 0) {
                alert.affected_barangays.forEach(barangayId => {
                    affectedBarangaysSet.add(barangayId);
                    
                    // Keep track of highest severity for this barangay
                    if (!barangayDetails[barangayId] || 
                        alert.severity_level > barangayDetails[barangayId].severity_level) {
                        barangayDetails[barangayId] = {
                            severity_level: alert.severity_level,
                            alert_title: alert.title,
                            severity_text: severityText,
                            alert_class: alertClass
                        };
                    }
                });
            }
            
            // Build the HTML for this alert
            alertsHtml += `
                <div class="alert ${alertClass} mb-3">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h5 class="alert-heading">${severityText}: ${alert.title}</h5>
                            <p>${alert.description}</p>
                            <div class="small text-muted mt-2">
                                Issued: ${issuedDate} by ${alert.issued_by_username || 'System'}
                            </div>
                        </div>
                        <div>
                            ${alert.predicted_flood_time ? `
                                <div class="text-center">
                                    <div class="fw-bold">Predicted Impact</div>
                                    <div class="countdown-timer" data-target="${new Date(alert.predicted_flood_time).getTime()}">
                                        Loading...
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        });
        
        // Update the alerts container
        alertsContainer.innerHTML = alertsHtml;
        
        // Initialize countdown timers
        document.querySelectorAll('.countdown-timer').forEach(timer => {
            const targetTime = parseInt(timer.getAttribute('data-target'));
            updateCountdown(timer, targetTime);
            setInterval(() => updateCountdown(timer, targetTime), 1000);
        });
        
        // Now handle the affected barangays section
        if (affectedBarangaysSet.size > 0) {
            // We have affected barangays
            if (affectedBarangaysContainer) {
                affectedBarangaysContainer.classList.remove('d-none');
            }
            if (noAffectedBarangaysElement) {
                noAffectedBarangaysElement.classList.add('d-none');
            }
            
            // Construct the URL with location parameters
            let barangayUrl = '/api/barangays/';
            
            // Add location parameters if available
            if (window.selectedMunicipality) {
                barangayUrl += `?municipality_id=${window.selectedMunicipality.id}`;
                console.log(`[Barangays] Adding municipality filter: ${window.selectedMunicipality.name}`);
            }
            
            console.log(`[Barangays] Fetching barangay data with URL: ${barangayUrl}`);
            
            // Fetch barangay details
            fetch(barangayUrl, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(barangayData => {
                    if (barangayData.results && barangayData.results.length > 0) {
                        const barangays = barangayData.results;
                        let barangayCardsHtml = '';
                        
                        // Filter to affected barangays and create cards
                        barangays.forEach(barangay => {
                            if (affectedBarangaysSet.has(barangay.id)) {
                                const details = barangayDetails[barangay.id];
                                
                                barangayCardsHtml += `
                                    <div class="col">
                                        <div class="card h-100">
                                            <div class="card-header ${details.alert_class} text-white">
                                                <h5 class="mb-0">${barangay.name}</h5>
                                            </div>
                                            <div class="card-body">
                                                <p><strong>Alert Level:</strong> ${details.severity_text}</p>
                                                <p><strong>Alert:</strong> ${details.alert_title}</p>
                                                <p><strong>Population:</strong> ${barangay.population.toLocaleString()}</p>
                                                <p><strong>Contact:</strong> ${barangay.contact_person || 'N/A'}</p>
                                                <p><strong>Phone:</strong> ${barangay.contact_number || 'N/A'}</p>
                                            </div>
                                            <div class="card-footer text-center">
                                                <button class="btn btn-sm btn-outline-primary" onclick="highlightBarangay(${barangay.id})">
                                                    <i class="fas fa-map-marker-alt me-1"></i> Show on Map
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                `;
                            }
                        });
                        
                        // Update the barangay cards container
                        document.getElementById('barangay-cards').innerHTML = barangayCardsHtml;
                    }
                })
                .catch(error => {
                    // Log the error but don't display the empty object in the console
                    console.error('Error fetching barangay data:', error.message || 'Network or server error');
                    
                    // Show a message in the affected barangays container
                    if (affectedBarangaysContainer) {
                        affectedBarangaysContainer.innerHTML = `
                            <div class="alert alert-secondary">
                                <i class="fas fa-exclamation-circle me-2"></i>
                                Unable to load barangay details at this time.
                            </div>
                        `;
                    }
                });
            
        } else {
            // No affected barangays
            if (affectedBarangaysContainer) {
                affectedBarangaysContainer.classList.add('d-none');
            }
            if (noAffectedBarangaysElement) {
                noAffectedBarangaysElement.classList.remove('d-none');
            }
        }
        
        // Update alert status display
        updateAlertStatus(alerts[0]);
    } else {
        // No active alerts
        if (alertsContainer) {
            alertsContainer.classList.add('d-none');
        }
        if (noAlertsElement) {
            noAlertsElement.classList.remove('d-none');
        }
        
        // Also clear affected barangays section
        if (affectedBarangaysContainer) {
            affectedBarangaysContainer.classList.add('d-none');
        }
        if (noAffectedBarangaysElement) {
            noAffectedBarangaysElement.classList.remove('d-none');
        }
        
        // Update alert status to normal
        updateAlertStatus(null);
    }
    })
    .catch(error => {
        // Check if containers exist before trying to update them
        const alertsContainer = document.getElementById('alerts-list');
        const noAlertsElement = document.getElementById('no-alerts');
        
        // If alert elements exist, show no alerts message
        if (alertsContainer && noAlertsElement) {
            alertsContainer.classList.add('d-none');
            noAlertsElement.classList.remove('d-none');
            noAlertsElement.innerHTML = '<div class="alert alert-secondary">Unable to load alerts at this time.</div>';
        }
        
        // Log the error but don't display the empty object in the console
        console.error('Error checking alerts:', error.message || 'Network or server error');
        
        // Update alert status to normal as a fallback
        if (typeof updateAlertStatus === 'function') {
            updateAlertStatus(null);
        }
    });
}

/**
 * Update the alert status display
 */
function updateAlertStatus(highestAlert) {
    const statusIcon = document.getElementById('status-icon');
    const statusText = document.getElementById('status-text');
    const alertsCount = document.getElementById('alerts-count');
    
    if (!highestAlert) {
        // No alerts - normal status
        statusIcon.innerHTML = '<i class="fas fa-check-circle fa-3x text-success"></i>';
        statusText.textContent = 'Normal';
        statusText.className = 'status-text text-success';
        if (alertsCount) alertsCount.textContent = 'No active alerts';
        return;
    }
    
    // Update based on the highest severity alert
    switch (highestAlert.severity_level) {
        case 5:
            statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle fa-3x text-danger"></i>';
            statusText.textContent = 'CATASTROPHIC';
            statusText.className = 'status-text text-danger';
            break;
        case 4:
            statusIcon.innerHTML = '<i class="fas fa-exclamation-triangle fa-3x text-danger"></i>';
            statusText.textContent = 'EMERGENCY';
            statusText.className = 'status-text text-danger';
            break;
        case 3:
            statusIcon.innerHTML = '<i class="fas fa-exclamation-circle fa-3x text-warning"></i>';
            statusText.textContent = 'WARNING';
            statusText.className = 'status-text text-warning';
            break;
        case 2:
            statusIcon.innerHTML = '<i class="fas fa-exclamation-circle fa-3x text-warning"></i>';
            statusText.textContent = 'WATCH';
            statusText.className = 'status-text text-warning';
            break;
        case 1:
            statusIcon.innerHTML = '<i class="fas fa-info-circle fa-3x text-info"></i>';
            statusText.textContent = 'ADVISORY';
            statusText.className = 'status-text text-info';
            break;
    }
    
    // Update alerts count text
    if (alertsCount) {
        // Construct the URL with location parameters
        let alertCountUrl = '/api/flood-alerts/?active=true';
        
        // Add location parameters if available
        if (window.selectedMunicipality) {
            alertCountUrl += `&municipality_id=${window.selectedMunicipality.id}`;
        }
        
        if (window.selectedBarangay) {
            alertCountUrl += `&barangay_id=${window.selectedBarangay.id}`;
        }
        
        fetch(alertCountUrl, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                const count = data.count || 0;
                alertsCount.textContent = `${count} active alert${count !== 1 ? 's' : ''}`;
            });
    }
}

/**
 * Update countdown timer display
 */
function updateCountdown(element, targetTime) {
    const now = new Date().getTime();
    const distance = targetTime - now;
    
    if (distance < 0) {
        element.innerHTML = '<span class="badge bg-danger">IMMINENT</span>';
        return;
    }
    
    // Calculate hours, minutes, seconds
    const hours = Math.floor(distance / (1000 * 60 * 60));
    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((distance % (1000 * 60)) / 1000);
    
    // Display countdown
    element.innerHTML = `
        <div class="badge bg-danger">
            ${hours}h ${minutes}m ${seconds}s
        </div>
    `;
}

/**
 * Check if the location has changed and update data if needed
 */
function checkLocationChange() {
    // Check for global location change flag
    if (window.locationChanged) {
        console.log('Location change detected in dashboard.js');
        // Update sensor data
        updateSensorData();
        // Update alerts
        checkActiveAlerts();
        // Update charts if applicable
        if (typeof updateAllCharts === 'function') {
            updateAllCharts();
        }
    }
}

/**
 * Highlight a barangay on the map when selected from the affected barangays list
 */
function highlightBarangay(barangayId) {
    // Select the barangay in the dropdown
    const barangaySelector = document.getElementById('barangay-selector');
    if (barangaySelector) {
        barangaySelector.value = barangayId;
        
        // Trigger the change event to update the map
        const event = new Event('change');
        barangaySelector.dispatchEvent(event);
        
        // Enable and click the focus button
        const focusButton = document.getElementById('focus-selected-barangay');
        if (focusButton) {
            focusButton.disabled = false;
            focusButton.click();
        }
    }
    
    // Scroll to the map section
    document.getElementById('flood-map').scrollIntoView({ behavior: 'smooth' });
}
