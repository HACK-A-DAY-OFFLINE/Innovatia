import pandas as pd
import numpy as np
import joblib
import os
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline

df = pd.read_csv("data/sample.csv")

y = df["weight"]

features = df.drop(columns=["weight"])

numeric = [
    "distance", "road_quality", "lane_count", "speed_limit",
    "tolls", "foot_traffic", "historical_congestion",
    "pothole_reports", "predicted_congestion"
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

model = RandomForestRegressor(
    n_estimators=200,
    random_state=42
)

pipeline = Pipeline([
    ("preprocess", preprocess),
    ("model", model)
])

pipeline.fit(features, y)

os.makedirs("model", exist_ok=True)
joblib.dump(pipeline, "model/weight.joblib")

print("Weight model saved successfully!")