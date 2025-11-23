from flask import Flask, request, jsonify
from routing_logic import calculate_route, load_graph_and_geometry

app = Flask(__name__)

# Attempt to load data for routing when the app starts
if not load_graph_and_geometry():
    print("API will run, but routing logic is disabled due to missing data.")

@app.route('/api/route', methods=['GET'])
def get_route():
    """
    API endpoint to calculate the best route.
    Expects: /api/route?source_lat=...&source_lon=...&dest_lat=...&dest_lon=...&vehicle=...
    """
    try:
        # 1. Get query parameters
        source_lat = float(request.args.get('source_lat'))
        source_lon = float(request.args.get('source_lon'))
        dest_lat = float(request.args.get('dest_lat'))
        dest_lon = float(request.args.get('dest_lon'))
        vehicle_type = request.args.get('vehicle', 'Sedan') # Default to Sedan
        
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid or missing latitude/longitude parameters."}), 400
    
    if not vehicle_type:
         return jsonify({"error": "Missing vehicle_type parameter."}), 400

    # 2. Check if the routing module loaded data successfully
    if not calculate_route: # If the function is not defined/loaded correctly
        return jsonify({"error": "Routing engine not initialized. Check server logs."}), 500

    # 3. Calculate the route
    route_coords = calculate_route(source_lat, source_lon, dest_lat, dest_lon, vehicle_type)
    
    if not route_coords:
        return jsonify({"error": "Could not find a valid route between the points."}), 404

    # 4. Return the calculated route (list of [lat, lon] pairs)
    return jsonify({
        "status": "success",
        "route_coordinates": route_coords
    }), 200

@app.route('/', methods=['GET'])
def home():
    return "Navai Routing API is running. Use /api/route endpoint."

if __name__ == '__main__':
    # When running locally, use a fixed port (e.g., 5000)
    # The Android app will need to target this IP/Port.
    print("\n--- STARTING FLASK API ---\n")
    print("The API is running on http://127.0.0.1:5000/")
    print("Ensure this IP/Port is accessible by the Android emulator/device.")
    print("Example Call: http://127.0.0.1:5000/api/route?source_lat=12.971&source_lon=77.594&dest_lat=12.973&dest_lon=77.601&vehicle=SUV")
    app.run(debug=True, host='0.0.0.0', port=5000)