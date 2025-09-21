/**
 * Prediction.js - Flood prediction functionality
 * Handles historical data analysis, prediction model visualization, and alert management
 */

// Global chart objects
let historicalChart;

// Current data mode (rainfall or water level)
let currentHistoricalMode = 'rainfall';

// Current time period for historical data
let currentHistoricalPeriod = 7;

// Initialize prediction page
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if we're on the prediction page
    if (!document.getElementById('historical-chart')) return;
    
    // Initialize historical chart
    initializeHistoricalChart();
    
    // Set up tab switching
    document.getElementById('btn-rainfall-history').addEventListener('click', function() {
        if (currentHistoricalMode !== 'rainfall') {
            currentHistoricalMode = 'rainfall';
            toggleHistoricalButtons();
            loadHistoricalData();
            loadDecisionSupportSuggestion();
        }
    });
    
    document.getElementById('btn-water-level-history').addEventListener('click', function() {
        if (currentHistoricalMode !== 'water_level') {
            currentHistoricalMode = 'water_level';
            toggleHistoricalButtons();
            loadHistoricalData();
            loadDecisionSupportSuggestion();
        }
    });
    
    // Set up period buttons
    document.querySelectorAll('[data-period]').forEach(btn => {
        btn.addEventListener('click', function() {
            // Update active button
            document.querySelectorAll('[data-period]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            // Update period and reload data
            currentHistoricalPeriod = parseInt(this.getAttribute('data-period'));
            loadHistoricalData();
            loadDecisionSupportSuggestion();
        });
    });
    
    // Initialize prediction model
    updatePredictionModel();
    // Initialize decision support suggestion
    loadDecisionSupportSuggestion();
    
    // Load affected barangays
    loadPotentiallyAffectedBarangays();
    
    // Set up form validation
    setupAlertForm();
    
    // View all barangays button
    document.getElementById('view-all-barangays').addEventListener('click', function() {
        window.location.href = '/barangays/';
    });
    
    // Refresh prediction button
    document.getElementById('refresh-prediction').addEventListener('click', function() {
        this.disabled = true;
        this.innerHTML = '<i class="fas fa-sync-alt fa-spin me-1"></i> Refreshing...';
        
        // Call the actual API for real-time data
        updatePredictionModel();
        
        // Re-enable the button after a short delay
        setTimeout(() => {
            this.disabled = false;
            this.innerHTML = '<i class="fas fa-sync-alt me-1"></i> Refresh';
        }, 1000);
    });
    
    // Export chart button
    document.querySelector('.export-chart').addEventListener('click', function() {
        exportHistoricalChart();
    });
});

/**
 * Initialize historical comparison chart
 */
function initializeHistoricalChart() {
    const ctx = document.getElementById('historical-chart').getContext('2d');
    
    // Get container width - important for proper sizing
    const container = document.getElementById('historical-chart-container');
    
    historicalChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Current Data',
                data: [],
                borderColor: 'rgb(54, 162, 235)',
                backgroundColor: 'rgba(54, 162, 235, 0.05)',
                borderWidth: 2,
                tension: 0.1,
                pointRadius: 2,
                pointHoverRadius: 4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            // Remove fixed aspectRatio to allow container-based sizing
            scales: {
                y: {
                    beginAtZero: false,
                    title: {
                        display: true,
                        text: 'Rainfall (mm)'
                    },
                    ticks: {
                        padding: 10,
                        font: {
                            size: 11
                        },
                        precision: 1
                    },
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.03)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Date'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 0,
                        padding: 10,
                        maxTicksLimit: 10,
                        autoSkip: true,
                        callback: function(value, index, values) {
                            // Improved date formatting 
                            if (typeof value === 'string' && value.includes('-')) {
                                try {
                                    const date = new Date(value);
                                    if (!isNaN(date.getTime())) {
                                        // Check time period
                                        const timeRange = currentHistoricalPeriod || 7;
                                        
                                        if (timeRange >= 30) {
                                            // For monthly view, show just month/day
                                            return `${date.getMonth()+1}/${date.getDate()}`;
                                        } else if (timeRange >= 7) {
                                            // For weekly view 
                                            return `${date.getMonth()+1}/${date.getDate()}`;
                                        } else {
                                            // For daily view
                                            return `${date.getMonth()+1}/${date.getDate()} ${date.getHours()}:${(date.getMinutes() < 10 ? '0' : '') + date.getMinutes()}`;
                                        }
                                    }
                                } catch (e) {}
                                
                                // Fallback if date parsing fails
                                const parts = value.split(' ');
                                if (parts.length > 1) {
                                    return parts[0];
                                }
                            }
                            return value;
                        }
                    }
                }
            },
            plugins: {
                tooltip: {
                    mode: 'index',
                    intersect: false
                },
                legend: {
                    position: 'top',
                },
                zoom: {
                    zoom: {
                        wheel: {
                            enabled: true,
                        },
                        pinch: {
                            enabled: true
                        },
                        mode: 'xy',
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
    
    // Load initial data
    loadHistoricalData();
}

/**
 * Toggle active class on historical data buttons
 */
function toggleHistoricalButtons() {
    if (currentHistoricalMode === 'rainfall') {
        document.getElementById('btn-rainfall-history').classList.add('active');
        document.getElementById('btn-water-level-history').classList.remove('active');
    } else {
        document.getElementById('btn-rainfall-history').classList.remove('active');
        document.getElementById('btn-water-level-history').classList.add('active');
    }
}

/**
 * Load historical data for comparison
 */
function loadHistoricalData() {
    // Update chart title and axis label based on mode
    if (currentHistoricalMode === 'rainfall') {
        historicalChart.options.scales.y.title.text = 'Rainfall (mm)';
        // Configure ideal y-axis for rainfall data
        historicalChart.options.scales.y.beginAtZero = true;
        // Allow more space above the maximum data point (rainfall can spike)
        historicalChart.options.scales.y.suggestedMax = null;
    } else {
        historicalChart.options.scales.y.title.text = 'Water Level (m)';
        // Configure ideal y-axis for water level data
        historicalChart.options.scales.y.beginAtZero = false;
        // Water levels need a narrower range for better visualization
        historicalChart.options.scales.y.suggestedMax = null;
    }
    
    // Construct the URL with parameters
    let url = `/api/chart-data/?type=${currentHistoricalMode}&days=${currentHistoricalPeriod}`;
    
    // Add location parameters if available
    if (window.selectedMunicipality) {
        url += `&municipality_id=${window.selectedMunicipality.id}`;
        console.log(`Adding municipality filter: ${window.selectedMunicipality.name}`);
    }
    
    if (window.selectedBarangay) {
        url += `&barangay_id=${window.selectedBarangay.id}`;
        console.log(`Adding barangay filter: ${window.selectedBarangay.name}`);
    }
    
    console.log(`Fetching historical ${currentHistoricalMode} data with URL: ${url}`);
    
    // Reset chart before loading new data
    if (historicalChart.data.datasets.length > 1) {
        historicalChart.data.datasets.splice(1); // Remove all datasets except the first one
    }
    
    // Fetch data from API with location filters
    fetch(url)
        .then(response => response.json())
        .then(data => {
            console.log(`Received ${data.labels ? data.labels.length : 0} data points for ${currentHistoricalMode}`);
            
            // Update current data
            historicalChart.data.labels = data.labels || [];
            historicalChart.data.datasets[0].data = data.values || [];
            
            // If no data received, show a helpful message on the chart
            if (!data.labels || data.labels.length === 0) {
                console.warn('No data available for the selected time period');
            }
            
            // Add historical comparison data
            addHistoricalComparisonData();
        })
        .catch(error => {
            console.error(`Error loading ${currentHistoricalMode} historical data:`, error);
        });
}

/**
 * Add historical comparison data to chart
 */
function addHistoricalComparisonData() {
    // Get current dataset values to help calculate thresholds
    const currentData = historicalChart.data.datasets[0].data;
    
    // Construct the URL with parameters
    let url = `/api/chart-data/?type=${currentHistoricalMode}&days=${currentHistoricalPeriod}&historical=true`;
    
    // Add location parameters if available for consistent data filtering
    if (window.selectedMunicipality) {
        url += `&municipality_id=${window.selectedMunicipality.id}`;
        console.log(`Adding municipality filter for historical comparison: ${window.selectedMunicipality.name}`);
    }
    
    if (window.selectedBarangay) {
        url += `&barangay_id=${window.selectedBarangay.id}`;
        console.log(`Adding barangay filter for historical comparison: ${window.selectedBarangay.name}`);
    }
    
    console.log(`Fetching historical comparison data with URL: ${url}`);
    
    // Fetch actual historical average data from the API with location filters
    fetch(url)
        .then(response => response.json())
        .then(data => {
            console.log(`Received ${data.historical_values ? data.historical_values.length : 0} historical comparison data points`);
            
            // Add the historical dataset if we have data
            if (data.historical_values && data.historical_values.length > 0) {
                historicalChart.data.datasets.push({
                    label: 'Historical Average (Past 3 Years)',
                    data: data.historical_values,
                    borderColor: 'rgba(180, 180, 180, 0.7)',
                    backgroundColor: 'rgba(180, 180, 180, 0.05)',
                    borderWidth: 1,
                    borderDash: [3, 3],
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    fill: true
                });
                
                // Update the chart
                historicalChart.update();
            } else {
                console.log('No historical average data available');
            }
            
            // Add flood threshold line if we're showing water level
            if (currentHistoricalMode === 'water_level') {
                // Get the threshold from API if available, otherwise use default
                const threshold = data.threshold_value || 1.5;
                
                // Add threshold line at the specified level (typical flood level)
                addThresholdLine(threshold, 'Flood Stage', 'rgba(220, 53, 69, 0.7)');
            } else if (currentHistoricalMode === 'rainfall') {
                // Add advisory threshold for significant rainfall (25mm/day)
                addThresholdLine(25, 'Heavy Rainfall Advisory', 'rgba(220, 53, 69, 0.9)');
            }
        })
        .catch(error => {
            console.error('Error loading historical comparison data:', error);
        });
}

/**
 * Add a threshold line to the chart
 */
function addThresholdLine(value, label, color) {
    // We'd use the annotation plugin in a full implementation
    // For this example, we'll just add another dataset as a horizontal line
    
    // Create array of same value for every label
    const thresholdData = historicalChart.data.labels.map(() => value);
    
    // Find if we already have a threshold line with this label
    const existingIndex = historicalChart.data.datasets.findIndex(ds => ds.label === label);
    
    if (existingIndex > 0) {
        // Update existing threshold dataset
        historicalChart.data.datasets[existingIndex].data = thresholdData;
    } else {
        // Add the threshold dataset
        historicalChart.data.datasets.push({
            label: label,
            data: thresholdData,
            borderColor: color,
            backgroundColor: 'transparent',
            borderWidth: 1.5,
            borderDash: [],
            pointRadius: 0,
            pointHoverRadius: 0,
            tension: 0,
            // Make threshold lines more obvious visually
            order: 0 // Ensure it's drawn on top
        });
    }
    
    // Adjust chart scale to ensure threshold is visible
    const minValue = Math.min(...historicalChart.data.datasets[0].data.filter(v => v !== null && v !== undefined));
    const maxValue = Math.max(...historicalChart.data.datasets[0].data.filter(v => v !== null && v !== undefined));
    const range = maxValue - minValue;
    
    // Only adjust if threshold value is outside current data range or very close to edges
    if (value < minValue || value > maxValue || Math.abs(value - minValue) < range * 0.1 || Math.abs(value - maxValue) < range * 0.1) {
        if (value < minValue) {
            historicalChart.options.scales.y.min = value * 0.9; // Give some padding below
        }
        if (value > maxValue) {
            historicalChart.options.scales.y.max = value * 1.1; // Give some padding above
        }
    }
    
    // Update the chart
    historicalChart.update();
}

/**
 * Update the prediction model visualization
 */
function updatePredictionModel() {
    // Show loading state
    document.getElementById('prediction-status').textContent = 'Loading prediction model...';
    document.getElementById('flood-probability').textContent = '--';
    document.getElementById('prediction-impact').textContent = 'Analyzing sensor data...';
    document.getElementById('prediction-eta').textContent = 'Calculating...';
    document.getElementById('contributing-factors').innerHTML = '<li>Loading factors...</li>';
    
    // Change gauge to loading state
    const gaugeCircle = document.querySelector('.gauge-circle');
    gaugeCircle.style.background = 'conic-gradient(#6c757d 0% 100%)';
    
    // Get location filters if available
    let url = '/api/prediction/';
    const params = [];
    
    // Add municipality filter if selected
    if (window.selectedMunicipality) {
        params.push(`municipality_id=${window.selectedMunicipality.id}`);
    }
    
    // Add barangay filter if selected
    if (window.selectedBarangay) {
        params.push(`barangay_id=${window.selectedBarangay.id}`);
    }
    
    // Add parameters to URL if any
    if (params.length > 0) {
        url += '?' + params.join('&');
    }
    
    console.log('Fetching prediction data from:', url);
    
    // Call the real-time prediction API
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Prediction data:', data);
            
            // Extract probability
            const probability = data.probability;
            
            // Update the gauge
            document.getElementById('flood-probability').textContent = probability + '%';
            
            // Change color based on probability - using only two colors (green for normal, red for danger)
            gaugeCircle.classList.remove('danger');
            if (probability >= 50) { // 50% or higher is considered danger level
                gaugeCircle.classList.add('danger');
                // Red for danger
                gaugeCircle.style.background = 'conic-gradient(#dc3545 0% 100%)';
            } else {
                // Green for normal
                gaugeCircle.style.background = 'conic-gradient(#198754 0% 100%)';
            }
            
            // Update predicted impact
            document.getElementById('prediction-impact').textContent = data.impact;
            
            // Update ETA
            let etaText;
            if (data.hours_to_flood && data.flood_time) {
                const floodDate = new Date(data.flood_time);
                etaText = `Estimated flood arrival: ${floodDate.toLocaleString()} (approximately ${Math.round(data.hours_to_flood)} hours from now)`;
            } else {
                etaText = 'No immediate flood threat expected in the next 24 hours.';
            }
            document.getElementById('prediction-eta').textContent = etaText;
            
            // Update contributing factors
            const factorsElement = document.getElementById('contributing-factors');
            if (data.contributing_factors && data.contributing_factors.length > 0) {
                factorsElement.innerHTML = data.contributing_factors.map(factor => `<li>${factor}</li>`).join('');
            } else {
                factorsElement.innerHTML = '<li>No significant contributing factors identified</li>';
            }
            
            // Update potentially affected barangays
            updateAffectedBarangays(data.affected_barangays || []);
            
            // Update additional data
            const statusElement = document.getElementById('prediction-status');
            statusElement.textContent = 'Prediction complete';
            statusElement.classList.remove('text-warning');
            statusElement.classList.add('text-success');
            
            // Update the last prediction time
            document.getElementById('last-prediction-time').textContent = new Date(data.last_updated).toLocaleString();
            
            // Update rainfall and water level indicators if available
            const rainfallElement = document.getElementById('rainfall-24h');
            if (rainfallElement) {
                // Check if rainfall_24h is an object with total property or a direct value
                if (data.rainfall_24h !== null && data.rainfall_24h !== undefined) {
                    if (typeof data.rainfall_24h === 'object' && data.rainfall_24h.total !== null && data.rainfall_24h.total !== undefined) {
                        rainfallElement.textContent = `${parseFloat(data.rainfall_24h.total).toFixed(1)}mm`;
                    } else if (typeof data.rainfall_24h === 'number') {
                        rainfallElement.textContent = `${parseFloat(data.rainfall_24h).toFixed(1)}mm`;
                    } else {
                        rainfallElement.textContent = '0.0mm';
                    }
                } else {
                    rainfallElement.textContent = '0.0mm';
                }
            }
            
            const waterLevelElement = document.getElementById('current-water-level');
            if (waterLevelElement) {
                if (data.water_level !== null && data.water_level !== undefined) {
                    waterLevelElement.textContent = `${parseFloat(data.water_level).toFixed(2)}m`;
                } else {
                    waterLevelElement.textContent = '0.00m';
                }
            }
        })
        .catch(error => {
            console.error('Error updating prediction model:', error);
            document.getElementById('prediction-status').textContent = 'Error loading prediction';
            document.getElementById('prediction-status').classList.remove('text-warning');
            document.getElementById('prediction-status').classList.add('text-danger');
            document.getElementById('flood-probability').textContent = 'N/A';
            document.getElementById('prediction-impact').textContent = 'Unable to generate prediction. Please try again later.';
            document.getElementById('prediction-eta').textContent = 'Data unavailable';
            document.getElementById('contributing-factors').innerHTML = '<li>Error retrieving data</li>';
        });
}

/**
 * Load potentially affected barangays
 */
function loadPotentiallyAffectedBarangays() {
    // Now just calls updatePredictionModel which will handle everything
    updatePredictionModel();
}

/**
 * Update the affected barangays table with real data
 */
function updateAffectedBarangays(barangays) {
    if (!barangays || barangays.length === 0) {
        document.getElementById('affected-barangays').innerHTML = 
            '<tr><td colspan="4" class="text-center">No potentially affected barangays identified.</td></tr>';
        return;
    }
    
    // Build the table rows
    let barangayRows = '';
    
    barangays.forEach((barangay) => {
        const riskClass = barangay.risk_level === 'High' ? 'text-danger' : 
            (barangay.risk_level === 'Moderate' ? 'text-warning' : 'text-success');
        
        barangayRows += `
            <tr>
                <td><a href="/barangays/${barangay.id}/" class="text-decoration-none">${barangay.name}</a></td>
                <td class="text-center">${barangay.population ? barangay.population.toLocaleString() : 'N/A'}</td>
                <td class="text-center"><span class="${riskClass} fw-bold">${barangay.risk_level}</span></td>
                <td class="text-center">${barangay.evacuation_centers}</td>
            </tr>
        `;
    });
    
    // Update the table
    document.getElementById('affected-barangays').innerHTML = barangayRows;
}

/**
 * Set up the alert form validation and enhancement
 */
function setupAlertForm() {
    const form = document.getElementById('alert-form');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        // Basic validation
        const title = document.getElementById('id_title').value.trim();
        const description = document.getElementById('id_description').value.trim();
        const severity = document.getElementById('id_severity_level').value;
        const barangays = document.getElementById('id_affected_barangays');
        
        if (!title) {
            e.preventDefault();
            alert('Please enter an alert title.');
            return;
        }
        
        if (!description) {
            e.preventDefault();
            alert('Please enter an alert description.');
            return;
        }
        
        if (severity === '') {
            e.preventDefault();
            alert('Please select a severity level.');
            return;
        }
        
        // Check if at least one barangay is selected
        let barangaySelected = false;
        for (let i = 0; i < barangays.options.length; i++) {
            if (barangays.options[i].selected) {
                barangaySelected = true;
                break;
            }
        }
        
        if (!barangaySelected) {
            e.preventDefault();
            alert('Please select at least one affected barangay.');
            return;
        }
        
        // Confirm before sending emergency alert (levels 4-5)
        if (severity === '4' || severity === '5') {
            if (!confirm('You are about to send an EMERGENCY LEVEL alert. This will trigger immediate notifications to all emergency contacts. Are you sure you want to proceed?')) {
                e.preventDefault();
                return;
            }
        }
    });
    
    // Dynamic form behavior - update predicted flood time requirement based on severity
    document.getElementById('id_severity_level').addEventListener('change', function() {
        const severityLevel = parseInt(this.value);
        const predictionTimeField = document.getElementById('id_predicted_flood_time');
        
        // Make prediction time required for high severity levels
        if (severityLevel >= 3) {
            predictionTimeField.setAttribute('required', 'required');
            predictionTimeField.parentElement.classList.add('required-field');
        } else {
            predictionTimeField.removeAttribute('required');
            predictionTimeField.parentElement.classList.remove('required-field');
        }
    });
}

/**
 * Export historical chart as image
 */
/**
 * Fetch backend suggestion based on current Historical Comparison settings
 */
function loadDecisionSupportSuggestion() {
    const mode = currentHistoricalMode; // 'rainfall' or 'water_level'
    const days = currentHistoricalPeriod; // 7, 30, 365
    let url = `/api/historical-suggestion/?type=${mode}&days=${days}`;

    if (window.selectedMunicipality) {
        url += `&municipality_id=${window.selectedMunicipality.id}`;
    }
    if (window.selectedBarangay) {
        url += `&barangay_id=${window.selectedBarangay.id}`;
    }

    // Set loading state
    setSuggestionUI({loading: true});

    fetch(url)
        .then(r => r.json())
        .then(data => {
            setSuggestionUI({
                subject: data.subject,
                level: data.level,
                level_numeric: data.level_numeric,
                reasons: data.reasons || [],
                suggested_action: data.suggested_action
            });
        })
        .catch(err => {
            console.error('Error loading decision support suggestion:', err);
            setSuggestionUI({
                subject: 'Unable to compute suggestion',
                level: 'Error',
                level_numeric: 0,
                reasons: ['An error occurred while analyzing historical data.'],
                suggested_action: 'Please try again later.'
            });
        });
}

function setSuggestionUI({subject, level, level_numeric, reasons, suggested_action, loading}) {
    const levelBadge = document.getElementById('suggestion-level');
    const subjectEl = document.getElementById('suggestion-subject');
    const reasonsEl = document.getElementById('suggestion-reasons');
    const actionEl = document.getElementById('suggested-action');

    if (loading) {
        if (levelBadge) levelBadge.textContent = 'Loading...';
        if (subjectEl) subjectEl.textContent = 'Analyzing historical comparison...';
        if (actionEl) actionEl.textContent = 'Please wait while we compute a recommendation.';
        if (reasonsEl) reasonsEl.innerHTML = '<li>Loading...</li>';
        return;
    }

    if (levelBadge) levelBadge.textContent = level || 'Normal';
    if (subjectEl) subjectEl.textContent = subject || 'Decision Support Available';
    if (actionEl) actionEl.textContent = suggested_action || 'Continue monitoring.';

    if (reasonsEl) {
        if (reasons && reasons.length > 0) {
            reasonsEl.innerHTML = reasons.map(r => `<li>${r}</li>`).join('');
        } else {
            reasonsEl.innerHTML = '<li>No specific reasons available.</li>';
        }
    }
}

function exportHistoricalChart() {
    if (!historicalChart) return;
    
    // Create a temporary link for downloading
    const link = document.createElement('a');
    link.download = `flood-prediction-${currentHistoricalMode}-${new Date().toISOString().slice(0, 10)}.png`;
    
    // Convert chart to data URL
    link.href = historicalChart.toBase64Image();
    link.click();
}
