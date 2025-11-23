import pandas as pd
import numpy as np
import joblib
import os
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline

CANDIDATES = [
    "datalink_output/segments_features_enriched_tomtom.csv",
    "datalink_output/segments_features_enriched.csv",
    "datalink_output/segments_features.csv",
    "/mnt/data/segments_features_enriched_tomtom.csv", 
]

MODEL_DIR = "model"
os.makedirs(MODEL_DIR, exist_ok=True)
OUT_MODEL = os.path.join(MODEL_DIR, "congestion.joblib")

def pick_file():
    for p in CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("No input CSV found. Place the datalink output in one of: " + ", ".join(CANDIDATES))

path = pick_file()
print("Using dataset:", path)
df = pd.read_csv(path)
print("Rows:", len(df))

# If label missing, create weak label (safe default) so training can proceed
if "predicted_congestion" not in df.columns:
    print("No 'predicted_congestion' column found — generating weak labels for training.")
    df["predicted_congestion"] = (
        df.get("historical_congestion", 0.3).fillna(0.3) * 0.5 +
        (1 - df.get("road_quality", 7).fillna(7) / 10) * 0.3 +
        (df.get("pothole_risk", 0).fillna(0) * 0.2)
    )

# Candidate feature lists (use intersection with actual columns)
numeric_candidates = [
    "length_m", "distance", "road_quality", "lane_count", "speed_limit_kph",
    "toll", "tolls", "foot_traffic_score", "foot_traffic", "historical_congestion",
    "pothole_risk", "accident_risk"
]

categorical = [
    "road_type", "event", "vehicle_type", "accident"
]

preprocess = ColumnTransformer(
    transformers=[
        ("num", StandardScaler(), numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical)
    ]
)

model = RandomForestRegressor(n_estimators=200, random_state=42)

pipeline = Pipeline([
    ("preprocess", preprocess),
    ("model", model)
])

pipeline.fit(features, y)

os.makedirs("model", exist_ok=True)
joblib.dump(pipeline, "model/congestion.joblib")

print("Congestion model saved successfully!")