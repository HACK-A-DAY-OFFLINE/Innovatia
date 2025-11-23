# demo_turns.py
import pandas as pd
import joblib
import folium
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import heapq

# -------------------- SAMPLE DATA --------------------
df = pd.DataFrame([
    {"source":"MG_Road","destination":"Node1","distance":202,"road_quality":4.59,"lane_count":3,"road_type":"urban","speed_limit_kph":40,"tolls":0,"foot_traffic":0.6,"event":"none","vehicle_type":"sedan","historical_congestion":0.45,"accident":"no","pothole_reports":2,"weight":64.43,"geometry":[[12.9716,77.5946],[12.97165,77.5947],[12.9717,77.5948]]},
    {"source":"Node1","destination":"Node2","distance":187,"road_quality":3.67,"lane_count":3,"road_type":"highway","speed_limit_kph":40,"tolls":0,"foot_traffic":0.97,"event":"none","vehicle_type":"sedan","historical_congestion":0.83,"accident":"no","pothole_reports":1,"weight":61.89,"geometry":[[12.9717,77.5948],[12.9720,77.5950],[12.9725,77.5955]]},
    {"source":"Node2","destination":"Node3","distance":291,"road_quality":4.98,"lane_count":1,"road_type":"highway","speed_limit_kph":50,"tolls":0,"foot_traffic":0.52,"event":"none","vehicle_type":"sedan","historical_congestion":0.43,"accident":"no","pothole_reports":0,"weight":90.82,"geometry":[[12.9725,77.5955],[12.9730,77.5960],[12.9735,77.5965]]},
    {"source":"Node3","destination":"Cubbon_Park","distance":158,"road_quality":3.8,"lane_count":3,"road_type":"highway","speed_limit_kph":50,"tolls":0,"foot_traffic":0.79,"event":"none","vehicle_type":"sedan","historical_congestion":0.2,"accident":"no","pothole_reports":3,"weight":51.48,"geometry":[[12.9735,77.5965],[12.9740,77.5970],[12.9745,77.5975]]}
])

# -------------------- BUILD GRAPH --------------------
graph = {}
segment_coords = {}
for _, row in df.iterrows():
    start, end = row["source"], row["destination"]
    graph.setdefault(start, []).append((end, row["weight"]))
    segment_coords[(start,end)] = row["geometry"]

# -------------------- A* ALGORITHM --------------------
def heuristic(n1,n2):
    return 0

def a_star(graph,start,goal):
    if start not in graph or goal not in {e for edges in graph.values() for e,_ in edges}:
        return [None],0
    open_set = [(0,start)]
    came_from = {}
    g_score = {node:float('inf') for node in graph}
    g_score[start]=0
    while open_set:
        _,current = heapq.heappop(open_set)
        if current==goal:
            path=[current]
            while current in came_from:
                current=came_from[current]
                path.append(current)
            return path[::-1], g_score[goal]
        for neighbor,weight in graph.get(current,[]):
            tentative=g_score[current]+weight
            if tentative<g_score.get(neighbor,float('inf')):
                came_from[neighbor]=current
                g_score[neighbor]=tentative
                heapq.heappush(open_set,(tentative,neighbor))
    return [None],0

# -------------------- FULL COORDINATES FOR PATH --------------------
def path_with_coords(graph,start,goal,segment_coords):
    path,total=a_star(graph,start,goal)
    if not path or path==[None]:
        return [],0
    full_coords=[]
    for i in range(len(path)-1):
        seg = segment_coords.get((path[i],path[i+1]),[])
        # Include all intermediate nodes for turns
        full_coords.extend(seg if i==0 else seg[1:])
    return full_coords,total

# -------------------- RUN DEMO --------------------
coords,total = path_with_coords(graph,"MG_Road","Cubbon_Park",segment_coords)
if not coords:
    print("No valid path found")
else:
    print("Best path coordinates:", coords)
    print("Total predicted weight:", round(total,2))
    m = folium.Map(location=coords[0],zoom_start=16)
    folium.PolyLine(coords,color="blue",weight=5).add_to(m)
    folium.Marker(coords[0],tooltip="Start",icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(coords[-1],tooltip="End",icon=folium.Icon(color="red")).add_to(m)
    # Add markers for every intermediate turn
    for pt in coords[1:-1]:
        folium.CircleMarker(pt,radius=3,color="orange").add_to(m)
    m.save("demo_turns_map.html")
    print("Map saved to demo_turns_map.html")
