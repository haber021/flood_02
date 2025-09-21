/**
 * Charts.js - Data visualization charts functionality
 * Handles chart creation, updates, and exports for the dashboard
 */

// Global chart objects
let temperatureChart;
let rainfallChart;
let waterLevelChart;

// Chart colors
const chartColors = {
    temperature: {
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)'
    },
    rainfall: {
        borderColor: 'rgb(54, 162, 235)',
        backgroundColor: 'rgba(54, 162, 235, 0.2)'
    },
    waterLevel: {
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)'
    }
};

// Default time period in days
let chartTimePeriod = 1;

// Manila timezone formatters (24-hour)
const manilaTimeFormatter = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Manila',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
});
const manilaDateTimeFormatter = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Manila',
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
});

function formatManila(dateLike, includeDate = false) {
    const d = (dateLike instanceof Date) ? dateLike : new Date(dateLike);
    try {
        return includeDate ? manilaDateTimeFormatter.format(d) : manilaTimeFormatter.format(d);
    } catch (err) {
        return d.toLocaleString('en-GB', { hour12: false });
    }
}

// Chart initialization
document.addEventListener('DOMContentLoaded', function() {
    // Initialize charts if we're on the dashboard page
    if (document.getElementById('temperature-chart')) {
        initializeCharts();
        
        // When municipality changes, also update chart data
        window.addEventListener('municipalityChanged', function(e) {
            console.log('[Charts] Detected municipality change, updating all charts');
            // Set a small delay to ensure all components have updated
            setTimeout(() => {
                loadChartData('temperature');
                loadChartData('rainfall');
                loadChartData('water_level');
            }, 100);
        });
        
        // Setup time period selector
        document.querySelectorAll('.chart-period').forEach(item => {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                // Update active period
                chartTimePeriod = parseInt(this.getAttribute('data-days'));
                // Update dropdown button text
                document.getElementById('chartDropdown').textContent = this.textContent;
                // Reload chart data
                loadChartData('temperature');
                loadChartData('rainfall');
                loadChartData('water_level');
            });
        });
        
        // Setup reset zoom buttons
        document.querySelectorAll('.reset-zoom').forEach(btn => {
            btn.addEventListener('click', function() {
                const chartId = this.getAttribute('data-chart');
                resetZoom(chartId);
            });
        });
        
        // Setup export buttons
        document.querySelectorAll('.export-chart').forEach(btn => {
            btn.addEventListener('click', function() {
                const chartId = this.getAttribute('data-chart');
                exportChart(chartId);
            });
        });
        
        // Set up window resize handler to adjust charts
        window.addEventListener('resize', function() {
            if (temperatureChart) {
                setTimeout(function() { temperatureChart.resize(); }, 100);
            }
            if (rainfallChart) {
                setTimeout(function() { rainfallChart.resize(); }, 100);
            }
            if (waterLevelChart) {
                setTimeout(function() { waterLevelChart.resize(); }, 100);
            }
        });
    }
});

/**
 * Initialize all charts with empty data
 */
function initializeCharts() {
    // Create temperature chart
    temperatureChart = createChart('temperature-chart', 'Temperature (°C)', chartColors.temperature);
    
    // Create rainfall chart
    rainfallChart = createChart('rainfall-chart', 'Rainfall (mm)', chartColors.rainfall);
    
    // Create water level chart
    waterLevelChart = createChart('water-level-chart', 'Water Level (m)', chartColors.waterLevel);
    
    // Load initial data
    loadChartData('temperature');
    loadChartData('rainfall');
    loadChartData('water_level');
}

/**
 * Update all charts at once
 * Used when location or filters change
 */
function updateAllCharts() {
    console.log('Updating all charts with location filters...');
    console.log('Current Municipality:', window.selectedMunicipality ? window.selectedMunicipality.name : 'All Municipalities');
    console.log('Current Barangay:', window.selectedBarangay ? window.selectedBarangay.name : 'All Barangays');
    
    // Reset zoom on all charts
    resetZoom('temperature-chart');
    resetZoom('rainfall-chart');
    resetZoom('water-level-chart');
    
    // Reload data for all charts with the current location filters
    loadChartData('temperature');
    loadChartData('rainfall');
    loadChartData('water_level');
    
    // Update the location display in the UI if applicable
    const locationDisplay = document.getElementById('current-location-display');
    if (locationDisplay) {
        let locationText = 'All Areas';
        
        if (window.selectedMunicipality) {
            locationText = window.selectedMunicipality.name;
            
            if (window.selectedBarangay) {
                locationText += ' > ' + window.selectedBarangay.name;
            }
        }
        
        locationDisplay.textContent = locationText;
    }
}

/**
 * Create a new chart with the specified configuration
 */
function createChart(canvasId, label, colors) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    // Register the zoom plugin if not already registered
    try {
        if (Chart.registry.getPlugin('zoom')) {
            console.log('Chart.js zoom plugin registered successfully');
        }
    } catch (e) {
        console.warn('Chart.js zoom plugin not detected. Some features may be limited.');
    }
    
    // Determine screen size categories
    const isMobile = window.innerWidth < 768;
    const isWideScreen = window.innerWidth >= 1400;
    const isUltraWideScreen = window.innerWidth >= 2200;
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: label,
                data: [],
                borderColor: colors.borderColor,
                backgroundColor: 'transparent',
                borderWidth: isMobile ? 1.5 : 2,
                tension: 0.2,
                pointRadius: isMobile ? 2 : 3,
                pointHoverRadius: isMobile ? 4 : 5,
                fill: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            devicePixelRatio: 2, // Higher quality rendering
            animation: {
                duration: 750, // General animation duration
                easing: 'easeOutQuart'
            },
            onResize: function(chart, size) {
                // Adjust point sizes and styling based on screen width
                const newIsMobile = size.width < 768;
                const isWideScreen = size.width >= 1400;
                const isUltraWideScreen = size.width >= 2200;
                
                chart.data.datasets.forEach(dataset => {
                    // Smaller points on mobile, larger on wide screens
                    dataset.pointRadius = newIsMobile ? 2 : (isUltraWideScreen ? 4 : (isWideScreen ? 3.5 : 3));
                    dataset.pointHoverRadius = newIsMobile ? 4 : (isUltraWideScreen ? 7 : (isWideScreen ? 6 : 5));
                    dataset.borderWidth = newIsMobile ? 1.5 : (isUltraWideScreen ? 2.5 : (isWideScreen ? 2.2 : 2));
                    
                    // Adjust line tension for better visualization on wide screens
                    dataset.tension = isWideScreen ? 0.3 : 0.2;
                });
                
                // Update chart to reflect the changes
                chart.update('none'); // Update without animation for better performance
            },
            layout: {
                padding: {
                    left: 15,
                    right: 25,
                    top: 30,
                    bottom: 15
                },
                autoPadding: true
            },
            scales: {
                y: {
                    beginAtZero: false,
                    title: {
                        display: true,
                        text: label,
                        font: {
                            size: isMobile ? 10 : 12,
                            weight: 'bold'
                        },
                        padding: {bottom: 10, top: 10}
                    },
                    ticks: {
                        // Add padding so that points near the top or bottom are visible
                        padding: isMobile ? 8 : 12,
                        font: {
                            size: isMobile ? 9 : 11
                        },
                        maxTicksLimit: isMobile ? 5 : 8, // Limit number of ticks on mobile
                        precision: 1 // Limit decimal places
                    },
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Time',
                        font: {
                            weight: 'bold'
                        },
                        padding: {top: 15, bottom: 10}
                    },
                    grid: {
                        display: true,
                        color: 'rgba(0, 0, 0, 0.05)' // Light grid lines
                    },
                    ticks: {
                        // For better readability on mobile
                        maxRotation: isMobile ? 45 : 30, // Allow some rotation for better spacing
                        minRotation: 0,
                        padding: isMobile ? 8 : 15, // More padding between labels
                        font: {
                            size: isMobile ? 10 : 12,
                            weight: isUltraWideScreen ? 'bold' : 'normal'
                        },
                        maxTicksLimit: isMobile ? 5 : (isUltraWideScreen ? 16 : (isWideScreen ? 12 : 8)), // Adjusted to show more dates on wider screens
                        autoSkip: true,
                        align: 'inner',
                        callback: function(value, index, values) {
                            // Format dates to Manila timezone (24-hour). Labels are ISO strings.
                            if (typeof value === 'string' && value.includes('-')) {
                                try {
                                    const date = new Date(value);
                                    if (!isNaN(date.getTime())) {
                                        const chartDays = chartTimePeriod || 1;

                                        if (chartDays >= 7) {
                                            // For weekly+ data, show month/day in Manila tz
                                            const parts = formatManila(date, false).split(',')[0] || formatManila(date, true);
                                            // show M/D
                                            return `${date.getMonth()+1}/${date.getDate()}`;
                                        } else if (chartDays > 1) {
                                            // For multi-day data, show day and time in Manila tz
                                            return `${date.getDate()}/${date.getMonth()+1} ${formatManila(date, false)}`;
                                        } else {
                                            // For single day data, show just the Manila time (24h)
                                            return formatManila(date, false);
                                        }
                                    }
                                } catch (e) {
                                    console.warn('Date parsing error:', e);
                                }

                                const parts = value.split(' ');
                                if (parts.length === 2) {
                                    return parts[1];
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
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.7)',
                    titleFont: {
                        size: isMobile ? 12 : 14
                    },
                    bodyFont: {
                        size: isMobile ? 11 : 13
                    },
                    padding: isMobile ? 8 : 10,
                    displayColors: true,
                    caretSize: isMobile ? 4 : 5,
                    callbacks: {
                        title: function(items) {
                            if (!items || items.length === 0) return '';
                            const item = items[0];
                            let date = null;

                            // Prefer parsed.x when available (numeric timestamp provided by Chart.js)
                            try {
                                if (item.parsed && item.parsed.x) {
                                    date = new Date(item.parsed.x);
                                }
                            } catch (e) {
                                // ignore
                            }

                            // Fall back to the label string (ISO timestamp)
                            if ((!date || isNaN(date.getTime())) && item.label) {
                                try {
                                    date = new Date(item.label);
                                } catch (e) {
                                    date = null;
                                }
                            }

                            if (date && !isNaN(date.getTime())) {
                                return formatManila(date, chartTimePeriod !== 1);
                            }

                            // Final fallback
                            return item.label || '';
                        }
                    }
                },
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: isMobile ? 10 : 15,
                        boxWidth: isMobile ? 8 : 10,
                        font: {
                            size: isMobile ? 10 : 12
                        }
                    }
                },
                zoom: {
                    limits: {
                        y: {min: 'original', max: 'original', minRange: 1}
                    },
                    pan: {
                        enabled: true,
                        mode: 'xy',
                        threshold: 10
                    },
                    zoom: {
                        wheel: {
                            enabled: true,
                        },
                        pinch: {
                            enabled: true
                        },
                        drag: {
                            enabled: true,
                            backgroundColor: 'rgba(0, 100, 200, 0.1)'
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
}

/**
 * Load chart data from API based on sensor type
 */
function loadChartData(sensorType) {
    // Determine which chart to update
    let chart;
    switch (sensorType) {
        case 'temperature':
            chart = temperatureChart;
            break;
        case 'rainfall':
            chart = rainfallChart;
            break;
        case 'water_level':
            chart = waterLevelChart;
            break;
        default:
            console.error('Unknown sensor type:', sensorType);
            return;
    }
    
    // Show loading state
    if (chart) {
        chart.data.labels = ['Loading...'];
        chart.data.datasets[0].data = [0];
        chart.update();
    }
    
    // Construct the URL with parameters
    let url = `/api/chart-data/?type=${sensorType}&days=${chartTimePeriod}`;
    
    // Add location parameters if available
    if (window.selectedMunicipality) {
        url += `&municipality_id=${window.selectedMunicipality.id}`;
        console.log(`[Chart] Adding municipality filter: ${window.selectedMunicipality.name}`);
    }
    
    if (window.selectedBarangay) {
        url += `&barangay_id=${window.selectedBarangay.id}`;
        console.log(`[Chart] Adding barangay filter: ${window.selectedBarangay.name}`);
    }
    
    console.log(`[Chart] Fetching ${sensorType} data with URL: ${url}`);
    
    // Fetch data from API with location filters
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Ensure we have valid data
            if (!data.labels || !data.values || data.labels.length === 0) {
                console.warn(`No chart data available for ${sensorType}`);
                
                // If there's a municipality filter, try fetching data without the filter
                if (window.selectedMunicipality && !window.isRetryFetch) {
                    console.log(`Retrying ${sensorType} data fetch without municipality filter as fallback`);
                    window.isRetryFetch = true;
                    let baseUrl = `/api/chart-data/?type=${sensorType}&days=${chartTimePeriod}`;
                    
                    fetch(baseUrl)
                        .then(response => response.json())
                        .then(fullData => {
                            window.isRetryFetch = false;
                            if (!fullData.labels || !fullData.values || fullData.labels.length === 0) {
                                chart.data.labels = ['No Data Available'];
                                chart.data.datasets[0].data = [0];
                            } else {
                                try {
                                    chart.data.labels = fullData.labels.map(l => {
                                        const d = new Date(l);
                                        return (!isNaN(d.getTime())) ? d.toISOString() : l;
                                    });
                                } catch (e) {
                                    chart.data.labels = fullData.labels;
                                }
                                chart.data.datasets[0].data = fullData.values;
                                console.log(`Updated ${sensorType} chart with ${fullData.labels.length} data points (using global data)`); 
                            }
                            chart.update();
                        })
                        .catch(error => {
                            window.isRetryFetch = false;
                            console.error(`Error loading full ${sensorType} chart data:`, error);
                            chart.data.labels = ['Error Loading Data'];
                            chart.data.datasets[0].data = [0];
                            chart.update();
                        });
                    return;
                }
                
                chart.data.labels = ['No Data Available'];
                chart.data.datasets[0].data = [0];
                chart.update();
                return;
            }
            
            // Update chart with new data (coerce labels to ISO when possible)
            try {
                chart.data.labels = data.labels.map(l => {
                    const d = new Date(l);
                    return (!isNaN(d.getTime())) ? d.toISOString() : l;
                });
            } catch (e) {
                chart.data.labels = data.labels;
            }
            chart.data.datasets[0].data = data.values;
            chart.update();
            
            console.log(`Updated ${sensorType} chart with ${data.labels.length} data points`);
        })
        .catch(error => {
            console.error(`Error loading ${sensorType} chart data:`, error);
            if (chart) {
                chart.data.labels = ['Error Loading Data'];
                chart.data.datasets[0].data = [0];
                chart.update();
            }
        });
}

/**
 * Export chart as image
 */
function exportChart(chartId) {
    let chart;
    
    // Get the appropriate chart object
    switch (chartId) {
        case 'temperature-chart':
            chart = temperatureChart;
            break;
        case 'rainfall-chart':
            chart = rainfallChart;
            break;
        case 'water-level-chart':
            chart = waterLevelChart;
            break;
        default:
            console.error('Unknown chart ID:', chartId);
            return;
    }
    
    if (!chart) return;
    
    // Create a temporary link for downloading
    const link = document.createElement('a');
    link.download = `${chartId}-${new Date().toISOString().slice(0, 10)}.png`;
    
    // Convert chart to data URL
    link.href = chart.toBase64Image();
    link.click();
}

/**
 * Update chart annotations with threshold markers
 */
function addThresholdAnnotation(chart, thresholdValue, label, color) {
    // If we're using Chart.js v3+, we need the annotation plugin
    if (!chart.options.plugins.annotation) {
        chart.options.plugins.annotation = {
            annotations: {}
        };
    }
    
    // Create a unique ID for this annotation
    const id = `threshold-${label.replace(/\s+/g, '-').toLowerCase()}`;
    
    // Add the horizontal line annotation
    chart.options.plugins.annotation.annotations[id] = {
        type: 'line',
        mode: 'horizontal',
        scaleID: 'y',
        value: thresholdValue,
        borderColor: color,
        borderWidth: 2,
        label: {
            backgroundColor: color,
            content: label,
            enabled: true,
            position: 'right'
        }
    };
    
    // Update the chart
    chart.update();
}

/**
 * Add historical comparison data to chart
 */
function addHistoricalComparison(chart, historicalData, label) {
    // Add a new dataset to the chart
    chart.data.datasets.push({
        label: label,
        data: historicalData.values,
        borderColor: 'rgba(128, 128, 128, 0.7)',
        backgroundColor: 'rgba(128, 128, 128, 0.1)',
        borderWidth: 1,
        borderDash: [5, 5],
        tension: 0.2,
        pointRadius: 2,
        pointHoverRadius: 4
    });
    
    // Update the chart
    chart.update();
}

/**
 * Reset chart zoom level
 */
function resetZoom(chartId) {
    let chart;
    
    switch (chartId) {
        case 'temperature-chart':
            chart = temperatureChart;
            break;
        case 'rainfall-chart':
            chart = rainfallChart;
            break;
        case 'water-level-chart':
            chart = waterLevelChart;
            break;
        default:
            return;
    }
    
    if (chart && chart.resetZoom) {
        chart.resetZoom();
    } else if (chart) {
        // For Chart.js v3+ with zoom plugin
        try {
            const zoomPlugin = Chart.registry.getPlugin('zoom');
            if (zoomPlugin) {
                zoomPlugin.resetZoom(chart);
            }
        } catch (e) {
            console.warn('Zoom plugin not detected or error resetting zoom:', e);
            // Try to reset scales to their defaults
            if (chart.options.scales) {
                chart.update();
            }
        }
    }
}


