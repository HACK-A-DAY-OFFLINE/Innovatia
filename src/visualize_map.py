"""
visualize_map.py

Visualises the road graph on an interactive map (Leaflet via folium).

- Reads the MOST enriched CSV it can find:
    1) segments_features_enriched_tomtom.csv
    2) segments_features_enriched.csv
    3) segments_features.csv

- Draws each road segment as a polyline.
- Colors segments based on:
    * red   -> event_blocked or vip_blocked or closed_for_construction
    * orange-> high congestion / risk
    * green -> normal

Output:
    datalink_output/navai_map.html
"""

import os
import math
import webbrowser

import pandas as pd
from shapely import wkt
import folium

# -----------------------------
# CONFIG
# -----------------------------

OUT_DIR = "datalink_output"

CANDIDATE_CSVS = [
    os.path.join(OUT_DIR, "segments_features_enriched_tomtom.csv"),
    os.path.join(OUT_DIR, "segments_features_enriched.csv"),
    os.path.join(OUT_DIR, "segments_features.csv"),
]

OUTPUT_HTML = os.path.join(OUT_DIR, "navai_map.html")


def pick_input_csv():
    for path in CANDIDATE_CSVS:
        if os.path.exists(path):
            return path
    return None


def get_center_from_df(df: pd.DataFrame):
    # try to estimate map center from node coordinates
    lats = []
    lons = []

    for col in ("from_node", "to_node"):
        if col not in df.columns:
            continue
        for nid in df[col].unique():
            try:
                lat_str, lon_str = str(nid).split("_")
                lats.append(float(lat_str))
                lons.append(float(lon_str))
            except Exception:
                continue

    if not lats or not lons:
        # fallback: Bangalore-ish
        return 12.976, 77.603

    return sum(lats) / len(lats), sum(lons) / len(lons)


def segment_color(row):
    # 1) if any blocking flag true → red
    blocked = False
    for col in ("event_blocked", "vip_blocked", "closed_for_construction"):
        if col in row and pd.notna(row[col]) and bool(row[col]):
            blocked = True
            break
    if blocked:
        return "red"

    # 2) else use congestion / risk / quality heuristics
    hist = row.get("historical_congestion", 0.0) or 0.0
    risk = row.get("accident_risk", 0.0) or 0.0
    qual = row.get("road_quality", 0.0) or 0.0

    try:
        hist = float(hist)
    except Exception:
        hist = 0.0
    try:
        risk = float(risk)
    except Exception:
        risk = 0.0
    try:
        qual = float(qual)
    except Exception:
        qual = 0.0

    # if high congestion or high risk → orange
    if hist > 0.6 or risk > 0.6:
        return "orange"

    # else good/okay roads → green
    return "green"


def main():
    csv_path = pick_input_csv()
    if not csv_path:
        print("ERROR: no segments CSV found in datalink_output.")
        print("Run datalink_pipeline.py (and enrichment scripts) first.")
        return

    print("Using CSV:", csv_path)
    df = pd.read_csv(csv_path)
    print("Rows:", len(df))

    if "geometry_wkt" in df.columns:
        geom_col = "geometry_wkt"
    elif "geometry" in df.columns:
        geom_col = "geometry"
    else:
        print("ERROR: no geometry column found (expected 'geometry_wkt' or 'geometry').")
        return

    # center of map
    center_lat, center_lon = get_center_from_df(df)
    print(f"Map center: ({center_lat:.6f}, {center_lon:.6f})")

    m = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles="CartoDB positron")

    # add segments
    count_drawn = 0
    for _, row in df.iterrows():
        wkt_str = row.get(geom_col)
        if not isinstance(wkt_str, str):
            continue
        try:
            geom = wkt.loads(wkt_str)
        except Exception:
            continue

        if geom.is_empty:
            continue

        # We expect LineString or MultiLineString
        lines = []
        if geom.geom_type == "LineString":
            lines = [geom]
        elif geom.geom_type == "MultiLineString":
            lines = list(geom.geoms)
        else:
            continue

        color = segment_color(row)

        for line in lines:
            # shapely stores coords as (lon, lat); folium wants (lat, lon)
            latlon = [(lat, lon) for lon, lat in line.coords]
            folium.PolyLine(
                locations=latlon,
                color=color,
                weight=3,
                opacity=0.8,
            ).add_to(m)
            count_drawn += 1

    print("Segments drawn:", count_drawn)

    # Legend (simple HTML)
    legend_html = """
     <div style="
        position: fixed;
        bottom: 50px;
        left: 50px;
        z-index:9999;
        background-color: white;
        padding: 10px;
        border:2px solid grey;
        border-radius:8px;
        font-size:14px;
     ">
     <b>Navai road status</b><br>
     <span style="color:red;">&#9608;</span> Blocked (event / VIP / construction)<br>
     <span style="color:orange;">&#9608;</span> High congestion / risk<br>
     <span style="color:green;">&#9608;</span> Normal / good<br>
     </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    os.makedirs(OUT_DIR, exist_ok=True)
    m.save(OUTPUT_HTML)
    print("Saved map to:", OUTPUT_HTML)

    # try to open automatically
    try:
        webbrowser.open("file://" + os.path.abspath(OUTPUT_HTML))
    except Exception:
        pass


if __name__ == "__main__":
    main()
