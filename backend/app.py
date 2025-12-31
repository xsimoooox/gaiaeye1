from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import ee
import gee_service
import os

app = Flask(__name__, static_folder='../frontend', static_url_path='/')
CORS(app)

# Initialize Earth Engine
gee_service.initialize_gee()

@app.route('/')
def home():
    return "Satellite Intelligence Platform API Running. Use POST /api/analyze."

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    Endpoint to receive coordinates and return Indicator tile URL.
    Expected JSON:
    {
        "north": float, "south": float, "east": float, "west": float,
        "date_start": "YYYY-MM-DD", "date_end": "YYYY-MM-DD",
        "indicator": "NDVI" | "EVI" | "SAVI" | "NDWI" | "MNDWI" | "NDBI" | "LST" | "RAIN" | "SAR" | "ELEVATION" | "SLOPE"
    }
    """
    try:
        data = request.json
        
        # Validation
        required_fields = ['north', 'south', 'east', 'west']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing coordinates. Requires north, south, east, west."}), 400
            
        coords = {
            'north': data['north'],
            'south': data['south'],
            'east': data['east'],
            'west': data['west']
        }
        
        date_start = data.get('date_start')
        date_end = data.get('date_end')
        indicator = data.get('indicator', 'NDVI') # Default to NDVI

        tile_url = gee_service.get_indicator_layer(coords, date_start, date_end, indicator)
        
        return jsonify({
            "success": True,
            "tile_url": tile_url,
            "coords": coords,
            "indicator": indicator,
            "dates": {"start": date_start, "end": date_end}
        })

    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/dashboard_stats', methods=['POST'])
def dashboard_stats():
    """
    Agricultural Dashboard endpoint
    Expected JSON:
    {
        "north": float, "south": float, "east": float, "west": float,
        "date_start": "YYYY-MM-DD", "date_end": "YYYY-MM-DD",
        "crop_type": "wheat" | "corn" | "rice" | "soybean" (optional),
        "input_costs": float (optional, in $/hectare)
    }
    """
    try:
        data = request.json
        
        # Validation
        required_fields = ['north', 'south', 'east', 'west']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing coordinates"}), 400
            
        coords = {
            'north': data['north'],
            'south': data['south'],
            'east': data['east'],
            'west': data['west']
        }
        
        date_start = data.get('date_start')
        date_end = data.get('date_end')
        crop_type = data.get('crop_type', 'wheat')
        input_costs = data.get('input_costs', 500)  # Default $500/ha
        
        # Calculate dashboard metrics
        stats = gee_service.calculate_dashboard_metrics(
            coords, date_start, date_end, crop_type, input_costs
        )
        
        return jsonify({
            "success": True,
            "stats": stats,
            "coords": coords,
            "dates": {"start": date_start, "end": date_end}
        })
        
    except Exception as e:
        print(f"Error in dashboard: {e}")
        return jsonify({"error": str(e), "success": False}), 500


if __name__ == '__main__':
    app.run(debug=True)
