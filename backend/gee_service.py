import ee
import datetime

# ==========================================
# CONFIGURATION
# ==========================================
GEE_PROJECT_ID = 'ee-mohamed-projet' 

INDICATORS_CONFIG = {
    # --- VEGETATION & AGRI (Sentinel-2) ---
    'NDVI': {'type': 'S2', 'name': 'NDVI (Vegetation)', 'vis': {'min': 0, 'max': 0.8, 'palette': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']}},
    'EVI':  {'type': 'S2', 'name': 'EVI (Enhanced Veg)', 'vis': {'min': 0, 'max': 0.8, 'palette': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']}},
    'SAVI': {'type': 'S2', 'name': 'SAVI (Soil Adjusted)', 'vis': {'min': 0, 'max': 0.8, 'palette': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']}},
    'LAI':  {'type': 'S2', 'name': 'LAI (Leaf Area)', 'vis': {'min': 0, 'max': 3, 'palette': ['white', 'green']}}, 
    
    # --- WATER (Sentinel-2 & JRC) ---
    'NDWI': {'type': 'S2', 'name': 'NDWI (Water)', 'vis': {'min': -0.5, 'max': 0.5, 'palette': ['#ffffff', '#deebf7', '#9ecae1', '#3182bd', '#08519c']}},
    'MNDWI':{'type': 'S2', 'name': 'MNDWI (Urban Water)', 'vis': {'min': -0.5, 'max': 0.5, 'palette': ['#ffffff', '#deebf7', '#9ecae1', '#3182bd', '#08519c']}},
    
    # --- URBAN (Sentinel-2) ---
    'NDBI': {'type': 'S2', 'name': 'NDBI (Built-up)', 'vis': {'min': -0.5, 'max': 0.5, 'palette': ['#2c003e', '#67008f', '#a900ba', '#e65c9e', '#ffaf7d', '#fff6a3']}},

    # --- CLIMATE (MODIS & CHIRPS) ---
    'LST':  {'type': 'MODIS', 'name': 'Land Surface Temp (C)', 'vis': {'min': 10, 'max': 45, 'palette': ['blue', 'yellow', 'red']}},
    'RAIN': {'type': 'CHIRPS', 'name': 'Total Rainfall (mm)', 'vis': {'min': 0, 'max': 300, 'palette': ['#ffffe5', '#f7fcb9', '#addd8e', '#41ab5d', '#238443', '#005a32']}},

    # --- TERRAIN (NASADEM) ---
    'ELEVATION': {'type': 'DEM', 'name': 'Elevation (m)', 'vis': {'min': 0, 'max': 2000, 'palette': ['006600', '002200', 'fff700', 'ab7634', 'c4d0ff', 'ffffff']}},
    'SLOPE':     {'type': 'DEM', 'name': 'Slope (deg)', 'vis': {'min': 0, 'max': 60, 'palette': ['black', 'white']}},

    # --- RADAR / FLOOD (Sentinel-1) ---
    'SAR':  {'type': 'S1', 'name': 'SAR Radar (VV)', 'vis': {'min': -25, 'max': 0, 'palette': ['black', 'white']}},
}

def initialize_gee():
    try:
        if GEE_PROJECT_ID and GEE_PROJECT_ID != 'your-project-id-here':
            print(f"Initializing GEE with project: {GEE_PROJECT_ID}")
            ee.Initialize(project=GEE_PROJECT_ID)
        else:
            ee.Initialize()
    except Exception as e:
        print(f"GEE Initialization failed: {e}")
        try:
            ee.Authenticate()
            ee.Initialize()
        except Exception as e2:
            raise RuntimeError(f"Auth failed: {e2}")

def get_indicator_layer(coords, date_start=None, date_end=None, indicator='NDVI'):
    roi = ee.Geometry.Rectangle([coords['west'], coords['south'], coords['east'], coords['north']])
    
    if not date_end: date_end = datetime.date.today().strftime('%Y-%m-%d')
    if not date_start: date_start = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')

    indicator = indicator.upper()
    config = INDICATORS_CONFIG.get(indicator, INDICATORS_CONFIG['NDVI'])
    dtype = config['type']
    
    print(f"Processing {indicator} ({dtype}) from {date_start} to {date_end}")

    image = None

    if dtype == 'S2':
        image = get_sentinel2_image(roi, date_start, date_end, indicator)
    elif dtype == 'S1':
        image = get_sentinel1_image(roi, date_start, date_end)
    elif dtype == 'MODIS':
        image = get_modis_image(roi, date_start, date_end)
    elif dtype == 'CHIRPS':
        image = get_chirps_image(roi, date_start, date_end)
    elif dtype == 'DEM':
        image = get_dem_image(roi)

    if not image:
        raise ValueError("Could not generate image")

    # Clip and Visualize
    image = image.clip(roi)
    map_id = ee.Image(image).getMapId(config['vis'])
    return map_id['tile_fetcher'].url_format

# --- DATA SOURCE HANDLERS ---

def get_sentinel2_image(roi, start, end, indicator):
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
           .filterBounds(roi) \
           .filterDate(start, end) \
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
           .map(mask_s2_clouds)
    
    composite = s2.median()
    
    if indicator == 'NDVI': return composite.normalizedDifference(['B8', 'B4'])
    if indicator == 'NDWI': return composite.normalizedDifference(['B3', 'B8'])
    if indicator == 'MNDWI': return composite.normalizedDifference(['B3', 'B11'])
    if indicator == 'NDBI': return composite.normalizedDifference(['B11', 'B8'])
    if indicator == 'LAI': return composite.normalizedDifference(['B8', 'B4']).multiply(3) # Simple proxy
    if indicator == 'EVI':
        return composite.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
            {'NIR': composite.select('B8'), 'RED': composite.select('B4'), 'BLUE': composite.select('B2')}
        )
    if indicator == 'SAVI':
        return composite.expression(
           '((NIR - RED) / (NIR + RED + 0.5)) * 1.5',
           {'NIR': composite.select('B8'), 'RED': composite.select('B4')}
        )
    return composite.select(['B4', 'B3', 'B2']) 

def get_sentinel1_image(roi, start, end):
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD') \
           .filterBounds(roi) \
           .filterDate(start, end) \
           .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
           .filter(ee.Filter.eq('instrumentMode', 'IW'))
    return s1.select('VV').mean()

def get_modis_image(roi, start, end):
    modis = ee.ImageCollection('MODIS/006/MOD11A2') \
              .filterBounds(roi) \
              .filterDate(start, end)
    def to_celsius(img):
        return img.select('LST_Day_1km').multiply(0.02).subtract(273.15)
    return modis.map(to_celsius).mean()

def get_chirps_image(roi, start, end):
    chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/PENTAD') \
               .filterBounds(roi) \
               .filterDate(start, end)
    return chirps.select('precipitation').sum()

def get_dem_image(roi):
    dem = ee.Image("NASA/NASADEM_HGT/001").select('elevation')
    return dem 

def mask_s2_clouds(image):
    qa = image.select('QA60')
    mask = qa.bitwiseAnd(1<<10).eq(0).And(qa.bitwiseAnd(1<<11).eq(0))
    return image.updateMask(mask).divide(10000)

# ==========================================
# AGRICULTURAL DASHBOARD FUNCTIONS
# ==========================================

# Crop yield coefficients (tons/hectare at optimal NDVI)
CROP_YIELDS = {
    'wheat': {'base_yield': 5.5, 'price_per_ton': 250},
    'corn': {'base_yield': 9.5, 'price_per_ton': 200},
    'rice': {'base_yield': 6.0, 'price_per_ton': 400},
    'soybean': {'base_yield': 3.2, 'price_per_ton': 450}
}

def calculate_dashboard_metrics(coords, date_start, date_end, crop_type, input_costs):
    """
    Calculate comprehensive agricultural metrics from GEE data
    """
    roi = ee.Geometry.Rectangle([coords['west'], coords['south'], coords['east'], coords['north']])
    
    if not date_end: date_end = datetime.date.today().strftime('%Y-%m-%d')
    if not date_start: date_start = (datetime.date.today() - datetime.timedelta(days=90)).strftime('%Y-%m-%d')
    
    # Calculate area in hectares
    area_m2 = roi.area().getInfo()
    area_ha = area_m2 / 10000
    
    # 1. Productivity Index (based on NDVI integral)
    productivity = calculate_productivity_index(roi, date_start, date_end, crop_type)
    
    # 2. Weather Risk Analysis
    weather_risk = calculate_weather_risk(roi, date_start, date_end)
    
    # 3. Pest Risk (based on temperature and humidity proxies)
    pest_risk = calculate_pest_risk(roi, date_start, date_end)
    
    # 4. Soil Health Proxies
    soil_health = calculate_soil_proxies(roi)
    
    # 5. Financial Analysis
    financial = calculate_financial_metrics(
        productivity, area_ha, crop_type, input_costs
    )
    
    # 6. Irrigation Recommendations
    irrigation = calculate_irrigation_needs(roi, date_start, date_end, weather_risk)
    
    # 7. Fertilization Recommendations
    fertilization = generate_fertilization_recommendations(soil_health, productivity)
    
    return {
        'area_hectares': round(area_ha, 2),
        'productivity_index': productivity,
        'weather_risk': weather_risk,
        'pest_risk': pest_risk,
        'soil_health': soil_health,
        'financial': financial,
        'irrigation': irrigation,
        'fertilization': fertilization,
        'crop_type': crop_type
    }

def calculate_productivity_index(roi, start, end, crop_type):
    """Calculate expected yield based on NDVI time series"""
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
           .filterBounds(roi) \
           .filterDate(start, end) \
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
           .map(mask_s2_clouds)
    
    # Calculate NDVI time series
    def calc_ndvi(img):
        return img.normalizedDifference(['B8', 'B4']).rename('NDVI')
    
    ndvi_collection = s2.map(calc_ndvi)
    
    # Get mean NDVI
    mean_ndvi = ndvi_collection.mean().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=10,
        maxPixels=1e9
    ).getInfo()
    
    ndvi_value = mean_ndvi.get('NDVI', 0.5)
    
    # Calculate yield estimate
    crop_params = CROP_YIELDS.get(crop_type, CROP_YIELDS['wheat'])
    
    # NDVI to yield conversion (simplified model)
    # Optimal NDVI range: 0.6-0.8
    if ndvi_value < 0.3:
        yield_factor = 0.3
    elif ndvi_value < 0.5:
        yield_factor = 0.6
    elif ndvi_value < 0.7:
        yield_factor = 0.85
    else:
        yield_factor = 1.0
    
    expected_yield = crop_params['base_yield'] * yield_factor
    
    return {
        'mean_ndvi': round(ndvi_value, 3),
        'health_status': get_health_status(ndvi_value),
        'expected_yield_tons_ha': round(expected_yield, 2),
        'yield_factor': round(yield_factor, 2)
    }

def calculate_weather_risk(roi, start, end):
    """Analyze weather patterns for risk assessment"""
    # Temperature analysis (MODIS LST)
    modis = ee.ImageCollection('MODIS/006/MOD11A2') \
              .filterBounds(roi) \
              .filterDate(start, end)
    
    def to_celsius(img):
        return img.select('LST_Day_1km').multiply(0.02).subtract(273.15)
    
    temp_stats = modis.map(to_celsius).reduce(ee.Reducer.mean().combine(
        ee.Reducer.max(), '', True
    )).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=1000,
        maxPixels=1e9
    ).getInfo()
    
    # Rainfall analysis (CHIRPS)
    chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/PENTAD') \
               .filterBounds(roi) \
               .filterDate(start, end)
    
    rain_stats = chirps.select('precipitation').reduce(
        ee.Reducer.sum().combine(ee.Reducer.mean(), '', True)
    ).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=5000,
        maxPixels=1e9
    ).getInfo()
    
    avg_temp = temp_stats.get('LST_Day_1km_mean', 25)
    max_temp = temp_stats.get('LST_Day_1km_max', 30)
    total_rain = rain_stats.get('precipitation_sum', 100)
    
    # Risk scoring
    temp_risk = 'high' if max_temp > 35 or avg_temp < 10 else 'low'
    rain_risk = 'high' if total_rain < 50 or total_rain > 500 else 'low'
    
    overall_risk = 'high' if temp_risk == 'high' or rain_risk == 'high' else 'moderate'
    
    return {
        'avg_temperature_c': round(avg_temp, 1),
        'max_temperature_c': round(max_temp, 1),
        'total_rainfall_mm': round(total_rain, 1),
        'temperature_risk': temp_risk,
        'rainfall_risk': rain_risk,
        'overall_risk': overall_risk
    }

def calculate_pest_risk(roi, start, end):
    """Estimate pest risk based on environmental conditions"""
    # Use temperature and humidity proxies
    modis = ee.ImageCollection('MODIS/006/MOD11A2') \
              .filterBounds(roi) \
              .filterDate(start, end)
    
    temp_mean = modis.select('LST_Day_1km').mean().multiply(0.02).subtract(273.15) \
                     .reduceRegion(
                         reducer=ee.Reducer.mean(),
                         geometry=roi,
                         scale=1000,
                         maxPixels=1e9
                     ).getInfo()
    
    temp = temp_mean.get('LST_Day_1km', 20)
    
    # Pest risk increases with temperature (20-30°C optimal for many pests)
    if 20 <= temp <= 30:
        risk_score = 0.7
        risk_level = 'high'
    elif 15 <= temp <= 35:
        risk_score = 0.4
        risk_level = 'moderate'
    else:
        risk_score = 0.2
        risk_level = 'low'
    
    return {
        'risk_score': round(risk_score, 2),
        'risk_level': risk_level,
        'avg_temperature_c': round(temp, 1),
        'recommendation': get_pest_recommendation(risk_level)
    }

def calculate_soil_proxies(roi):
    """Estimate soil properties using satellite proxies"""
    # Use Sentinel-2 bands as soil proxies
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
           .filterBounds(roi) \
           .filterDate(datetime.date.today() - datetime.timedelta(days=60), datetime.date.today()) \
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)) \
           .map(mask_s2_clouds) \
           .median()
    
    # Calculate soil indices
    # NDMI (moisture)
    ndmi = s2.normalizedDifference(['B8', 'B11'])
    
    stats = ndmi.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=10,
        maxPixels=1e9
    ).getInfo()
    
    moisture_index = stats.get('nd', 0.3)
    
    # Classify soil health
    if moisture_index > 0.4:
        health = 'good'
        nitrogen_status = 'adequate'
    elif moisture_index > 0.2:
        health = 'moderate'
        nitrogen_status = 'low'
    else:
        health = 'poor'
        nitrogen_status = 'deficient'
    
    return {
        'moisture_index': round(moisture_index, 3),
        'health_status': health,
        'nitrogen_status': nitrogen_status,
        'organic_matter': 'moderate'  # Placeholder - would need specific data
    }

def calculate_financial_metrics(productivity, area_ha, crop_type, input_costs):
    """Calculate cost/benefit analysis"""
    crop_params = CROP_YIELDS.get(crop_type, CROP_YIELDS['wheat'])
    
    expected_yield_total = productivity['expected_yield_tons_ha'] * area_ha
    expected_revenue = expected_yield_total * crop_params['price_per_ton']
    total_costs = input_costs * area_ha
    net_profit = expected_revenue - total_costs
    roi = (net_profit / total_costs * 100) if total_costs > 0 else 0
    
    return {
        'expected_yield_total_tons': round(expected_yield_total, 2),
        'expected_revenue_usd': round(expected_revenue, 2),
        'total_input_costs_usd': round(total_costs, 2),
        'net_profit_usd': round(net_profit, 2),
        'roi_percent': round(roi, 1),
        'price_per_ton_usd': crop_params['price_per_ton']
    }

def calculate_irrigation_needs(roi, start, end, weather_risk):
    """Generate irrigation recommendations"""
    total_rain = weather_risk['total_rainfall_mm']
    avg_temp = weather_risk['avg_temperature_c']
    
    # Simple irrigation model
    if total_rain < 50:
        urgency = 'high'
        frequency = 'daily'
        amount_mm = 10
    elif total_rain < 100:
        urgency = 'moderate'
        frequency = 'every 2-3 days'
        amount_mm = 7
    else:
        urgency = 'low'
        frequency = 'weekly'
        amount_mm = 5
    
    return {
        'urgency': urgency,
        'recommended_frequency': frequency,
        'amount_per_session_mm': amount_mm,
        'next_irrigation': 'within 24h' if urgency == 'high' else 'within 3 days'
    }

def generate_fertilization_recommendations(soil_health, productivity):
    """Generate precision fertilization recommendations"""
    nitrogen_status = soil_health['nitrogen_status']
    ndvi = productivity['mean_ndvi']
    
    if nitrogen_status == 'deficient' or ndvi < 0.4:
        n_kg_ha = 120
        p_kg_ha = 60
        k_kg_ha = 80
        priority = 'high'
    elif nitrogen_status == 'low' or ndvi < 0.6:
        n_kg_ha = 80
        p_kg_ha = 40
        k_kg_ha = 50
        priority = 'moderate'
    else:
        n_kg_ha = 40
        p_kg_ha = 20
        k_kg_ha = 30
        priority = 'low'
    
    return {
        'nitrogen_kg_ha': n_kg_ha,
        'phosphorus_kg_ha': p_kg_ha,
        'potassium_kg_ha': k_kg_ha,
        'priority': priority,
        'application_method': 'split application recommended',
        'timing': 'apply before next growth stage'
    }

def get_health_status(ndvi):
    """Convert NDVI to health status"""
    if ndvi > 0.7:
        return 'excellent'
    elif ndvi > 0.5:
        return 'good'
    elif ndvi > 0.3:
        return 'moderate'
    else:
        return 'poor'

def get_pest_recommendation(risk_level):
    """Get pest management recommendation"""
    if risk_level == 'high':
        return 'Implement immediate monitoring and consider preventive treatment'
    elif risk_level == 'moderate':
        return 'Regular monitoring recommended'
    else:
        return 'Continue routine observation'

