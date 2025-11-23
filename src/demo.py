# demo_map_real.py
import joblib
import pandas as pd
import heapq
import folium

# -----------------------------
# Config
# -----------------------------
CSV_FILE = "data/mg_to_cubbon.csv"
WEIGHT_MODEL_FILE = "model/weight.joblib"
MAP_FILE = "route_map.html"

# -----------------------------
# Load model and data
# -----------------------------
weight_model = joblib.load(WEIGHT_MODEL_FILE)
df = pd.read_csv(CSV_FILE)

# -----------------------------
# Build graph
# -----------------------------
graph = {}
for idx, row in df.iterrows():
    start = row['source']
    end = row['destination']
    features = row.drop(['source', 'destination']).to_frame().T
    weight = weight_model.predict(features)[0]

    if start not in graph:
        graph[start] = []
    graph[start].append((end, weight))

# -----------------------------
# Node coordinates (intermediate points along road)
# -----------------------------
coords = {
    "MG_Road": [12.9716, 77.5946],
    "Turn1": [12.9720, 77.5950],
    "Turn2": [12.9728, 77.5958],
    "Node1": [12.9735, 77.5965],
    "Turn3": [12.9742, 77.5972],
    "Node2": [12.9748, 77.5979],
    "Turn4": [12.9755, 77.5985],
    "Node3": [12.9760, 77.5989],
    "Cubbon_Park": [12.9766, 77.5990]
}

# -----------------------------
# Heuristic
# -----------------------------
def heuristic(node1, node2):
    return 0

# -----------------------------
# A* algorithm
# -----------------------------
def a_star(graph, start, goal):
    if start not in graph:
        return [None], 0
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {node: float('inf') for node in graph}
    g_score[start] = 0

    while open_set:
        current_f, current = heapq.heappop(open_set)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path, g_score[goal]

        for neighbor, w in graph.get(current, []):
            tentative_g = g_score[current] + w
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                heapq.heappush(open_set, (tentative_g + heuristic(neighbor, goal), neighbor))

    return [None], 0

# -----------------------------
# Run demo
# -----------------------------
source_node = "MG_Road"
dest_node = "Cubbon_Park"

path, total_weight = a_star(graph, source_node, dest_node)

print("Best path:", path)
print(f"Total predicted weight: {total_weight:.2f}")

# -----------------------------
# Visualize with Folium
# -----------------------------
m = folium.Map(location=coords[source_node], zoom_start=17)

# Draw polyline along all nodes in path
for i in range(len(path)-1):
    folium.PolyLine(
        [coords[path[i]], coords[path[i+1]]],
        color="blue",
        weight=5,
        opacity=0.8
    ).add_to(m)

# Add markers
for node in path:
    folium.Marker(
        coords[node],
        tooltip=node,
        icon=folium.Icon(color="green" if node==dest_node else "red")
    ).add_to(m)

# Save map
m.save(MAP_FILE)
print(f"Map saved to {MAP_FILE}")
