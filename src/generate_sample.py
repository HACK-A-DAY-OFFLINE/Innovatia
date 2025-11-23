import pandas as pd
import numpy as np
from pathlib import Path

def generate_sample_data(n=5000, out_file="data/sample.csv"):
    rng = np.random.default_rng(42)
    
    nodes = ["A", "B", "C", "D", "E"]
    road_types = ["highway", "urban", "rural"]
    vehicle_types = ["sedan", "suv", "truck", "bike"] 
    events = ["none", "none", "none", "procession", "vip_movement"]
    accidents = ["yes", "no"]

    rows = []

    for _ in range(n):
        source = rng.choice(nodes)
        destination = rng.choice(nodes)
        while destination == source:
            destination = rng.choice(nodes)

        distance = float(rng.integers(1, 60))
        road_quality = rng.uniform(1.0, 5.0)
        lane_count = int(rng.choice([1, 2, 3, 4], p=[0.2, 0.5, 0.2, 0.1]))
        road_type = rng.choice(road_types)
        speed_limit = rng.choice([40, 60, 80, 100])
        tolls = int(rng.choice([0, 0, 0, 1, 2]))
        foot_traffic = rng.uniform(0, 1)
        event = rng.choice(events)
        vehicle_type = rng.choice(vehicle_types)
        historical_congestion = rng.uniform(0, 1)
        
        accident_prob = [0.05, 0.95] # 5% chance of accident
        accident = rng.choice(["yes", "no"], p=accident_prob)
        
        potholes = int(rng.integers(0, 11))

        acc_factor = 0.8 if accident == "yes" else 0.0
        congestion = (
            0.4 * (1 / road_quality) +
            0.2 * foot_traffic +
            0.2 * historical_congestion +
            acc_factor +
            0.1 * (potholes / 10)
        )
        congestion = float(np.clip(congestion, 0, 1))

        weight = (
            0.3 * distance +
            5 * (1 / road_quality) +
            3 * (1 - speed_limit / 120) +
            2 * tolls +
            10 * congestion +  
            (10 if accident == "yes" else 0) +
            potholes * 0.2
        )

        rows.append({
            "source": source,
            "destination": destination,
            "distance": distance,
            "road_quality": round(road_quality, 2),
            "lane_count": lane_count,
            "road_type": road_type,
            "speed_limit": speed_limit,
            "tolls": tolls,
            "foot_traffic": round(foot_traffic, 3),
            "event": event,
            "vehicle_type": vehicle_type,
            "historical_congestion": round(historical_congestion, 3),
            "accident": accident,
            "pothole_reports": potholes,
            "predicted_congestion": round(congestion, 3),
            "weight": round(weight, 3)
        })

    df = pd.DataFrame(rows)
    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_file, index=False)
    print(f"[OK] Sample data generated → {out_file}")

if __name__ == "__main__":
    generate_sample_data()