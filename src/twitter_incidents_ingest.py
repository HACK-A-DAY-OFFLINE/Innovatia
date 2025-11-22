"""
twitter_incidents_ingest.py

Reads datalink_output/segments_features.csv,
fetches recent tweets from a traffic police Twitter account,
detects closure / VIP / event tweets, geocodes their locations,
finds nearest road segments, and flips:
  - event_blocked
  - vip_blocked
  - closed_for_construction

Usage:
  python twitter_incidents_ingest.py
"""

import os
import math
import time
from typing import Optional, Tuple, List, Dict

import requests
import pandas as pd

# -----------------------------
# CONFIG - EDIT THIS
# -----------------------------

# 1) Your Twitter/X API v2 Bearer token
TWITTER_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAEVH5gEAAAAAucmSX1QQGjA8SohcNIdEr2FJ3nk%3DhuWtYGqxWzHvvQhFXMK4ESbnoORpumbsKBxJ24mVx6DRz7qZZL"

# 2) Traffic police account username
TRAFFIC_USERNAME = "blrcitytraffic"  # change if you want another city

# 3) Input/Output files
INPUT_CSV = "datalink_output/segments_features.csv"
OUTPUT_CSV = "datalink_output/segments_features_enriched.csv"

# 4) Nominatim (OpenStreetMap) base URL for geocoding
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# -----------------------------
# Helper functions
# -----------------------------

def haversine_meters(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# -----------------------------
# Twitter API calls
# -----------------------------

def twitter_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

def get_user_id(username: str) -> Optional[str]:
    urls = [
        f"https://api.x.com/2/users/by/username/{username}",
        f"https://api.twitter.com/2/users/by/username/{username}",
    ]
    for u in urls:
        resp = requests.get(u, headers=twitter_headers())
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("id")
    print("Failed to get user id for", username)
    return None

def get_recent_tweets(user_id: str, max_results: int = 20) -> List[Dict]:
    urls = [
        f"https://api.x.com/2/users/{user_id}/tweets",
        f"https://api.twitter.com/2/users/{user_id}/tweets",
    ]
    params = {
        "max_results": str(max_results),
        "tweet.fields": "created_at,text"
    }
    for u in urls:
        resp = requests.get(u, headers=twitter_headers(), params=params)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", [])
    print("Failed to fetch recent tweets")
    return []

# -----------------------------
# Simple classification & location extraction
# -----------------------------

EVENT_KEYWORDS = ["procession", "rally", "marathon", "festival", "event", "bandh"]
VIP_KEYWORDS = ["vip movement", "vip", "hon'ble", "prime minister", "president", "cm convoy"]
CLOSURE_KEYWORDS = ["closed", "road work", "construction", "repair", "maintenance", "blocked", "diversion"]

LOCATION_HINT_WORDS = [" at ", " near ", " from ", " towards ", " on ", " around "]

# common Bangalore spots – add more if you want
MANUAL_LOCATIONS = {
    "mg road": (12.9750, 77.6050),
    "hebbal flyover": (13.0357, 77.5919),
    "silk board": (12.9166, 77.6241),
    "majestic": (12.9789, 77.5713),
}

def classify_tweet_type(text: str) -> Dict[str, bool]:
    t = text.lower()
    is_event = any(kw in t for kw in EVENT_KEYWORDS)
    is_vip = any(kw in t for kw in VIP_KEYWORDS)
    is_closure = any(kw in t for kw in CLOSURE_KEYWORDS)
    return {"event": is_event, "vip": is_vip, "closure": is_closure}

def extract_location_hint(text: str) -> Optional[str]:
    t = text.lower()
    # manual first
    for name in MANUAL_LOCATIONS.keys():
        if name in t:
            return name
    # heuristic: after " at ", " near " etc.
    for hint in LOCATION_HINT_WORDS:
        if hint in t:
            idx = t.index(hint) + len(hint)
            loc = t[idx:]
            for sep in [",", ";", " due", " because"]:
                sep_idx = loc.find(sep)
                if sep_idx != -1:
                    loc = loc[:sep_idx]
            loc = loc.strip()
            if len(loc) > 3:
                return loc
    return None

# -----------------------------
# Geocoding
# -----------------------------

def geocode_place(place: str, city: str = "Bengaluru") -> Optional[Tuple[float, float]]:
    place = place.strip()
    if place in MANUAL_LOCATIONS:
        return MANUAL_LOCATIONS[place]

    q = f"{place}, {city}"
    params = {"q": q, "format": "json", "limit": 1}
    headers = {"User-Agent": "navai-hackathon-bot/1.0"}
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers)
        if resp.status_code == 200:
            arr = resp.json()
            if arr:
                lat = float(arr[0]["lat"])
                lon = float(arr[0]["lon"])
                return lat, lon
        print("Geocode failed for", q)
    except Exception as e:
        print("Geocode exception for", q, ":", e)
    return None

# -----------------------------
# Map location -> graph segments
# -----------------------------

def build_node_table(df: pd.DataFrame):
    nodes = {}
    def parse_node(nid: str):
        lat_str, lon_str = nid.split("_")
        return float(lat_str), float(lon_str)
    for col in ["from_node", "to_node"]:
        if col not in df.columns:
            continue
        for nid in df[col].unique():
            if nid not in nodes:
                try:
                    nodes[nid] = parse_node(nid)
                except Exception:
                    continue
    return nodes

def find_nearest_node(nodes: Dict[str, Tuple[float,float]], lat: float, lon: float) -> Optional[str]:
    best_id = None
    best_d = float("inf")
    for nid, (nlat, nlon) in nodes.items():
        d = haversine_meters(lat, lon, nlat, nlon)
        if d < best_d:
            best_d = d
            best_id = nid
    return best_id

def apply_incident_to_segments(df: pd.DataFrame,
                               node_id: str,
                               incident_flags: Dict[str, bool]) -> None:
    mask = (df["from_node"] == node_id) | (df["to_node"] == node_id)
    if not mask.any():
        return

    if "event_blocked" not in df.columns:
        df["event_blocked"] = False
    if "vip_blocked" not in df.columns:
        df["vip_blocked"] = False
    if "closed_for_construction" not in df.columns:
        df["closed_for_construction"] = False

    if incident_flags.get("event"):
        df.loc[mask, "event_blocked"] = True
    if incident_flags.get("vip"):
        df.loc[mask, "vip_blocked"] = True
    if incident_flags.get("closure"):
        df.loc[mask, "closed_for_construction"] = True

# -----------------------------
# Main
# -----------------------------

def main():
    # Check token looks non-empty (you edited it)
    if len(TWITTER_BEARER_TOKEN.strip()) < 20 or "PAAAAAAAAAAAAAAAAAAAAAEVH5gEAAAAAucmSX1QQGjA8SohcNIdEr2FJ3nk%3DhuWtYGqxWzHvvQhFXMK4ESbnoORpumbsKBxJ24mVx6DRz7qZZL" in TWITTER_BEARER_TOKEN:
        print("ERROR: Please set TWITTER_BEARER_TOKEN at top of this file.")
        return

    if not os.path.exists(INPUT_CSV):
        print("ERROR: Input CSV not found:", INPUT_CSV)
        print("Run datalink_pipeline.py first.")
        return

    print("Loading segments CSV:", INPUT_CSV)
    df = pd.read_csv(INPUT_CSV)
    print("Rows:", len(df))

    print("Building node table...")
    nodes = build_node_table(df)
    print("Unique nodes:", len(nodes))

    print("Fetching Twitter user id for:", TRAFFIC_USERNAME)
    user_id = get_user_id(TRAFFIC_USERNAME)
    if not user_id:
        print("Could not get user id, aborting.")
        return
    print("User id:", user_id)

    print("Fetching recent tweets for user id:", user_id)
    tweets = get_recent_tweets(user_id, max_results=20)
    print("Fetched", len(tweets), "tweets")

    for tw in tweets:
        text = tw.get("text", "")
        created_at = tw.get("created_at", "")
        print("\nTweet:", created_at)
        print(text)

        flags = classify_tweet_type(text)
        if not any(flags.values()):
            print(" -> No closure/VIP/event keywords, skipping.")
            continue

        loc_hint = extract_location_hint(text)
        if not loc_hint:
            print(" -> Could not find location in tweet, skipping.")
            continue

        print(" -> Detected incident type:", flags, "location hint:", loc_hint)
        geo = geocode_place(loc_hint, city="Bengaluru")
        if not geo:
            print(" -> Geocoding failed for location:", loc_hint)
            continue

        lat, lon = geo
        print(f" -> Geocoded to ({lat:.5f}, {lon:.5f})")

        node_id = find_nearest_node(nodes, lat, lon)
        if not node_id:
            print(" -> No nearest node found, skipping.")
            continue

        print(" -> Nearest graph node:", node_id)
        apply_incident_to_segments(df, node_id, flags)
        print(" -> Applied incident flags to connected segments.")

        # Be nice to Nominatim
        time.sleep(1.0)

    print("\nSaving enriched CSV to:", OUTPUT_CSV)
    df.to_csv(OUTPUT_CSV, index=False)
    print("Done.")

if __name__ == "__main__":
    main()
