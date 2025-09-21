/**
 * Localhost Helper Script for Flood Monitoring System
 * 
 * This script helps fix common issues when running the application on localhost.
 * Add this script to your base.html template to ensure proper data loading.
 */

// Execute once the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Localhost helper script initialized');
    
    // Fix for cross-origin issues in localhost
    fixCrossOriginHeaders();
    
    // Fix for API URL paths in localhost
    fixApiUrls();
    
    // Fix for empty gauges
    monitorGauges();
    
    // Fix for map data errors
    retryMapDataIfNeeded();
});

/**
 * Fix cross-origin headers for fetch requests
 */
function fixCrossOriginHeaders() {
    // Store the original fetch function
    const originalFetch = window.fetch;
    
    // Override fetch to add proper headers for localhost
    window.fetch = function(url, options = {}) {
        // Ensure options has headers object
        if (!options.headers) {
            options.headers = {};
        }
        
        // Add headers needed for localhost
        options.headers['X-Requested-With'] = 'XMLHttpRequest';
        options.headers['Accept'] = 'application/json';
        
        // Call the original fetch with our modified options
        return originalFetch(url, options);
    };
    
    console.log('Cross-origin headers fix applied');
}

/**
 * Fix API URLs for localhost environment
 */
function fixApiUrls() {
    // Get the current host (e.g., localhost:8000 or 127.0.0.1:5000)
    const currentHost = window.location.host;
    
    // Extract the port
    const port = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
    
    console.log(`Detected localhost environment: ${currentHost} (port: ${port})`);
    
    // Override XMLHttpRequest.open to fix URLs
    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url, async, user, password) {
        // If URL is relative and starts with '/api', make sure it uses the current host
        if (typeof url === 'string' && url.startsWith('/api')) {
            const absoluteUrl = window.location.protocol + '//' + currentHost + url;
            console.log(`Modified XHR URL from ${url} to ${absoluteUrl}`);
            return originalOpen.call(this, method, absoluteUrl, async, user, password);
        }
        
        return originalOpen.call(this, method, url, async, user, password);
    };
    
    console.log('API URL fix applied for XMLHttpRequest');
}

/**
 * Monitor gauges and retry data loading if they're empty
 */
function monitorGauges() {
    // Wait a bit for the initial data load attempt
    setTimeout(() => {
        const gauges = document.querySelectorAll('.gauge-value');
        let emptyGauges = 0;
        
        // Count empty gauges
        gauges.forEach(gauge => {
            if (gauge.textContent === '--' || gauge.textContent === '' || gauge.textContent === '0 °C') {
                emptyGauges++;
            }
        });
        
        // If most gauges are empty, try to update sensor data
        if (emptyGauges > 2 && window.updateSensorData) {
            console.log(`Found ${emptyGauges} empty gauges, attempting to reload sensor data...`);
            
            // Force direct sensor data update
            if (window.directUpdateSensorData) {
                window.directUpdateSensorData();
            } else {
                // Create a direct update function if it doesn't exist
                window.directUpdateSensorData = function() {
                    // Fetch sensor data directly
                    fetch('/api/sensor-data/?limit=5', {
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'Accept': 'application/json'
                        }
                    })
                    .then(response => response.json())
                    .then(data => {
                        console.log('Direct fetch received data:', data);
                        
                        // Update gauges if we have data
                        if (data.results && data.results.length > 0) {
                            // Find values by sensor type
                            const temperatureData = data.results.find(item => item.sensor_type === 'temperature');
                            const humidityData = data.results.find(item => item.sensor_type === 'humidity');
                            const rainfallData = data.results.find(item => item.sensor_type === 'rainfall');
                            const waterLevelData = data.results.find(item => item.sensor_type === 'water_level');
                            const windSpeedData = data.results.find(item => item.sensor_type === 'wind_speed');
                            
                            // Update each gauge directly
                            if (temperatureData) {
                                updateGaugeDirectly('temperature-gauge', temperatureData.value, temperatureData.unit);
                            }
                            if (humidityData) {
                                updateGaugeDirectly('humidity-gauge', humidityData.value, humidityData.unit);
                            }
                            if (rainfallData) {
                                updateGaugeDirectly('rainfall-gauge', rainfallData.value, rainfallData.unit);
                            }
                            if (waterLevelData) {
                                updateGaugeDirectly('water-level-gauge', waterLevelData.value, waterLevelData.unit);
                            }
                            if (windSpeedData) {
                                updateGaugeDirectly('wind-speed-gauge', windSpeedData.value, windSpeedData.unit);
                            }
                        }
                    })
                    .catch(error => {
                        console.error('Error in direct sensor data update:', error);
                    });
                };
                
                // Call the newly created function
                window.directUpdateSensorData();
            }
        }
    }, 2000); // Wait 2 seconds after page load
}

/**
 * Update a gauge directly with the given value
 */
function updateGaugeDirectly(gaugeId, value, unit) {
    if (!gaugeId || value === undefined || value === null) return;
    
    // Get gauge elements
    const gauge = document.getElementById(gaugeId);
    if (!gauge) return;
    
    const gaugeValue = gauge.querySelector('.gauge-value');
    if (!gaugeValue) return;
    
    // Calculate severity (green for normal, red for danger)
    let isSevere = false;
    if (gaugeId === 'temperature-gauge' && value > 35) isSevere = true;
    if (gaugeId === 'humidity-gauge' && value > 90) isSevere = true;
    if (gaugeId === 'rainfall-gauge' && value > 25) isSevere = true;
    if (gaugeId === 'water-level-gauge' && value > 1.2) isSevere = true;
    if (gaugeId === 'wind-speed-gauge' && value > 30) isSevere = true;
    
    // Set gauge color based on severity
    if (isSevere) {
        gauge.classList.add('gauge-danger');
    } else {
        gauge.classList.remove('gauge-danger');
    }
    
    // Update gauge value
    gaugeValue.textContent = value + ' ' + unit;
    console.log(`Direct update: ${gaugeId} with value ${value} ${unit}`);
    
    // Update timestamp
    const updatedElement = document.getElementById(gaugeId.split('-')[0] + '-updated');
    if (updatedElement) {
        updatedElement.textContent = 'Updated: ' + new Date().toLocaleTimeString();
    }
}

/**
 * Retry loading map data if map shows an error
 */
function retryMapDataIfNeeded() {
    setTimeout(() => {
        // Check if map error message is visible
        const mapErrorElements = document.querySelectorAll('.leaflet-popup-content');
        let hasMapError = false;
        
        mapErrorElements.forEach(element => {
            if (element.textContent.includes('Map Data Error') || 
                element.textContent.includes('Unable to load')) {
                hasMapError = true;
            }
        });
        
        if (hasMapError || !window.hasMapData) {
            console.log('Map data error detected, attempting to reload map data...');
            
            // Try to get selected municipality
            let municipalityId = null;
            if (window.selectedMunicipality && window.selectedMunicipality.id) {
                municipalityId = window.selectedMunicipality.id;
            }
            
            // Build URL for map data
            let mapDataUrl = '/api/map-data/';
            if (municipalityId) {
                mapDataUrl += `?municipality_id=${municipalityId}`;
            }
            
            // Fetch map data
            fetch(mapDataUrl, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                console.log('Successfully fetched map data:', data);
                
                // If we have a loadMapData function, call it
                if (window.loadMapData) {
                    window.loadMapData(data);
                } else if (window.initializeMap) {
                    window.initializeMap(data);
                }
                
                window.hasMapData = true;
            })
            .catch(error => {
                console.error('Error loading map data:', error);
            });
        }
    }, 3000); // Wait 3 seconds after page load
}
