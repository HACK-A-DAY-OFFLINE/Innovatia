import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import SGDRegressor

# --- CONFIG ---
DATA_FILES = [
    "datalink_output/segments_features_enriched_tomtom.csv",
    "datalink_output/segments_features_enriched.csv",
    "datalink_output/segments_features.csv"
]
CONGESTION_MODEL_FILE = "model/congestion.joblib"
WEIGHT_MODEL_FILE = "model/weight.joblib"

# --- HELPER FUNCTIONS ---
def detect_features(df):
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    return numeric_cols, categorical_cols

def fill_missing_columns(df, all_numeric, all_categorical):
    for col in all_numeric:
        if col not in df.columns:
            df[col] = 0.0
    for col in all_categorical:
        if col not in df.columns:
            df[col] = ''
    return df

def load_or_create_pipeline(model_file, numeric_features, categorical_features):
    preprocessor = ColumnTransformer([
        ('num', StandardScaler(), numeric_features),
        ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
    ])
    
    if Path(model_file).exists():
        model = joblib.load(model_file)
        # Wrap plain regressors in pipeline
        if isinstance(model, Pipeline):
            pipeline = model
        else:
            pipeline = Pipeline([
                ('preprocessor', preprocessor),
                ('regressor', model)
            ])
        first_fit = not hasattr(pipeline.named_steps['regressor'], "coef_")
        return pipeline, first_fit
    else:
        pipeline = Pipeline([
            ('preprocessor', preprocessor),
            ('regressor', SGDRegressor(max_iter=1000, tol=1e-3, random_state=42))
        ])
        return pipeline, True

def fit_or_partial(model, X, y, first_fit):
    if isinstance(model, Pipeline) and 'regressor' in model.named_steps:
        if first_fit:
            model.fit(X, y)
        else:
            X_trans = model.named_steps['preprocessor'].transform(X)
            model.named_steps['regressor'].partial_fit(X_trans, y)
    else:
        if first_fit:
            model.fit(X, y)
        else:
            model.partial_fit(X, y)

# --- MAIN ---
all_numeric, all_categorical = [], []

# First pass to collect all columns across CSVs
for file in DATA_FILES:
    if Path(file).exists():
        df = pd.read_csv(file)
        nums, cats = detect_features(df)
        all_numeric = list(set(all_numeric + nums))
        all_categorical = list(set(all_categorical + cats))

congestion_model, first_cong_fit = load_or_create_pipeline(
    CONGESTION_MODEL_FILE, all_numeric, all_categorical
)
weight_model, first_weight_fit = load_or_create_pipeline(
    WEIGHT_MODEL_FILE, all_numeric, all_categorical
)

for file in DATA_FILES:
    if not Path(file).exists():
        continue
    df = pd.read_csv(file)
    df = fill_missing_columns(df, all_numeric, all_categorical)

    if 'congestion' not in df.columns:
        df['congestion'] = np.random.rand(len(df))
    if 'travel_time' not in df.columns:
        if 'speed_limit' in df.columns and 'length' in df.columns:
            df['travel_time'] = df['length'] / df['speed_limit'].replace(0, 1)
        else:
            df['travel_time'] = np.random.rand(len(df))

    X = df[all_numeric + all_categorical]
    y_cong = df['congestion']
    y_weight = df['travel_time']

    fit_or_partial(congestion_model, X, y_cong, first_cong_fit)
    first_cong_fit = False
    fit_or_partial(weight_model, X, y_weight, first_weight_fit)
    first_weight_fit = False

    print(f"Congestion mean error: {np.mean(y_cong - congestion_model.predict(X)):.4f}")
    print(f"Weight mean error: {np.mean(y_weight - weight_model.predict(X)):.4f}")

joblib.dump(congestion_model, CONGESTION_MODEL_FILE)
joblib.dump(weight_model, WEIGHT_MODEL_FILE)
print("Models updated and saved successfully.")
