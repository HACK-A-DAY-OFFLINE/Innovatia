# astar.py
import sys
import pandas as pd
import joblib
import networkx as nx
from pathlib import Path

# --- CONFIG ---
CSV_FILE = "datalink_output/segments_features_enriched_tomtom.csv"
WEIGHT_MODEL_FILE = "model/weight.joblib"

# --- HELPER FUNCTIONS ---
def latlon_to_node(latlon):
    """Convert 'lat_lon' string to tuple of floats."""
    lat, lon = map(float, latlon.split("_"))
    return (lat, lon)

def closest_node(latlon_tuple, nodes):
    """Return the node in nodes closest to latlon_tuple."""
    lat, lon = latlon_tuple
    return min(nodes, key=lambda n: (n[0]-lat)**2 + (n[1]-lon)**2)

def load_graph(df):
    """Build a NetworkX graph from CSV data."""
    G = nx.DiGraph()
    for _, row in df.iterrows():
        try:
            start = latlon_to_node(row['start_node'])
            end = latlon_to_node(row['end_node'])
            G.add_edge(start, end, index=_)
        except KeyError:
            continue
    return G

def predict_weights(G, df, model):
    """Predict weights for each edge using weight_model."""
    for u, v, data in G.edges(data=True):
        idx = data['index']
        row = df.iloc[[idx]]  # keep as DataFrame
        X = row.select_dtypes(include=['number', 'object'])
        weight = model.predict(X)[0]
        G[u][v]['weight'] = weight
    return G

def run_astar(G, source, target):
    try:
        path = nx.astar_path(G, source, target, weight='weight')
        total_weight = sum(G[u][v]['weight'] for u, v in zip(path[:-1], path[1:]))
        return path, total_weight
    except nx.NetworkXNoPath:
        return [], 0.0

# --- MAIN ---
if len(sys.argv) != 3:
    print("Usage: python astar.py <source_lat_lon> <dest_lat_lon>")
    print("Example: python astar.py 12.9725_77.6018 12.9790_77.6023")
    sys.exit(1)

source_str, dest_str = sys.argv[1], sys.argv[2]
source = latlon_to_node(source_str)
target = latlon_to_node(dest_str)

# Load data and model
if not Path(CSV_FILE).exists() or not Path(WEIGHT_MODEL_FILE).exists():
    print("Missing CSV file or weight model.")
    sys.exit(1)

df = pd.read_csv(CSV_FILE)
weight_model = joblib.load(WEIGHT_MODEL_FILE)

# Build graph and predict weights
G = load_graph(df)
G = predict_weights(G, df, weight_model)

# Snap source/target to closest graph nodes
source = closest_node(source, list(G.nodes))
target = closest_node(target, list(G.nodes))

# Run A* search
best_path, total_weight = run_astar(G, source, target)

print("Best path:", best_path)
print("Total predicted weight:", total_weight)
