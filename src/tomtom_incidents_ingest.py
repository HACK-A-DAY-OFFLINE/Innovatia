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
TOMTOM_API_KEY = "7QF9hqXNPCMJkoQNay3abAJ1H6wkVnOH"      # <-- put your key here

# 2) Same bbox as datalink_pipeline.py  (minlat, minlon, maxlat, maxlon)
BBOX = (12.9680, 77.5920, 12.9820, 77.6020)

# 3) Input / Output CSVs
BASE_CSV = "datalink_output/segments_features_enriched.csv"
FALLBACK_CSV = "datalink_output/segments_features.csv"
OUTPUT_CSV = "datalink_output/segments_features_enriched_tomtom.csv"

# 4) TomTom Incident Details endpoint
#    v5 Incident Details service (s3 = "combined" source)
TOMTOM_INCIDENT_URL = "https://api.tomtom.com/traffic/services/5/incidentDetails"

# -----------------------------
# Basic geo helpers
# -----------------------------

def haversine_meters(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

# -----------------------------
# Dataframe → node table
# -----------------------------

def build_node_table(df: pd.DataFrame) -> Dict[str, Tuple[float, float]]:
    """
    Build dict: node_id -> (lat, lon) from from_node / to_node.
    Node IDs are strings like '12.9716_77.5946'.
    """
    nodes: Dict[str, Tuple[float, float]] = {}

    def parse_node(nid: str) -> Tuple[float, float]:
        lat_str, lon_str = nid.split("_")
        return float(lat_str), float(lon_str)

    for col in ["from_node", "to_node"]:
        if col not in df.columns:
            continue
        for nid in df[col].unique():
            if nid not in nodes:
                try:
                    nodes[nid] = parse_node(nid)
                except Exception:
                    continue
    return nodes

def find_nearest_node(nodes: Dict[str, Tuple[float, float]],
                      lat: float,
                      lon: float) -> Optional[str]:
    best_id = None
    best_d = float("inf")
    for nid, (nlat, nlon) in nodes.items():
        d = haversine_meters(lat, lon, nlat, nlon)
        if d < best_d:
            best_d = d
            best_id = nid
    return best_id

# -----------------------------
# Apply incident flags to segments
# -----------------------------

def apply_incident_to_segments(df: pd.DataFrame,
                               node_id: str,
                               incident_type: str) -> None:
    """
    incident_type: "roadworks" / "closure" / "other"
    """
    mask = (df["from_node"] == node_id) | (df["to_node"] == node_id)
    if not mask.any():
        return

    # Ensure columns exist
    if "event_blocked" not in df.columns:
        df["event_blocked"] = False
    if "vip_blocked" not in df.columns:
        df["vip_blocked"] = False
    if "closed_for_construction" not in df.columns:
        df["closed_for_construction"] = False

    if incident_type == "roadworks":
        df.loc[mask, "closed_for_construction"] = True
    elif incident_type == "closure":
        df.loc[mask, "event_blocked"] = True
    else:
        # generic major incident → treat as event_blocked for now
        df.loc[mask, "event_blocked"] = True

# -----------------------------
# TomTom Incident API helpers
# -----------------------------

def fetch_tomtom_incidents(bbox: Tuple[float, float, float, float]) -> List[dict]:
    """
    Call TomTom Incident Details API for given bbox.
    Returns a list of incident objects.
    """
    if (not TOMTOM_API_KEY) or TOMTOM_API_KEY == "7QF9hqXNPCMJkoQNay3abAJ1H6wkVnOH":
        print("ERROR: Set TOMTOM_API_KEY at top of this file.")
        return []

    minlat, minlon, maxlat, maxlon = bbox
    # TomTom expects bbox = minLon,minLat,maxLon,maxLat
    bbox_param = f"{minlon},{minlat},{maxlon},{maxlat}"

    # Fields: ask only for what we need
    fields = "{incidents{geometry{type,coordinates},properties{iconCategory,description}}}"

    params = {
        "key": TOMTOM_API_KEY,
        "bbox": bbox_param,
        "fields": fields,
        "language": "en-GB",
    }

    print("Calling TomTom Incident API...")
    resp = requests.get(TOMTOM_INCIDENT_URL, params=params)
    if resp.status_code != 200:
        print("TomTom API error:", resp.status_code, resp.text[:300])
        return []

    data = resp.json()
    incidents = data.get("incidents", [])
    print("TomTom returned", len(incidents), "incidents.")
    return incidents

def incident_type_from_icon_category(icon_cat: int, description: str) -> str:
    """
    Rough mapping from TomTom iconCategory/description → our incident_type.
    Good enough for hackathon.
    """
    desc = (description or "").lower()

    if "roadworks" in desc or "construction" in desc or "maintenance" in desc or "repair" in desc:
        return "roadworks"

    # very rough heuristic from iconCategory
    if icon_cat in (4, 5, 6, 7):
        return "roadworks"
    if icon_cat in (8, 9, 10):
        return "closure"

    return "other"

def extract_incident_points(incident: dict) -> List[Tuple[float, float]]:
    """
    From TomTom incident geometry, extract list of (lat, lon) points.
    """
    geom = incident.get("geometry", {})
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])

    points: List[Tuple[float, float]] = []

    if not gtype or not coords:
        return points

    # TomTom: Point = [lon, lat]; LineString = [[lon, lat], ...]
    if gtype == "Point":
        if isinstance(coords, list) and len(coords) >= 2:
            lon, lat = coords[0], coords[1]
            points.append((lat, lon))
    elif gtype == "LineString":
        for pair in coords:
            if isinstance(pair, list) and len(pair) >= 2:
                lon, lat = pair[0], pair[1]
                points.append((lat, lon))
    else:
        # For Polygon/MultiLineString etc, just sample numbers if present
        if isinstance(coords, list):
            for item in coords:
                if isinstance(item, list) and len(item) >= 2 and isinstance(item[0], (int, float)):
                    lon, lat = item[0], item[1]
                    points.append((lat, lon))

    return points

# -----------------------------
# Main
# -----------------------------

def main():
    # 1) Load CSV from previous stages
    if os.path.exists(BASE_CSV):
        csv_path = BASE_CSV
    elif os.path.exists(FALLBACK_CSV):
        csv_path = FALLBACK_CSV
    else:
        print("ERROR: No input CSV found.")
        print("Run datalink_pipeline.py (and twitter_incidents_ingest.py) first.")
        return

    print("Loading segments CSV:", csv_path)
    df = pd.read_csv(csv_path)
    print("Rows:", len(df))

    # 2) Build node table
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

        # use middle point of geometry
        mid_idx = len(pts) // 2
        lat, lon = pts[mid_idx]
        print(f" approx point: ({lat:.5f}, {lon:.5f})")

        nid = find_nearest_node(nodes, lat, lon)
        if not nid:
            print("  -> No nearest node found, skipping.")
            continue

        print("  -> Nearest graph node:", nid)
        apply_incident_to_segments(df, nid, itype)
        print("  -> Applied incident flags to connected segments.")

    # 5) Save result
    print("\nSaving TomTom-enriched CSV to:", OUTPUT_CSV)
    df.to_csv(OUTPUT_CSV, index=False)
    print("Done.")

if __name__ == "__main__":
    main()
