import pandas as pd
import numpy as np
import joblib
import os
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline

df = pd.read_csv("data/sample_data.csv")

y = df["predicted_congestion"]

features = df.drop(columns=["predicted_congestion", "weight"])

numeric = [
    "distance", "road_quality", "lane_count", "speed_limit",
    "tolls", "foot_traffic", "historical_congestion",
    "pothole_reports"
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