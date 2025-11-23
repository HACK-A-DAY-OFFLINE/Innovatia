"""
tomtom_incidents_ingest.py

Reads datalink_output/segments_features_enriched.csv (or segments_features.csv),
calls TomTom Traffic Incident API for the same bbox,
maps incidents to nearest road graph nodes,
and sets:
  - closed_for_construction = True   (for roadworks / construction)
  - event_blocked = True             (for closures / other major incidents)

Usage:
  python tomtom_incidents_ingest.py
"""

import os
import math
from typing import Dict, List, Tuple, Optional

import requests
import pandas as pd

# -----------------------------
# CONFIG - EDIT THIS
# -----------------------------

# 1) Your TomTom Traffic API key
# *** MANDATORY: Insert your valid TomTom API Key here ***
TOMTOM_API_KEY = "7QF9hqXNPCMJkoQNay3abAJ1H6wkVnOH"

# 2) Same bbox as datalink_pipeline.py  (minlat, minlon, maxlat, maxlon)
BBOX = (12.9680, 77.5920, 12.9820, 77.6020)

# 3) Input / Output CSVs
BASE_CSV = "datalink_output/segments_features_enriched.csv"
FALLBACK_CSV = "datalink_output/segments_features.csv"
OUTPUT_CSV = "datalink_output/segments_features_enriched_tomtom.csv"

TOMTOM_INCIDENT_URL = "https://api.tomtom.com/traffic/services/4/incidentDetails"
# -----------------------------


def haversine_meters(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on the Earth."""
    R = 6371000  # Earth's radius in meters
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def incident_type_from_icon_category(icon_cat: int, description: str) -> str:
    """Classify the incident based on TomTom iconCategory and description."""
    if icon_cat in [1, 2, 3, 4, 5, 8]:  # accident, broken-down vehicle, road closed, lane blocked, etc.
        return "event_blocked"
    elif icon_cat in [6, 12, 13]:  # road works, construction
        return "closed_for_construction"
    elif "vip" in description.lower() or "movement" in description.lower():
        return "vip_blocked"
    return "event_blocked"  # Default to general blockage


def extract_incident_points(incident: Dict) -> List[Tuple[float, float]]:
    """Extracts a list of (lat, lon) points from an incident geometry."""
    geometry = incident.get("geometry", {})
    if geometry.get("type") == "Point":
        # Coordinates are [lon, lat] in GeoJSON format
        lon, lat = geometry.get("coordinates", [0, 0])
        return [(lat, lon)]
    elif geometry.get("type") == "LineString":
        # Coordinates are [[lon1, lat1], [lon2, lat2], ...]
        coords = geometry.get("coordinates", [])
        return [(lat, lon) for lon, lat in coords]
    return []


def find_nearest_node(nodes: Dict[int, Tuple[float, float]], lat: float, lon: float) -> Optional[int]:
    """Finds the graph node ID closest to the given (lat, lon)."""
    min_dist = float('inf')
    nearest_node_id = None

    for node_id, (n_lat, n_lon) in nodes.items():
        dist = haversine_meters(lat, lon, n_lat, n_lon)
        if dist < min_dist:
            min_dist = dist
            nearest_node_id = node_id

    # Use a reasonable threshold (e.g., 50 meters) to match incidents to roads
    if min_dist < 50:
        return nearest_node_id
    return None


def build_node_table(df: pd.DataFrame) -> Dict[int, Tuple[float, float]]:
    """Builds a dictionary mapping node_id to (lat, lon)."""
    nodes = {}
    
    # Extract 'from' nodes
    from_nodes = df[['from_node', 'from_lat', 'from_lon']].drop_duplicates()
    for _, row in from_nodes.iterrows():
        nodes[row['from_node']] = (row['from_lat'], row['from_lon'])
        
    # Extract 'to' nodes (to catch all nodes)
    to_nodes = df[['to_node', 'to_lat', 'to_lon']].drop_duplicates()
    for _, row in to_nodes.iterrows():
        # Only update if not already present or if the 'to' node lat/lon is more precise (unlikely here)
        if row['to_node'] not in nodes:
             nodes[row['to_node']] = (row['to_lat'], row['to_lon'])

    return nodes


def apply_incident_to_segments(df: pd.DataFrame, node_id: int, incident_type: str):
    """Sets the incident flag to True for all segments connected to node_id."""
    
    # Segments starting at the node
    starting_mask = df['from_node'] == node_id
    
    # Segments ending at the node
    ending_mask = df['to_node'] == node_id
    
    # Combine masks
    mask = starting_mask | ending_mask
    
    # Set the appropriate flag
    if incident_type == "closed_for_construction":
        df.loc[mask, 'closed_for_construction'] = True
    elif incident_type == "vip_blocked":
        df.loc[mask, 'vip_blocked'] = True
    elif incident_type == "event_blocked":
        df.loc[mask, 'event_blocked'] = True
    # Ensure boolean columns are treated as boolean (important for CSV export)
    df['closed_for_construction'] = df['closed_for_construction'].astype(bool)
    df['vip_blocked'] = df['vip_blocked'].astype(bool)
    df['event_blocked'] = df['event_blocked'].astype(bool)


def fetch_tomtom_incidents(bbox: Tuple[float, float, float, float]) -> List[Dict]:
    """Fetches traffic incidents from the TomTom API."""
    if not TOMTOM_API_KEY:
        print("\n--- ERROR ---\nTomTom API Key is empty. Please set TOMTOM_API_KEY in the script.\n--- END ERROR ---")
        return []
        
    # bbox in TomTom API is: north, east, south, west
    # Our BBOX is: minlat, minlon, maxlat, maxlon
    north, west, south, east = bbox
    
    # Construct the bounding box string
    bbox_str = f"{north},{east},{south},{west}" 
    
    params = {
        "key": TOMTOM_API_KEY,
        "language": "en-US",
        "incidentType": "JAM,ROADCLOSURE,HAZARD,OTHER", # types of incidents
        "bbox": bbox_str
    }
    
    url = TOMTOM_INCIDENT_URL + "/?" + requests.compat.urlencode(params)
    
    print("\nAttempting to fetch TomTom incidents...")
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'incidents' in data:
                return data['incidents']
            return []
        else:
            print(f"\n--- ERROR ---\nTomTom API Request Failed.")
            print(f"Status Code: {response.status_code}")
            try:
                # Print API error message if available
                print(f"Response Body: {response.json()}")
            except:
                print(f"Response Body: {response.text}")
            print(f"URL: {url}")
            print("--- END ERROR ---")
            return []

    except requests.exceptions.RequestException as e:
        print(f"\n--- ERROR ---\nNetwork or Connection Error when fetching TomTom incidents: {e}\n--- END ERROR ---")
        return []


def main():
    
    # --- Load Data ---
    if os.path.exists(BASE_CSV):
        input_csv = BASE_CSV
    elif os.path.exists(FALLBACK_CSV):
        input_csv = FALLBACK_CSV
    else:
        print(f"Error: Neither {BASE_CSV} nor {FALLBACK_CSV} found. Run datalink_pipeline.py first.")
        return

    print(f"Loading base data from: {input_csv}")
    df = pd.read_csv(input_csv)
    
    # Initialize incident columns if they don't exist (needed if loading base segments_features.csv)
    if 'event_blocked' not in df.columns: df['event_blocked'] = False
    if 'vip_blocked' not in df.columns: df['vip_blocked'] = False
    if 'closed_for_construction' not in df.columns: df['closed_for_construction'] = False


    # 2) Build node table for nearest neighbor search
    print("Building node table...")
    nodes = build_node_table(df)
    print("Unique nodes:", len(nodes))

    # 3) Fetch incidents from TomTom
    incidents = fetch_tomtom_incidents(BBOX)
    if not incidents:
        print("No incidents or API error, saving copy as:", OUTPUT_CSV)
        df.to_csv(OUTPUT_CSV, index=False)
        print("Done.")
        return

    # 4) Map incidents to graph
    print(f"Successfully fetched {len(incidents)} TomTom incidents.")
    
    incidents_applied_count = 0
    for inc in incidents:
        props = inc.get("properties", {})
        icon_cat = props.get("iconCategory", 0)
        desc = props.get("description", "")

        itype = incident_type_from_icon_category(icon_cat, desc)
        pts = extract_incident_points(inc)
        if not pts:
            continue

        print("\nIncident:", desc or "(no description)")
        print(" iconCategory:", icon_cat, "-> type:", itype)

        # use middle point of geometry for nearest node calculation
        mid_idx = len(pts) // 2
        lat, lon = pts[mid_idx]
        print(f" approx point: ({lat:.5f}, {lon:.5f})")

        nid = find_nearest_node(nodes, lat, lon)
        if not nid:
            print("  -> No nearest node found (closest point > 50m), skipping.")
            continue

        print("  -> Nearest graph node:", nid)
        apply_incident_to_segments(df, nid, itype)
        incidents_applied_count += 1
        print("  -> Applied incident flags to connected segments.")


    print(f"\nSuccessfully applied {incidents_applied_count} incidents to the graph data.")
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Final enriched data saved to: {OUTPUT_CSV}")
    print("Done.")

if __name__ == "__main__":
    main()