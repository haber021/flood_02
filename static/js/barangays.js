/**
 * Barangays.js - Barangay management functionality
 * Handles barangay listings, filtering, searching, and map visualization
 */

// Global variables
let barangayMap;
let allMunicipalities = [];
let allBarangays = [];
let loadedMunicipalityBarangays = [];
let selectedMunicipalityId = null;
let selectedBarangayId = null;
// Keep a registry of markers by barangay id for quick focus
const markerByBarangayId = new Map();

// Initialize barangays page
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the barangays map if present
    const mapElement = document.getElementById('barangays-map');
    if (mapElement) {
        initializeBarangaysMap();
    }
    
    // Set up search form functionality
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        setupSearchForm(searchForm);
    }
    
    // Load all municipalities
    loadMunicipalities();
    
    // Set up municipality selector
    const municipalitySelect = document.getElementById('municipality-select');
    const barangaySelect = document.getElementById('barangay-select');
    if (municipalitySelect) {
        municipalitySelect.addEventListener('change', function() {
            selectedMunicipalityId = this.value || null;
            sessionStorage.setItem('barangays_page_muni_id', selectedMunicipalityId || '');
            selectedBarangayId = null;
            if (barangaySelect) {
                barangaySelect.innerHTML = '<option value="">-- All Barangays --</option>';
                barangaySelect.disabled = !selectedMunicipalityId;
            }
            if (selectedMunicipalityId) {
                loadAllBarangaysForMunicipality(selectedMunicipalityId).then(() => {
                    // Populate barangay dropdown
                    populateBarangayDropdown(allBarangays);
                });
            } else {
                // Reset barangay display when no municipality is selected
                document.getElementById('barangay-cards-container').innerHTML = 
                    '<div class="col-12 text-center py-5"><p class="text-muted">Please select a municipality to view its barangays</p></div>';
                // Clear markers
                clearBarangayMarkers();
            }
        });
    }

    if (barangaySelect) {
        barangaySelect.addEventListener('change', function() {
            selectedBarangayId = this.value || null;
            sessionStorage.setItem('barangays_page_brgy_id', selectedBarangayId || '');
            focusSelectedBarangayOnMap(selectedBarangayId);
        });
    }

    // Restore saved selections
    const savedMuni = sessionStorage.getItem('barangays_page_muni_id');
    const savedBrgy = sessionStorage.getItem('barangays_page_brgy_id');
    if (savedMuni && municipalitySelect) {
        municipalitySelect.value = savedMuni;
        selectedMunicipalityId = savedMuni;
        loadAllBarangaysForMunicipality(savedMuni).then(() => {
            populateBarangayDropdown(allBarangays);
            if (savedBrgy && barangaySelect) {
                barangaySelect.value = savedBrgy;
                selectedBarangayId = savedBrgy;
                focusSelectedBarangayOnMap(selectedBarangayId);
            }
        });
    }
});

/**
 * Initialize the barangays overview map
 */
function initializeBarangaysMap() {
    // Create the map centered on the Philippines
    barangayMap = L.map('barangays-map').setView([12.8797, 121.7740], 6);
    
    // Add the base tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(barangayMap);
    
    // Load barangay data
    loadBarangayMapData();
}

/**
 * Load barangay data for map visualization
 */
function loadBarangayMapData() {
    fetch('/api/barangays/')
        .then(response => response.json())
        .then(data => {
            if (!data.results || data.results.length === 0) {
                console.warn('No barangay data available');
                return;
            }
            
            // Load active alerts to check affected barangays
            fetch('/api/flood-alerts/?active=true')
                .then(alertResponse => alertResponse.json())
                .then(alertData => {
                    const activeAlerts = alertData.results || [];
                    // Create a map of barangay IDs to their highest alert severity
                    const affectedBarangays = {};
                    
                    activeAlerts.forEach(alert => {
                        (alert.affected_barangays || []).forEach(barangayId => {
                            // If this barangay doesn't have a severity yet or this alert has higher severity, update it
                            if (!affectedBarangays[barangayId] || alert.severity_level > affectedBarangays[barangayId]) {
                                affectedBarangays[barangayId] = alert.severity_level;
                            }
                        });
                    });
                    
                    // Add barangay markers to the map
                    addBarangayMarkers(data.results, affectedBarangays);
                })
                .catch(error => {
                    console.error('Error loading alert data:', error);
                    // Still add markers without alert status
                    addBarangayMarkers(data.results, {});
                });
        })
        .catch(error => {
            console.error('Error loading barangay data:', error);
        });
}

/**
 * Add barangay markers to the map
 */
function addBarangayMarkers(barangays, affectedBarangays) {
    // Reset marker registry
    markerByBarangayId.clear();

    // Collect all coordinates for bounding the map
    let coordinates = [];
    
    // Create markers for each barangay
    barangays.forEach(barangay => {
        if (!barangay.latitude || !barangay.longitude) return;
        // Add to coordinates list
        coordinates.push([barangay.latitude, barangay.longitude]);
        
        // Determine marker color based on alert severity
        let markerColor = '#198754'; // Default green (Normal)
        let severityText = 'Normal';
        const severity = affectedBarangays[barangay.id];
        
        if (severity) {
            switch (severity) {
                case 5:
                    markerColor = '#7F0000'; // Catastrophic
                    severityText = 'Catastrophic';
                    break;
                case 4:
                    markerColor = '#DC3545'; // Emergency
                    severityText = 'Emergency';
                    break;
                case 3:
                    markerColor = '#FD7E14'; // Warning
                    severityText = 'Warning';
                    break;
                case 2:
                    markerColor = '#FFC107'; // Watch
                    severityText = 'Watch';
                    break;
                case 1:
                    markerColor = '#0DCAF0'; // Advisory
                    severityText = 'Advisory';
                    break;
            }
        }
        
        // Create custom icon
        const icon = L.divIcon({
            className: 'custom-div-icon',
            html: `<div style="background-color: ${markerColor}; width: 15px; height: 15px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 8px rgba(0,0,0,0.3);"></div>`,
            iconSize: [15, 15],
            iconAnchor: [7.5, 7.5]
        });
        
        // Add marker with popup and store in registry
        const marker = L.marker([barangay.latitude, barangay.longitude], { icon: icon })
            .bindPopup(`
                <strong>${barangay.name}</strong><br>
                Population: ${barangay.population.toLocaleString()}<br>
                Status: <span style="color: ${markerColor};">${severityText}</span><br>
                <a href="/barangays/${barangay.id}/" class="btn btn-sm btn-primary mt-2">View Details</a>
            `)
            .addTo(barangayMap);
        markerByBarangayId.set(String(barangay.id), marker);
    });
    
    // If we have coordinates, adjust the map view
    if (coordinates.length > 0) {
        barangayMap.fitBounds(L.latLngBounds(coordinates), {
            padding: [50, 50],
            maxZoom: 10
        });
    }

    // If a specific barangay was selected previously, focus it
    if (selectedBarangayId) {
        focusSelectedBarangayOnMap(selectedBarangayId);
    }
}

/**
 * Set up search and filter functionality
 */
function setupSearchForm(form) {
    // Add event listener for real-time filtering
    const nameInput = form.querySelector('input[name="name"]');
    const severitySelect = form.querySelector('select[name="severity_level"]');
    
    // Real-time filtering with debounce
    let debounceTimer;
    
    nameInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            form.submit();
        }, 500);
    });
    
    severitySelect.addEventListener('change', function() {
        form.submit();
    });
}

/**
 * Load all municipalities into the dropdown
 */
function loadMunicipalities() {
    fetch('/api/municipalities/')
        .then(response => response.json())
        .then(data => {
            if (!data.results || data.results.length === 0) {
                console.warn('No municipalities available');
                return;
            }
            
            // Store municipalities in global variable
            allMunicipalities = data.results;
            
            // Populate municipality dropdown
            const municipalitySelect = document.getElementById('municipality-select');
            if (municipalitySelect) {
                // Clear existing options except the default prompt
                while (municipalitySelect.options.length > 1) {
                    municipalitySelect.remove(1);
                }
                
                // Sort municipalities by name
                const sortedMunicipalities = [...allMunicipalities].sort((a, b) => a.name.localeCompare(b.name));
                
                // Add municipalities to dropdown
                sortedMunicipalities.forEach(municipality => {
                    const option = document.createElement('option');
                    option.value = municipality.id;
                    option.textContent = `${municipality.name}, ${municipality.province}`;
                    municipalitySelect.appendChild(option);
                });
                
                // Check if we need to auto-select a municipality
                // Try to get from URL parameters first, then session storage
                const urlParams = new URLSearchParams(window.location.search);
                const municipalityIdFromUrl = urlParams.get('municipality_id');
                
                if (municipalityIdFromUrl) {
                    municipalitySelect.value = municipalityIdFromUrl;
                    selectedMunicipalityId = municipalityIdFromUrl;
                    loadAllBarangaysForMunicipality(municipalityIdFromUrl);
                } else {
                    const savedMunicipalityId = sessionStorage.getItem('selectedMunicipalityId');
                    if (savedMunicipalityId) {
                        municipalitySelect.value = savedMunicipalityId;
                        selectedMunicipalityId = savedMunicipalityId;
                        loadAllBarangaysForMunicipality(savedMunicipalityId);
                    }
                }
            }
        })
        .catch(error => {
            console.error('Error loading municipalities:', error);
        });
}

/**
 * Load all barangays for a specific municipality using the dedicated API endpoint
 */
function loadAllBarangaysForMunicipality(municipalityId) {
    if (!municipalityId) return;
    
    // Convert to integer for consistent comparison
    const municipalityIdInt = parseInt(municipalityId);
    
    // Save the selection to session storage
    sessionStorage.setItem('selectedMunicipalityId', municipalityIdInt);
    
    // Show loading state
    const barangayCardsContainer = document.getElementById('barangay-cards-container');
    if (barangayCardsContainer) {
        barangayCardsContainer.innerHTML = `
            <div class="col-12 text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-3 text-muted">Loading barangays for selected municipality...</p>
            </div>
        `;
    }
    
    // Use the new comprehensive API endpoint
    const url = `/api/all-barangays/?municipality_id=${municipalityIdInt}`;
    
    return fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.barangays && data.barangays.length > 0) {
                // Determine municipality object from API (supports either `municipality` or `municipalities` array)
                const muniFromSingle = data.municipality || null;
                const muniFromList = (data.municipalities && data.municipalities.length)
                  ? (data.municipalities.find(m => String(m.id) === String(municipalityIdInt)) || data.municipalities[0])
                  : null;
                const municipalityObj = muniFromSingle || muniFromList || { name: 'Municipality', province: '' };

                console.log(`[Barangays] Found ${data.barangays.length} barangays for ${municipalityObj.name}`);
                
                // Store all the barangays for this municipality
                allBarangays = data.barangays;
                
                // Fetch active alerts for the municipality to annotate cards with warnings
                const alertsUrl = `/api/flood-alerts/?active=true&municipality_id=${municipalityIdInt}`;
                return fetch(alertsUrl)
                  .then(r => r.ok ? r.json() : { results: [] })
                  .then(alertData => {
                    const alerts = alertData.results || [];
                    const alertsByBarangay = {};
                    alerts.forEach(alert => {
                        (alert.affected_barangays || []).forEach(bid => {
                            // keep highest severity per barangay
                            if (!alertsByBarangay[bid] || alert.severity_level > alertsByBarangay[bid].level) {
                                alertsByBarangay[bid] = { level: alert.severity_level, title: alert.title || 'Active Alert' };
                            }
                        });
                    });
                    // Render the barangay cards with warning strips/messages
                    displayBarangayCards(municipalityObj, data.barangays, alertsByBarangay);
                    // Update map if possible
                    updateMapWithBarangays(data.barangays);
                  });
            } else {
                // Display no barangays message
                if (barangayCardsContainer) {
                    barangayCardsContainer.innerHTML = `
                        <div class="col-12 text-center py-5">
                            <i class="fas fa-info-circle fa-3x text-muted mb-3"></i>
                            <h5>No barangays found for the selected municipality</h5>
                            <p class="text-muted">Try selecting a different municipality</p>
                        </div>
                    `;
                }
            }
        })
        .catch(error => {
            console.error(`Error loading barangays for municipality ${municipalityId}:`, error);
            
            // Display error message
            if (barangayCardsContainer) {
                barangayCardsContainer.innerHTML = `
                    <div class="col-12 text-center py-5">
                        <i class="fas fa-exclamation-triangle fa-3x text-danger mb-3"></i>
                        <h5>Error loading barangays</h5>
                        <p class="text-muted">There was a problem loading barangay data. Please try again.</p>
                    </div>
                `;
            }
        });
}

/**
 * Display barangay cards in a grid layout
 */
function displayBarangayCards(municipality, barangays, alertsByBarangay = {}) {
    const barangayCardsContainer = document.getElementById('barangay-cards-container');
    if (!barangayCardsContainer) return;
    
    // Calculate total population
    const totalPopulation = barangays.reduce((sum, b) => sum + b.population, 0);
    
    // Start with municipality summary card
    let cardsHtml = `
        <div class="col-12 mb-4">
            <div class="card bg-primary text-white">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h4 class="mb-0">${municipality.name}</h4>
                            <p class="mb-0">${municipality.province}</p>
                        </div>
                        <div class="text-end">
                            <h4 class="mb-0">${totalPopulation.toLocaleString()}</h4>
                            <p class="mb-0">Total Population</p>
                        </div>
                    </div>
                    <div class="mt-3">
                        <span class="badge bg-white text-primary">Total Barangays: ${barangays.length}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Sort barangays alphabetically
    const sortedBarangays = [...barangays].sort((a, b) => a.name.localeCompare(b.name));
    
    // Add individual barangay cards
    sortedBarangays.forEach(barangay => {
        // Calculate population percentage
        const populationPercentage = (barangay.population / totalPopulation * 100).toFixed(1);
        // Determine warning based on alerts map
        const a = alertsByBarangay[barangay.id];
        const sev = a ? a.level : 0;
        let stripColor = '#198754'; // default green
        let sevText = 'Normal';
        if (sev === 1) { stripColor = '#0DCAF0'; sevText = 'Advisory'; }
        if (sev === 2) { stripColor = '#FFC107'; sevText = 'Watch'; }
        if (sev === 3) { stripColor = '#FD7E14'; sevText = 'Warning'; }
        if (sev === 4) { stripColor = '#DC3545'; sevText = 'Emergency'; }
        if (sev === 5) { stripColor = '#7F0000'; sevText = 'Catastrophic'; }

        cardsHtml += `
            <div class="col-md-4 col-lg-3 mb-3">
                <div class="card h-100 shadow-sm position-relative">
                    ${sev > 0 ? `<div style="position:absolute;left:0;top:0;bottom:0;width:6px;background:${stripColor};border-top-left-radius:.375rem;border-bottom-left-radius:.375rem"></div>` : ''}
                    <div class="card-header bg-light">
                        <h6 class="mb-0">${barangay.name}</h6>
                    </div>
                    <div class="card-body">
                        ${sev > 0 ? `
                        <div class="d-flex align-items-start mb-3" style="color:${stripColor}">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            <div>
                                <strong>${sevText}</strong>${a && a.title ? `: ${escapeHtml(a.title)}` : ''}
                            </div>
                        </div>
                        ` : ''}
                        <div class="d-flex justify-content-between mb-2">
                            <span>Population:</span>
                            <strong>${barangay.population.toLocaleString()}</strong>
                        </div>
                        <div class="d-flex justify-content-between mb-3">
                            <span>% of Municipality:</span>
                            <strong>${populationPercentage}%</strong>
                        </div>
                        
                        ${barangay.contact_person ? `
                        <div class="d-flex justify-content-between mb-2">
                            <span>Contact Person:</span>
                            <strong>${barangay.contact_person}</strong>
                        </div>` : ''}
                        
                        ${barangay.contact_number ? `
                        <div class="d-flex justify-content-between">
                            <span>Contact Number:</span>
                            <strong>${barangay.contact_number}</strong>
                        </div>` : ''}
                    </div>
                    <div class="card-footer bg-white d-flex justify-content-between align-items-center">
                        <a href="/barangays/${barangay.id}/" class="btn btn-sm btn-outline-primary">
                            <i class="fas fa-eye me-1"></i> Details
                        </a>
                        <button onclick="showBarangayOnMap(${barangay.latitude}, ${barangay.longitude})" class="btn btn-sm btn-outline-secondary">
                            <i class="fas fa-map-marker-alt me-1"></i> Show on Map
                        </button>
                    </div>
                </div>
            </div>
        `;
    });
    
    // Update the container
    barangayCardsContainer.innerHTML = cardsHtml;
}

// Basic HTML escape to avoid XSS when rendering alert titles
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#39;');
}

function populateBarangayDropdown(barangays) {
    const barangaySelect = document.getElementById('barangay-select');
    if (!barangaySelect) return;
    barangaySelect.innerHTML = '<option value="">-- All Barangays --</option>';
    barangaySelect.disabled = !barangays || barangays.length === 0;
    if (!barangays || barangays.length === 0) return;
    const sorted = [...barangays].sort((a,b)=>a.name.localeCompare(b.name));
    sorted.forEach(b => {
        if (b.id != null) {
            const opt = document.createElement('option');
            opt.value = String(b.id);
            opt.textContent = b.name;
            barangaySelect.appendChild(opt);
        }
    });
}

function clearBarangayMarkers() {
    // Remove markers only; preserve base tile layer
    const layersToRemove = [];
    barangayMap.eachLayer(layer => {
        if (layer instanceof L.Marker || layer instanceof L.Circle || layer instanceof L.CircleMarker) {
            layersToRemove.push(layer);
        }
    });
    layersToRemove.forEach(l => barangayMap.removeLayer(l));
    markerByBarangayId.clear();
}

function focusSelectedBarangayOnMap(barangayId) {
    if (!barangayId) return;
    const marker = markerByBarangayId.get(String(barangayId));
    if (marker && barangayMap) {
        const latLng = marker.getLatLng();
        barangayMap.setView(latLng, 15, { animate: true });
        marker.openPopup();
        // Add a brief pulse effect
        const pulse = L.circleMarker(latLng, { radius: 28, color: '#0d6efd', fillColor: '#0d6efd', fillOpacity: 0.3, weight: 2 }).addTo(barangayMap);
        setTimeout(() => barangayMap.removeLayer(pulse), 1800);
    } else {
        // If marker not present yet (e.g., initial load), try to find by data cache
        const found = allBarangays.find(b => String(b.id) === String(barangayId));
        if (found && found.latitude && found.longitude) {
            barangayMap.setView([found.latitude, found.longitude], 15, { animate: true });
        }
    }
}

/**
 * Show a specific barangay on the map
 */
function showBarangayOnMap(lat, lng) {
    if (!barangayMap || !lat || !lng) return;
    
    // Zoom to the barangay location
    barangayMap.setView([lat, lng], 15);
    
    // Add a temporary highlight effect
    const highlightMarker = L.circleMarker([lat, lng], {
        color: '#007bff',
        fillColor: '#007bff',
        fillOpacity: 0.5,
        radius: 30,
        weight: 2
    }).addTo(barangayMap);
    
    // Animate the highlight
    let size = 30;
    const pulseAnimation = setInterval(() => {
        size = size === 30 ? 20 : 30;
        highlightMarker.setRadius(size);
    }, 500);
    
    // Remove the highlight after a few seconds
    setTimeout(() => {
        clearInterval(pulseAnimation);
        barangayMap.removeLayer(highlightMarker);
    }, 5000);
}

/**
 * Update the map with specific barangays
 */
function updateMapWithBarangays(barangays) {
    if (!barangayMap || !barangays.length) return;
    
    // Clear existing markers (markers and circles)
    clearBarangayMarkers();
    
    // Add markers for each barangay
    const coordinates = [];
    
    barangays.forEach(barangay => {
        if (barangay.latitude && barangay.longitude) {
            coordinates.push([barangay.latitude, barangay.longitude]);
            
            // Create marker and registry
            const marker = L.marker([barangay.latitude, barangay.longitude])
                .bindPopup(`
                    <strong>${barangay.name}</strong><br>
                    Population: ${barangay.population.toLocaleString()}<br>
                    <a href="/barangays/${barangay.id}/" class="btn btn-sm btn-primary mt-2">View Details</a>
                `)
                .addTo(barangayMap);
            markerByBarangayId.set(String(barangay.id), marker);
        }
    });
    
    // Adjust the map view to show all barangays
    if (coordinates.length > 0) {
        barangayMap.fitBounds(L.latLngBounds(coordinates), {
            padding: [50, 50],
            maxZoom: 12
        });
    }

    // If a specific barangay selected, focus it
    if (selectedBarangayId) {
        focusSelectedBarangayOnMap(selectedBarangayId);
    }
}

/**
 * Format number with commas for thousands
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Handle individual barangay map if on detail page
 */
if (document.getElementById('barangay-map')) {
    // Get barangay coordinates from data attributes or default to Philippines
    const mapElement = document.getElementById('barangay-map');
    const latitude = parseFloat(mapElement.getAttribute('data-latitude') || 12.8797);
    const longitude = parseFloat(mapElement.getAttribute('data-longitude') || 121.7740);
    
    // Initialize map
    const map = L.map('barangay-map').setView([latitude, longitude], 14);
    
    // Add base tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    
    // Add barangay marker
    const barangayIcon = L.divIcon({
        html: '<i class="fas fa-home fa-2x text-primary"></i>',
        className: 'custom-div-icon',
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    });
    
    L.marker([latitude, longitude], {icon: barangayIcon})
        .addTo(map)
        .bindPopup(`<strong>${mapElement.getAttribute('data-name') || 'Barangay'}</strong><br>Barangay Office`);
}
