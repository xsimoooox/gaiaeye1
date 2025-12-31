// Backend API URL
const API_URL = 'http://127.0.0.1:5000/api/analyze';

// Global state
let currentIndicator = 'NDVI';
let currentCoords = null; // Store coords to re-fetch when indicator changes

// Initialize Map
const map = L.map('map', {
    zoomControl: false // Move zoom control if needed, but default is top-left which is fine
}).setView([20, 0], 3);

// Add Satellite Basemap
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri'
}).addTo(map);

// Add Labels overlay
L.tileLayer('https://stamen-tiles-{s}.a.ssl.fastly.net/toner-labels/{z}/{x}/{y}{r}.png', {
    attribution: 'Map tiles by Stamen Design, CC BY 3.0 -- Map data &copy; OpenStreetMap',
    subdomains: 'abcd',
    minZoom: 0,
    maxZoom: 20,
    ext: 'png'
}).addTo(map);

// Feature Group for Drawings
const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

// Draw Control
const drawControl = new L.Control.Draw({
    draw: {
        polygon: false,
        polyline: false,
        circle: false,
        marker: false,
        circlemarker: false,
        rectangle: {
            shapeOptions: {
                color: '#4ade80',
                weight: 2
            }
        }
    },
    edit: {
        featureGroup: drawnItems,
        remove: true
    }
});
map.addControl(drawControl);

// Store the current GEE layer
let currentLayer = null;

// ==========================================
// DATE SLIDER LOGIC
// ==========================================

// Configuration
const START_YEAR = 2021;
const startEpoch = new Date(START_YEAR, 0, 1); // Jan 1, 2021
const today = new Date();

// Calculate total months since Start Epoch
const totalMonths = (today.getFullYear() - START_YEAR) * 12 + today.getMonth();

// Initialize Slider
const timeSlider = document.getElementById('time-slider');
if (timeSlider) {
    timeSlider.min = 0;
    timeSlider.max = totalMonths;
    timeSlider.value = totalMonths; // Default to now
}

// State for selected month
let selectedDate = new Date(today.getFullYear(), today.getMonth(), 1);

function updateDateFromSlider() {
    if (!timeSlider) return;

    const monthsSinceStart = parseInt(timeSlider.value);
    const date = new Date(startEpoch);
    date.setMonth(startEpoch.getMonth() + monthsSinceStart);
    selectedDate = date;

    // Update Text Display
    const display = document.getElementById('date-display');
    if (display) {
        display.textContent = date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    }

    // Trigger Analysis (Debounced ideally, but direct for now)
    if (currentCoords) {
        fetchAnalysis();
    }
}

if (timeSlider) {
    timeSlider.addEventListener('input', updateDateFromSlider);
}

// Button Nav
const prevBtn = document.getElementById('prev-month');
if (prevBtn) {
    prevBtn.addEventListener('click', () => {
        if (timeSlider && timeSlider.value > 0) {
            timeSlider.value = parseInt(timeSlider.value) - 1;
            updateDateFromSlider();
        }
    });
}

const nextBtn = document.getElementById('next-month');
if (nextBtn) {
    nextBtn.addEventListener('click', () => {
        if (timeSlider && timeSlider.value < timeSlider.max) {
            timeSlider.value = parseInt(timeSlider.value) + 1;
            updateDateFromSlider();
        }
    });
}

// Trigger initial update to set text
updateDateFromSlider();


// ==========================================
// UI INTERACTION LOGIC
// ==========================================

// 1. Sidebar Category Selection
document.querySelectorAll('.sidebar-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.stopPropagation();

        // Update Active State
        document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');

        // Show Corresponding Sub-menu
        const cat = item.dataset.cat;
        document.querySelectorAll('.sub-menu').forEach(m => m.classList.remove('visible'));

        const targetMenu = document.getElementById(`sub-${cat}`);
        if (targetMenu) {
            targetMenu.classList.add('visible');

            // UX Improvement: Auto-select the first indicator of this category
            // This ensures clicking the icon "displays data" immediately (if area drawn)
            const firstBtn = targetMenu.querySelector('.indicator-btn');
            if (firstBtn) {
                firstBtn.click();
            }
        }
    });
});

// 2. Hide Sub-menus when clicking map or outside
document.addEventListener('click', (e) => {
    const isSidebar = e.target.closest('.sidebar');
    const isSubMenu = e.target.closest('.sub-menu');

    if (!isSidebar && !isSubMenu) {
        document.querySelectorAll('.sub-menu').forEach(m => m.classList.remove('visible'));
        document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
    }
});


// 3. Indicator Selection
document.querySelectorAll('.indicator-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent closing menu immediately on selection

        // Update UI
        document.querySelectorAll('.indicator-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update State
        currentIndicator = btn.dataset.ind;

        // Trigger Analysis
        if (currentCoords) {
            fetchAnalysis();
        } else {
            const statusMsg = document.getElementById('status-msg');
            if (statusMsg) {
                statusMsg.textContent = "⚠️ Please draw an area on the map first.";
                statusMsg.className = 'status-text error';
            }
        }
    });
});

// 4. Update Button Logic (Deprecated but keep for compatibility if element exists?)
// We removed update-btn in index.html in favor of Slider. 
// But if it were there:
const updateBtn = document.getElementById('update-btn');
if (updateBtn) {
    updateBtn.addEventListener('click', () => {
        if (currentCoords) {
            fetchAnalysis();
        } else {
            alert("Please draw a region on the map first.");
        }
    });
}


// ==========================================
// CORE ANALYSIS LOGIC
// ==========================================

// Handle Draw Created Event
map.on(L.Draw.Event.CREATED, function (e) {
    const layer = e.layer;
    drawnItems.clearLayers();
    if (currentLayer) map.removeLayer(currentLayer);
    drawnItems.addLayer(layer);

    const bounds = layer.getBounds();
    currentCoords = {
        north: bounds.getNorth(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        west: bounds.getWest()
    };

    fetchAnalysis();
});

async function fetchAnalysis() {
    if (!currentCoords) return;

    const statusMsg = document.getElementById('status-msg');

    // Calculate First and Last Day of selected month
    const year = selectedDate.getFullYear();
    const month = selectedDate.getMonth();

    const firstDay = new Date(year, month, 1);

    // Last day: Using new Date(year, month + 1, 0) gives the last day of 'month'
    const lastDay = new Date(year, month + 1, 0);

    const formatDate = (d) => {
        // Adjust for timezone offset to ensure we get YYYY-MM-DD correctly
        const offset = d.getTimezoneOffset();
        const adjustedDate = new Date(d.getTime() - (offset * 60 * 1000));
        return adjustedDate.toISOString().split('T')[0];
    };

    const payload = {
        ...currentCoords,
        date_start: formatDate(firstDay),
        date_end: formatDate(lastDay),
        indicator: currentIndicator
    };

    if (statusMsg) {
        statusMsg.className = 'status-text loading';
        statusMsg.textContent = `Computing ${currentIndicator} for ${firstDay.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}...`;
    }

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) throw new Error(data.error || 'Server Error');

        if (data.success && data.tile_url) {
            updateLayer(data.tile_url);
            if (statusMsg) {
                statusMsg.className = 'status-text success';
                statusMsg.textContent = `${currentIndicator} Loaded.`;
            }
        } else {
            throw new Error('Invalid response from server');
        }

    } catch (error) {
        console.error('Error:', error);
        if (statusMsg) {
            statusMsg.className = 'status-text error';
            statusMsg.textContent = `Error: ${error.message}`;
        }
    }
}

function updateLayer(tileUrlFormat) {
    if (currentLayer) {
        map.removeLayer(currentLayer);
    }

    currentLayer = L.tileLayer(tileUrlFormat, {
        attribution: `Google Earth Engine`,
        opacity: 0.8
    }).addTo(map);
}

// ==========================================
// AGRICULTURAL DASHBOARD LOGIC
// ==========================================

const dashboardOverlay = document.getElementById('agri-dashboard');
const dashboardToggle = document.getElementById('dashboard-toggle');
const closeDashboard = document.getElementById('close-dashboard');
const calculateDashboard = document.getElementById('calculate-dashboard');

// Toggle Dashboard
if (dashboardToggle) {
    dashboardToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!currentCoords) {
            alert("Please draw an area on the map first to view agricultural metrics.");
            return;
        }
        dashboardOverlay.classList.remove('hidden');
    });
}

// Close Dashboard
if (closeDashboard) {
    closeDashboard.addEventListener('click', () => {
        dashboardOverlay.classList.add('hidden');
    });
}

// Calculate Dashboard Metrics
if (calculateDashboard) {
    calculateDashboard.addEventListener('click', async () => {
        if (!currentCoords) {
            alert("Please draw an area on the map first.");
            return;
        }

        const cropType = document.getElementById('crop-type').value;
        const inputCosts = parseFloat(document.getElementById('input-costs').value);

        // Calculate dates (last 90 days for better analysis)
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(endDate.getDate() - 90);

        const formatDate = (d) => {
            const offset = d.getTimezoneOffset();
            const adjustedDate = new Date(d.getTime() - (offset * 60 * 1000));
            return adjustedDate.toISOString().split('T')[0];
        };

        const payload = {
            ...currentCoords,
            date_start: formatDate(startDate),
            date_end: formatDate(endDate),
            crop_type: cropType,
            input_costs: inputCosts
        };

        // Show loading state
        calculateDashboard.textContent = 'Calculating...';
        calculateDashboard.disabled = true;

        try {
            const response = await fetch('http://127.0.0.1:5000/api/dashboard_stats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok) throw new Error(data.error || 'Server Error');

            if (data.success && data.stats) {
                updateDashboardUI(data.stats);
            } else {
                throw new Error('Invalid response from server');
            }

        } catch (error) {
            console.error('Dashboard Error:', error);
            alert(`Error calculating metrics: ${error.message}`);
        } finally {
            calculateDashboard.textContent = 'Calculate Metrics';
            calculateDashboard.disabled = false;
        }
    });
}

function updateDashboardUI(stats) {
    // Productivity
    const prod = stats.productivity_index;
    document.getElementById('productivity-ndvi').textContent = prod.mean_ndvi;
    document.getElementById('productivity-status').textContent = prod.health_status.toUpperCase();
    document.getElementById('productivity-yield').textContent = `Expected: ${prod.expected_yield_tons_ha} tons/ha`;

    // Apply health color
    const prodValue = document.getElementById('productivity-ndvi');
    prodValue.className = 'metric-value health-' + prod.health_status;

    // Financial
    const fin = stats.financial;
    document.getElementById('financial-profit').textContent = `$${fin.net_profit_usd.toLocaleString()}`;
    document.getElementById('financial-roi').textContent = `ROI: ${fin.roi_percent}%`;
    document.getElementById('financial-revenue').textContent = `Revenue: $${fin.expected_revenue_usd.toLocaleString()}`;

    // Weather Risk
    const weather = stats.weather_risk;
    document.getElementById('weather-risk').textContent = weather.overall_risk.toUpperCase();
    document.getElementById('weather-temp').textContent = `Temp: ${weather.avg_temperature_c}°C`;
    document.getElementById('weather-rain').textContent = `Rain: ${weather.total_rainfall_mm} mm`;

    const weatherValue = document.getElementById('weather-risk');
    weatherValue.className = 'metric-value risk-' + weather.overall_risk;

    // Pest Risk
    const pest = stats.pest_risk;
    document.getElementById('pest-risk').textContent = pest.risk_level.toUpperCase();
    document.getElementById('pest-recommendation').textContent = pest.recommendation;

    const pestValue = document.getElementById('pest-risk');
    pestValue.className = 'metric-value risk-' + pest.risk_level;

    // Soil Health
    const soil = stats.soil_health;
    document.getElementById('soil-health').textContent = soil.health_status.toUpperCase();
    document.getElementById('soil-nitrogen').textContent = `N: ${soil.nitrogen_status}`;
    document.getElementById('soil-moisture').textContent = `Moisture: ${soil.moisture_index}`;

    const soilValue = document.getElementById('soil-health');
    soilValue.className = 'metric-value health-' + soil.health_status;

    // Irrigation
    const irrig = stats.irrigation;
    document.getElementById('irrigation-urgency').textContent = irrig.urgency.toUpperCase();
    document.getElementById('irrigation-frequency').textContent = irrig.recommended_frequency;
    document.getElementById('irrigation-amount').textContent = `${irrig.amount_per_session_mm} mm/session`;

    const irrigValue = document.getElementById('irrigation-urgency');
    irrigValue.className = 'metric-value risk-' + irrig.urgency;

    // Fertilization
    const fert = stats.fertilization;
    document.getElementById('fert-n').textContent = `${fert.nitrogen_kg_ha} kg/ha`;
    document.getElementById('fert-p').textContent = `${fert.phosphorus_kg_ha} kg/ha`;
    document.getElementById('fert-k').textContent = `${fert.potassium_kg_ha} kg/ha`;
    document.getElementById('fert-priority').textContent = fert.priority.toUpperCase();

    // Plot Info
    document.getElementById('plot-area').textContent = stats.area_hectares;
    document.getElementById('plot-crop').textContent = stats.crop_type.charAt(0).toUpperCase() + stats.crop_type.slice(1);
}

