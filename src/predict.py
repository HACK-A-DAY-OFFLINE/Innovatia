# predict.py
import sys
import os
import math
import pandas as pd
import joblib
import networkx as nx
from shapely import wkt

CANDIDATES = [
    "datalink_output/segments_features_enriched_tomtom.csv",
    "datalink_output/segments_features_enriched.csv",
    "datalink_output/segments_features.csv",
]

MODEL_DIR = "model"
CONG_MODEL = os.path.join(MODEL_DIR, "congestion.joblib")
WEIGHT_MODEL = os.path.join(MODEL_DIR, "weight.joblib")

def pick_file():
    for p in CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("No input CSV found in /mnt/data. Make sure datalink pipeline output is present.")

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

def node_to_latlon(nid):
    lat_str, lon_str = nid.split("_")
    return float(lat_str), float(lon_str)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: python predict.py <source_node> <dest_node>')
        print('Example node format: "12.971566_77.594566"')
        sys.exit(1)

    source = sys.argv[1]
    dest = sys.argv[2]

    datafile = pick_file()
    df = pd.read_csv(datafile)

    # Ensure length_m exists; if not, try computing from geometry_wkt
    if "length_m" not in df.columns and "geometry_wkt" in df.columns:
        def seg_len_from_wkt(wktstr):
            try:
                geom = wkt.loads(wktstr)
                coords = list(geom.coords)
                total = 0.0
                for i in range(len(coords)-1):
                    lon1, lat1 = coords[i]
                    lon2, lat2 = coords[i+1]
                    total += haversine_m(lat1, lon1, lat2, lon2)
                return total
            except Exception:
                return 0.0
        df["length_m"] = df["geometry_wkt"].apply(seg_len_from_wkt)

    # Build directed graph
    G = nx.DiGraph()
    for _, r in df.iterrows():
        u = r["from_node"]
        v = r["to_node"]
        length = float(r.get("length_m", r.get("distance", 1.0)))
        # put placeholder weight for A* search: use length as cost
        G.add_edge(u, v, length=length)

    # A* requires a heuristic that is admissible: use straight-line haversine between nodes
    # build node lat/lon dict
    nodes = {}
    for n in set(df["from_node"].tolist() + df["to_node"].tolist()):
        try:
            nodes[n] = node_to_latlon(n)
        except:
            pass

    if source not in nodes or dest not in nodes:
        print("Source or destination not present as nodes in the graph.")
        sys.exit(1)

    def heuristic(n1, n2):
        lat1, lon1 = nodes[n1]
        lat2, lon2 = nodes[n2]
        return haversine_m(lat1, lon1, lat2, lon2)

    try:
        path = nx.astar_path(G, source, dest, heuristic=heuristic, weight="length")
    except nx.NetworkXNoPath:
        print("No path found between source and destination.")
        sys.exit(1)

    # compute route distance
    total_dist = 0.0
    edges = []
    for i in range(len(path)-1):
        u, v = path[i], path[i+1]
        length = G[u][v]["length"]
        total_dist += length
        edges.append((u, v))

    # load models
    if not os.path.exists(CONG_MODEL) or not os.path.exists(WEIGHT_MODEL):
        print("Model files not found. Run training first.")
        sys.exit(1)

    cong_model = joblib.load(CONG_MODEL)
    weight_model = joblib.load(WEIGHT_MODEL)

    # Build per-edge feature rows by selecting the same columns used in training.
    # We will create a features DataFrame for the edges in the route.
    route_rows = []
    for (u, v) in edges:
        # find a representative row in df matching u->v (take first match)
        row = df[(df["from_node"]==u) & (df["to_node"]==v)]
        if row.empty:
            # fallback: create minimal row
            route_rows.append({})
            continue
        r = row.iloc[0].to_dict()
        # add route_distance as additional feature
        r["route_distance"] = total_dist
        route_rows.append(r)

    feat_df = pd.DataFrame(route_rows).fillna(0)

    # Ensure features include numeric/categorical columns expected by models.
    # The model pipelines were trained on whatever features existed at training time.
    # Passing the DataFrame directly works as long as column names align.
    try:
        pred_cong = cong_model.predict(feat_df)
        pred_weight = weight_model.predict(feat_df)
    except Exception as e:
        print("Prediction error:", e)
        sys.exit(1)

    # aggregate along route
    avg_cong = float(pred_cong.mean()) if len(pred_cong)>0 else 0.0
    sum_weight = float(pred_weight.sum()) if len(pred_weight)>0 else 0.0

    # Print route summary
    print("Route nodes:", path)
    print("Total distance (m):", round(total_dist,2))
    print("Avg predicted congestion:", avg_cong)
    print("Sum predicted weight:", round(sum_weight,3))
    # show per-edge predictions (optional)
    for i,(u,v) in enumerate(edges):
        print(f"Edge {u}->{v} | cong={pred_cong[i]:.4f} | weight={pred_weight[i]:.4f}")