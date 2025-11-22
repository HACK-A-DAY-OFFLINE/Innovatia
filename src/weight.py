# weight.py
import os
import pandas as pd
import joblib
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
OUT_MODEL = os.path.join(MODEL_DIR, "weight.joblib")

def pick_file():
    for p in CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("No input CSV found. Place the datalink output in one of: " + ", ".join(CANDIDATES))

path = pick_file()
print("Using dataset:", path)
df = pd.read_csv(path)
print("Rows:", len(df))

# If weight missing, create weak label for training
if "weight" not in df.columns:
    print("No 'weight' column found — generating weak weight labels for training.")
    # base weight: length / speed factor + congestion factor + toll penalty
    speed = df.get("speed_limit_kph", df.get("speed_limit", 40)).fillna(40)
    length = df.get("length_m", df.get("distance", 1)).fillna(1)
    road_quality = df.get("road_quality", 7).fillna(7)
    hist = df.get("historical_congestion", 0.3).fillna(0.3)
    toll = df.get("toll", df.get("tolls", 0)).fillna(0)
    df["weight"] = (length / (speed + 1.0)) * 10 + (1 - road_quality / 10) * 20 + hist * 30 + toll * 5

numeric_candidates = [
    "length_m", "distance", "road_quality", "lane_count", "speed_limit_kph",
    "toll", "tolls", "historical_congestion", "pothole_risk", "accident_risk"
]

categorical_candidates = [
    "road_type", "surface_type", "surface", "provenance", "lit", "one_way"
]

numeric = [c for c in numeric_candidates if c in df.columns]
categorical = [c for c in categorical_candidates if c in df.columns]

print("Numeric features:", numeric)
print("Categorical features:", categorical)

if not numeric and not categorical:
    raise ValueError("No usable features found in dataset.")

X = df[numeric + categorical]
y = df["weight"]

preprocessor = ColumnTransformer(
    transformers=[
        ("num", StandardScaler(), numeric) if numeric else ("num", "passthrough", []),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical) if categorical else ("cat", "passthrough", [])
    ]
)

model = Pipeline([
    ("preprocess", preprocessor),
    ("est", RandomForestRegressor(n_estimators=200, random_state=42))
])

print("Training weight model...")
model.fit(X, y)
joblib.dump(model, OUT_MODEL)
print("Saved weight model to", OUT_MODEL)