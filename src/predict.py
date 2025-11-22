import joblib
import pandas as pd

congestion_model = joblib.load("model/congestion.joblib")
weight_model = joblib.load("model/weight.joblib")

def predict_congestion(input_dict: dict) -> float:
    df = pd.DataFrame([input_dict])
    result = congestion_model.predict(df)[0]
    return float(result)


def predict_weight(input_dict: dict) -> float:
    df = pd.DataFrame([input_dict])
    result = weight_model.predict(df)[0]
    return float(result)

if __name__ == "__main__":
    sample = pd.DataFrame([{
        "distance": 3.2,
        "road_quality": 0.7,
        "lane_count": 3,
        "speed_limit": 80,
        "tolls": 1,
        "foot_traffic": 0.3,
        "historical_congestion": 0.4,
        "pothole_reports": 1,
        "road_type": "highway",
        "event": "none",
        "vehicle_type": "sedan",
        "accident": "no"
    }])

    predicted_congestion = congestion_model.predict(sample)[0]
    print("Predicted Congestion:", predicted_congestion)

    sample["predicted_congestion"] = predicted_congestion

    predicted_weight = weight_model.predict(sample)[0]
    print("Predicted Weight:", predicted_weight)