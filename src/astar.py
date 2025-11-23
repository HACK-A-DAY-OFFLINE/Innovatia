# astar.py
import pandas as pd
import joblib
import heapq
import sys
import os

# --------------------------
# Config
# --------------------------
DATA_FILE = "data/sample.csv"
WEIGHT_MODEL_FILE = "model/weight.joblib"

if not os.path.exists(DATA_FILE):
    raise FileNotFoundError(f"{DATA_FILE} not found. Generate it first using generate_sample_data.py")

if not os.path.exists(WEIGHT_MODEL_FILE):
    raise FileNotFoundError(f"{WEIGHT_MODEL_FILE} not found. Train the weight model first using trainer_real.py")

# --------------------------
# Load model & data
# --------------------------
weight_model = joblib.load(WEIGHT_MODEL_FILE)
df = pd.read_csv(DATA_FILE)

# --------------------------
# Build graph with predicted weights
# --------------------------
graph = {}
for idx, row in df.iterrows():
    start = row['source']
    end = row['destination']
    
    # Predict weight using model
    edge_features = row.drop(['source', 'destination']).to_frame().T
    weight = weight_model.predict(edge_features)[0]
    
    if start not in graph:
        graph[start] = []
    graph[start].append((end, weight))

# --------------------------
# Heuristic function (Dijkstra fallback)
# --------------------------
def heuristic(node1, node2):
    return 0  # No coordinates in sample CSV

# --------------------------
# A* algorithm
# --------------------------
def a_star(graph, start, goal):
    if start not in graph or goal not in set(df['destination']):
        return [None], 0  # Invalid nodes
    
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {node: float('inf') for node in graph}
    g_score[start] = 0
    f_score = {node: float('inf') for node in graph}
    f_score[start] = 0

    while open_set:
        current_f, current = heapq.heappop(open_set)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path, g_score[goal]

        for neighbor, weight in graph.get(current, []):
            tentative_g = g_score[current] + weight
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

    return [None], 0  # no path found

# --------------------------
# Main CLI
# --------------------------
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python astar.py <source_node> <destination_node>")
        print("Example nodes: 'A', 'B', 'C', 'D', 'E'")
        sys.exit(1)

    source_node = sys.argv[1]
    dest_node = sys.argv[2]

    path, total_weight = a_star(graph, source_node, dest_node)
    print("Best path:", path)
    print("Total predicted weight:", total_weight)