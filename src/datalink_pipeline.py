"""
datalink_pipeline.py
Data Link Layer pipeline that ingests real road data from OpenStreetMap Overpass API,
builds a directed graph of road segments, enriches attributes (lanes, speed, toll, quality,
surface, lighting, one-way, foot-traffic score, historical congestion, pothole & accident risk,
event flags), and exports segments_features.csv + segments_features.geojson.

Usage:
  python datalink_pipeline.py
"""
import os
import math
import json
from datetime import datetime
from typing import List, Dict

import requests
import pandas as pd
import networkx as nx
from shapely.geometry import LineString  # only for WKT creation

# -----------------------
# CONFIG: change bbox if you want a different area
# bbox = minlat, minlon, maxlat, maxlon
# Here is a small Bangalore bbox near the coordinates used earlier.
BBOX = (12.9680, 77.5920, 12.9820, 77.6020)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUT_DIR = "datalink_output"
# -----------------------

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def haversine_meters(lat1, lon1, lat2, lon2):
    # Digit-by-digit safe haversine
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def linestring_length_m(coords: List[Dict[str,float]]):
    # coords: list of {"lat":..., "lon":...}
    total = 0.0
    if len(coords) < 2:
        return 0.0
    for i in range(len(coords)-1):
        total += haversine_meters(coords[i]["lat"], coords[i]["lon"],
                                  coords[i+1]["lat"], coords[i+1]["lon"])
    return total

# -----------------------
# Overpass query: ways with highway tag in bbox; ask for geometry and tags
# -----------------------
def fetch_osm_roads(bbox):
    minlat, minlon, maxlat, maxlon = bbox
    # Overpass QL: fetch ways with highway tag in bbox
    query = f"""
    [out:json][timeout:60];
    (
      way["highway"]({minlat},{minlon},{maxlat},{maxlon});
    );
    out body;
    >;
    out skel qt;
    """
    print("Querying Overpass API for bbox:", bbox)
    resp = requests.post(OVERPASS_URL, data={"data": query})
    if resp.status_code != 200:
        raise RuntimeError(f"Overpass query failed: HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    return data

# -----------------------
# Parse Overpass JSON: build ways -> geometry list of lat/lon and tags
# -----------------------
def parse_overpass_to_ways(overpass_json):
    nodes = {}
    ways = []
    for el in overpass_json.get("elements", []):
        if el["type"] == "node":
            nodes[el["id"]] = {"lat": el["lat"], "lon": el["lon"]}
    for el in overpass_json.get("elements", []):
        if el["type"] == "way":
            tags = el.get("tags", {})
            geom = el.get("geometry")
            coords = []
            if geom:
                coords = [{"lat": p["lat"], "lon": p["lon"]} for p in geom]
            else:
                # fallback: build from node refs if available
                for nid in el.get("nodes", []):
                    if nid in nodes:
                        coords.append({"lat": nodes[nid]["lat"], "lon": nodes[nid]["lon"]})
            ways.append({
                "id": el.get("id"),
                "tags": tags,
                "coords": coords
            })
    return ways

# -----------------------
# Build DataFrame of segments (one row per directed segment)
# -----------------------
def ways_to_segments_df(ways):
    rows = []

    # maps used for derived features
    surface_quality_map = {
        "asphalt": 0.9,
        "paved": 0.8,
        "concrete": 0.9,
        "compacted": 0.7,
        "gravel": 0.5,
        "fine_gravel": 0.6,
        "ground": 0.4,
        "dirt": 0.3,
        "unpaved": 0.4,
        "sand": 0.2
    }

    foot_traffic_base_map = {
        "residential": 0.8,
        "living_street": 0.9,
        "tertiary": 0.7,
        "secondary": 0.5,
        "primary": 0.4,
        "trunk": 0.3,
        "motorway": 0.1,
        "unclassified": 0.5,
        "service": 0.6
    }

    historical_congestion_base_map = {
        "motorway": 0.5,
        "trunk": 0.6,
        "primary": 0.7,
        "secondary": 0.6,
        "tertiary": 0.5,
        "residential": 0.4,
        "unclassified": 0.5,
        "service": 0.45
    }

    for w in ways:
        coords = w["coords"]
        if not coords or len(coords) < 2:
            continue

        tags = w["tags"]

        # --- basic tags ---
        lane_tag = (tags.get("lanes") or
                    tags.get("lanes:forward") or
                    tags.get("lanes:backward"))
        try:
            lane_count = int(lane_tag) if lane_tag is not None else None
        except Exception:
            lane_count = None

        maxspeed = tags.get("maxspeed")
        try:
            speed_limit_kph = int(maxspeed.split()[0]) if isinstance(maxspeed, str) else None
        except Exception:
            speed_limit_kph = None

        toll = 1 if tags.get("toll", "no").lower() in ("yes", "true", "1") else 0
        road_type = tags.get("highway", "unclassified")

        # --- new: surface & lighting & oneway ---
        surface_type = tags.get("surface", "unknown")
        surface_quality = surface_quality_map.get(surface_type, 0.5)

        lit_tag = tags.get("lit", "no").lower()
        lit = True if lit_tag in ("yes", "true", "1") else False

        oneway_tag = tags.get("oneway", "no").lower()
        one_way = True if oneway_tag in ("yes", "true", "1", "-1") else False

        # base foot traffic by road type
        base_foot = foot_traffic_base_map.get(road_type, 0.4)
        # adjust slightly by lane_count (more lanes -> more traffic)
        lane_factor = (lane_count if lane_count is not None else 1)
        foot_traffic_score = min(base_foot * (0.8 + 0.05 * lane_factor), 1.0)

        # base historical congestion by road type
        hist_base = historical_congestion_base_map.get(road_type, 0.5)
        # adjust by speed (faster + urban-ish -> more congestion potential)
        spd = speed_limit_kph if speed_limit_kph is not None else 40
        spd_factor = min(spd, 120) / 120.0
        historical_congestion = max(min(hist_base * (0.7 + 0.6 * spd_factor), 1.0), 0.0)

        # compute length for whole way (not strictly needed per segment)
        _ = linestring_length_m(coords)

        # split each consecutive pair of coords into its own segment row
        for i in range(len(coords)-1):
            a = coords[i]; b = coords[i+1]
            from_node = f"{round(a['lat'],6)}_{round(a['lon'],6)}"
            to_node   = f"{round(b['lat'],6)}_{round(b['lon'],6)}"

            # geometry linestring for this small segment (WKT)
            ls = LineString([(a["lon"], a["lat"]), (b["lon"], b["lat"])])
            seg_len = haversine_meters(a["lat"], a["lon"], b["lat"], b["lon"])

            # heuristic road quality: base per road type + lanes
            base_quality = {
                "motorway": 10, "trunk": 8, "primary": 7, "secondary": 6,
                "tertiary": 5, "residential": 3, "unclassified": 4, "service": 4
            }.get(road_type, 4)
            quality = base_quality + (lane_count if lane_count is not None else 0)

            # --- new: risk scores ---
            # pothole risk: higher if surface is poor + quality is low
            pothole_risk = max(
                min((1.0 - surface_quality) * 0.6 + (max(12 - quality, 0) / 12.0) * 0.4, 1.0),
                0.0
            )

            # accident risk: higher with high speed + congestion
            accident_risk = max(
                min(0.2 + 0.5 * spd_factor + 0.3 * historical_congestion, 1.0),
                0.0
            )

            # event flags (default false; can be updated by event ingestion later)
            event_blocked = False
            vip_blocked = False
            closed_for_construction = False

            rows.append({
                "from_node": from_node,
                "to_node": to_node,
                "way_id": w["id"],
                "road_type": road_type,
                "lane_count": lane_count if lane_count is not None else 1,
                "speed_limit_kph": speed_limit_kph if speed_limit_kph is not None else 40,
                "toll": toll,
                "length_m": seg_len,
                "road_quality": quality,
                "geometry": ls.wkt,
                # new fields
                "surface_type": surface_type,
                "surface_quality": surface_quality,
                "lit": lit,
                "one_way": one_way,
                "foot_traffic_score": foot_traffic_score,
                "historical_congestion": historical_congestion,
                "pothole_risk": pothole_risk,
                "accident_risk": accident_risk,
                "event_blocked": event_blocked,
                "vip_blocked": vip_blocked,
                "closed_for_construction": closed_for_construction,
            })

    df = pd.DataFrame(rows)
    return df

# -----------------------
# Build NetworkX directed graph from segments df
# -----------------------
def build_graph_from_segments_df(df_segments):
    G = nx.DiGraph()
    for _, r in df_segments.iterrows():
        u = r["from_node"]
        v = r["to_node"]

        if not G.has_node(u):
            lat, lon = map(float, u.split("_"))
            G.add_node(u, lat=lat, lon=lon)
        if not G.has_node(v):
            lat, lon = map(float, v.split("_"))
            G.add_node(v, lat=lat, lon=lon)

        edge_attrs = {
            "segment_id": f"{r['way_id']}",
            "length_m": float(r["length_m"]),
            "lane_count": int(r["lane_count"]),
            "road_type": r["road_type"],
            "speed_limit_kph": int(r["speed_limit_kph"]),
            "toll": int(r["toll"]),
            "road_quality": float(r["road_quality"]),
            "geometry_wkt": r["geometry"],
            "surface_type": r["surface_type"],
            "surface_quality": float(r["surface_quality"]),
            "lit": bool(r["lit"]),
            "one_way": bool(r["one_way"]),
            "foot_traffic_score": float(r["foot_traffic_score"]),
            "historical_congestion": float(r["historical_congestion"]),
            "pothole_risk": float(r["pothole_risk"]),
            "accident_risk": float(r["accident_risk"]),
            "event_blocked": bool(r["event_blocked"]),
            "vip_blocked": bool(r["vip_blocked"]),
            "closed_for_construction": bool(r["closed_for_construction"]),
            "provenance": "overpass",
            "normalized_ts": now_iso()
        }
        G.add_edge(u, v, **edge_attrs)
    return G

# -----------------------
# Export functions
# -----------------------
def export_graph_edges_to_csv(G, out_path):
    rows = []
    for u, v, data in G.edges(data=True):
        row = data.copy()
        row["from_node"] = u
        row["to_node"] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    return df

def export_graph_edges_to_geojson(G, out_path):
    """
    Export graph edges to GeoJSON using node coordinates directly.
    This guarantees valid [lon, lat] and avoids any WKT issues.
    """
    features = []
    for u, v, data in G.edges(data=True):
        lat_u = G.nodes[u]["lat"]
        lon_u = G.nodes[u]["lon"]
        lat_v = G.nodes[v]["lat"]
        lon_v = G.nodes[v]["lon"]

        geom = {
            "type": "LineString",
            "coordinates": [
                [float(lon_u), float(lat_u)],   # [lon, lat]
                [float(lon_v), float(lat_v)]
            ]
        }

        feat = {
            "type": "Feature",
            "properties": {k: v for k, v in data.items() if k != "geometry_wkt"},
            "geometry": geom
        }
        features.append(feat)

    geo = {"type": "FeatureCollection", "features": features}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geo, f)
    return geo

# -----------------------
# Main pipeline
# -----------------------
def run_pipeline(bbox):
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR, exist_ok=True)

    raw = fetch_osm_roads(bbox)
    ways = parse_overpass_to_ways(raw)
    print(f"Fetched {len(ways)} ways from Overpass. Converting to segments...")
    df_segments = ways_to_segments_df(ways)
    print(f"Created {len(df_segments)} directed segments (rows). Building graph...")
    G = build_graph_from_segments_df(df_segments)

    csv_path = os.path.join(OUT_DIR, "segments_features.csv")
    geojson_path = os.path.join(OUT_DIR, "segments_features.geojson")

    df_out = export_graph_edges_to_csv(G, csv_path)
    export_graph_edges_to_geojson(G, geojson_path)

    print("Exported CSV:", csv_path)
    print("Exported GeoJSON:", geojson_path)
    print("Sample rows:")
    print(df_out.head().to_string(index=False))

if __name__ == "__main__":
    try:
        run_pipeline(BBOX)
    except Exception as e:
        print("Error:", e)
        print("If Overpass API rate-limited you, wait a moment and re-run.")