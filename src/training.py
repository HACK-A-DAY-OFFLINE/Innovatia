# trainer_real.py
import os
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline

# --------------------------
# Paths
# --------------------------
DATA_PATH = "data/sample.csv"          
MODEL_DIR = "model"
CONGESTION_MODEL_PATH = os.path.join(MODEL_DIR, "congestion.joblib")
WEIGHT_MODEL_PATH = os.path.join(MODEL_DIR, "weight.joblib")

os.makedirs(MODEL_DIR, exist_ok=True)

# --------------------------
# Load data
# --------------------------
df = pd.read_csv(DATA_PATH)
print(f"Loaded {len(df)} rows from {DATA_PATH}")

# --------------------------
# Targets
# --------------------------
y_cong = df["predicted_congestion"]
y_weight = df["weight"]

# Features (drop the targets)
features = df.drop(columns=["predicted_congestion", "weight", "source", "destination"])

# --------------------------
# Preprocessing
# --------------------------
numeric_features = [
    "distance", "road_quality", "lane_count", "speed_limit",
    "tolls", "foot_traffic", "historical_congestion",
    "pothole_reports"
]

categorical_features = [
    "road_type", "event", "vehicle_type", "accident"
]

preprocessor = ColumnTransformer([
    ("num", StandardScaler(), numeric_features),
    ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features)
])

# --------------------------
# Train Congestion Model
# --------------------------
cong_model = Pipeline([
    ("preprocess", preprocessor),
    ("regressor", RandomForestRegressor(n_estimators=200, random_state=42))
])

print("Training congestion model...")
cong_model.fit(features, y_cong)
joblib.dump(cong_model, CONGESTION_MODEL_PATH)
print(f"✅ Congestion model saved at {CONGESTION_MODEL_PATH}")

# --------------------------
# Train Weight Model
# --------------------------
weight_model = Pipeline([
    ("preprocess", preprocessor),
    ("regressor", RandomForestRegressor(n_estimators=200, random_state=42))
])

print("Training weight model...")
weight_model.fit(features, y_weight)
joblib.dump(weight_model, WEIGHT_MODEL_PATH)
print(f"✅ Weight model saved at {WEIGHT_MODEL_PATH}")