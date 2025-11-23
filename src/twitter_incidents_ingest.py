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
# *** MANDATORY: Insert your valid Twitter/X Bearer Token here ***
TWITTER_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAEVH5gEAAAAAucmSX1QQGjA8SohcNIdEr2FJ3nk%3DhuWtYGqxWzHvvQhFXMK4ESbnoORpumbsKBxJ24mVx6DRz7qZZL"

# 2) Traffic police account username
TRAFFIC_USERNAME = "blrcitytraffic"  # change if you want another city

# 3) Input/Output files
INPUT_CSV = "datalink_output/segments_features.csv"
OUTPUT_CSV = "datalink_output/segments_features_enriched.csv"

# 4) Nominatim (OpenStreetMap) base URL for geocoding
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# -----------------------------

# Twitter API Endpoints
TWITTER_BASE_URL = "https://api.twitter.com/2"


def haversine_meters(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on the Earth."""
    R = 6371000  # Earth's radius in meters
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def build_node_table(df: pd.DataFrame) -> Dict[int, Tuple[float, float]]:
    """Builds a dictionary mapping node_id to (lat, lon)."""
    nodes = {}
    # Extract 'from' nodes
    from_nodes = df[['from_node', 'from_lat', 'from_lon']].drop_duplicates()
    for _, row in from_nodes.iterrows():
        nodes[row['from_node']] = (row['from_lat'], row['from_lon'])
        
    # Extract 'to' nodes (to catch all nodes)
    to_nodes = df[['to_node', 'to_lat', 'to_lon']].drop_duplicates()
    for _, row in to_nodes.iterrows():
        if row['to_node'] not in nodes:
             nodes[row['to_node']] = (row['to_lat'], row['to_lon'])

    return nodes


def find_nearest_node(nodes: Dict[int, Tuple[float, float]], lat: float, lon: float) -> Optional[int]:
    """Finds the graph node ID closest to the given (lat, lon)."""
    min_dist = float('inf')
    nearest_node_id = None

    for node_id, (n_lat, n_lon) in nodes.items():
        dist = haversine_meters(lat, lon, n_lat, n_lon)
        if dist < min_dist:
            min_dist = dist
            nearest_node_id = node_id

    # Use a reasonable threshold (e.g., 50 meters) to match incidents to roads
    if min_dist < 50:
        return nearest_node_id
    return None


def apply_incident_to_segments(df: pd.DataFrame, node_id: int, flags: Dict[str, bool]):
    """Sets the incident flags to True for all segments connected to node_id."""
    
    # Segments starting or ending at the node
    mask = (df['from_node'] == node_id) | (df['to_node'] == node_id)
    
    if flags.get("construction"):
        df.loc[mask, 'closed_for_construction'] = True
    if flags.get("vip"):
        df.loc[mask, 'vip_blocked'] = True
    if flags.get("event"):
        df.loc[mask, 'event_blocked'] = True
        
    # Ensure boolean columns are treated as boolean (important for CSV export)
    df['closed_for_construction'] = df['closed_for_construction'].astype(bool)
    df['vip_blocked'] = df['vip_blocked'].astype(bool)
    df['event_blocked'] = df['event_blocked'].astype(bool)


def get_user_id(username: str) -> Optional[str]:
    """Retrieves the numeric user ID for a given username."""
    if not TWITTER_BEARER_TOKEN:
        return None
    url = f"{TWITTER_BASE_URL}/users/by/username/{username}"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    
    print(f"Looking up User ID for @{username}...")
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("data", {}).get("id")
        else:
            print(f"Error fetching User ID (Status: {response.status_code}).")
            print(f"Response Body: {response.json()}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Network error during User ID lookup: {e}")
        return None


def get_recent_tweets(user_id: str, max_results: int = 20) -> List[Dict]:
    """Fetches recent tweets for a user ID."""
    if not TWITTER_BEARER_TOKEN:
        print("\n--- ERROR ---\nTwitter/X Bearer Token is empty. Please set TWITTER_BEARER_TOKEN in the script.\n--- END ERROR ---")
        return []

    url = f"{TWITTER_BASE_URL}/users/{user_id}/tweets"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    params = {
        "max_results": max_results,
        "tweet.fields": "created_at"
    }
    
    print(f"Fetching {max_results} recent tweets...")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            print(f"\n--- ERROR ---\nTwitter API Request Failed.")
            print(f"Status Code: {response.status_code}")
            try:
                # Print API error message if available
                print(f"Response Body: {response.json()}")
            except:
                print(f"Response Body: {response.text}")
            print(f"URL: {url}")
            print("--- END ERROR ---")
            return []

    except requests.exceptions.RequestException as e:
        print(f"\n--- ERROR ---\nNetwork or Connection Error when fetching Twitter/X incidents: {e}\n--- END ERROR ---")
        return []


def classify_tweet_type(text: str) -> Dict[str, bool]:
    """Determines incident flags based on tweet text keywords."""
    text = text.lower()
    flags = {
        "construction": any(k in text for k in ["road work", "construction", "repair", "maintenance"]),
        "vip": any(k in text for k in ["vip", "movement", "procession", "rally"]),
        "event": any(k in text for k in ["closure", "block", "diversion", "accident", "jampacked"])
    }
    return flags


def extract_location_hint(text: str) -> Optional[str]:
    """Simple heuristic to find a location name in the tweet text."""
    # Look for common road-related keywords near capitalized words
    keywords = ["near", "at", "road", "street", "junction", "signal", "circle", "flyover"]
    words = text.split()
    
    # Simple strategy: look for sequences of capitalized words that follow a keyword
    # This is highly dependent on the target city/twitter style
    for i, word in enumerate(words):
        if word.lower() in keywords and i + 1 < len(words):
            location_parts = []
            # Start gathering capitalized words after the keyword
            for j in range(i + 1, len(words)):
                if words[j].istitle() or words[j].isupper() or words[j].isdigit():
                    location_parts.append(words[j])
                else:
                    break
            if location_parts:
                return " ".join(location_parts)
    
    # Fallback: Just return the first sequence of two or more capitalized words
    for i in range(len(words) - 1):
        if words[i].istitle() and words[i+1].istitle():
            loc = [words[i], words[i+1]]
            for j in range(i + 2, len(words)):
                 if words[j].istitle():
                    loc.append(words[j])
                 else:
                    break
            return " ".join(loc)
            
    return None


def geocode_place(query: str, city: str) -> Optional[Tuple[float, float]]:
    """Geocodes a location query using OpenStreetMap Nominatim API."""
    params = {
        "q": f"{query}, {city}, India",  # Geocode within the context of the city
        "format": "json",
        "limit": 1
    }
    
    print(f"Geocoding query: '{query}'...")
    try:
        response = requests.get(NOMINATIM_URL, params=params, timeout=10)
        response.raise_for_status()
        results = response.json()
        
        if results:
            lat = float(results[0].get('lat'))
            lon = float(results[0].get('lon'))
            return lat, lon
        return None
    
    except requests.exceptions.RequestException as e:
        print(f"Geocoding error: {e}")
        return None


def main():
    if not os.path.exists(INPUT_CSV):
        print(f"Error: Input CSV not found: {INPUT_CSV}. Run datalink_pipeline.py first.")
        return

    print(f"Loading base data from: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV)
    
    # Initialize incident columns if they don't exist
    if 'event_blocked' not in df.columns: df['event_blocked'] = False
    if 'vip_blocked' not in df.columns: df['vip_blocked'] = False
    if 'closed_for_construction' not in df.columns: df['closed_for_construction'] = False

    # 1) Get User ID
    user_id = get_user_id(TRAFFIC_USERNAME)
    if not user_id:
        print(f"Could not retrieve User ID for @{TRAFFIC_USERNAME}. Cannot proceed with tweet ingestion.")
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"Data saved without Twitter enrichment to: {OUTPUT_CSV}")
        return
    print(f"Successfully retrieved User ID: {user_id}")

    # 2) Build node table for nearest neighbor search
    print("Building node table...")
    nodes = build_node_table(df)
    print("Unique nodes:", len(nodes))

    # 3) Fetch recent tweets
    tweets = get_recent_tweets(user_id, max_results=20)
    
    if not tweets:
        print("No tweets fetched or API error. Saving base copy as:", OUTPUT_CSV)
        df.to_csv(OUTPUT_CSV, index=False)
        return

    # 4) Process and map tweets
    incidents_applied_count = 0
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
        
        # Geocode the location hint
        geo = geocode_place(loc_hint, city="Bengaluru")
        
        if not geo:
            print(" -> Geocoding failed for location:", loc_hint)
            continue

        lat, lon = geo
        print(f" -> Geocoded to ({lat:.5f}, {lon:.5f})")

        node_id = find_nearest_node(nodes, lat, lon)
        if not node_id:
            print(" -> No nearest node found (closest point > 50m), skipping.")
            continue

        print(" -> Nearest graph node:", node_id)
        apply_incident_to_segments(df, node_id, flags)
        incidents_applied_count += 1
        print(" -> Applied incident flags to connected segments.")


    print(f"\nSuccessfully applied {incidents_applied_count} Twitter incidents to the graph data.")
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Final enriched data saved to: {OUTPUT_CSV}")
    print("Done.")

if __name__ == "__main__":
    main()