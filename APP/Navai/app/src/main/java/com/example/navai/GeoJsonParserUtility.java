// GeoJsonParserUtility.java (Updated with sample names)
package com.example.navai;

import android.content.Context;
import android.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Scanner;

public class GeoJsonParserUtility {

    private static final String TAG = "GeoJsonParserUtility";
    // Stores: Human-Readable Name (String) -> {Latitude (double), Longitude (double)}
    private static HashMap<String, double[]> locationCoordinatesCache = new HashMap<>();
    private static boolean isDataLoaded = false;

    // *** CRITICAL: YOU MUST EXPAND THIS TABLE WITH YOUR 4133 LOCATIONS ***
    // This maps the segment_id (number) to a human-readable name.
    private static final HashMap<String, String> MANUAL_NAME_LOOKUP = new HashMap<String, String>() {{
        // Segment IDs found in the GeoJSON snippet:
        put("23029701", "MG Road - Trinity Circle");
        put("135997372", "Residential Lane near MG Road");
        put("1422250267", "Kasturba Road Vicinity");
        put("328753690", "Service Road off MG Road");
        put("36883291", "Residential Lane North");
        put("1125877410", "Small Service Lane");

        // Add the remaining ~4127 segment IDs here:
        // put("123456789", "Commercial Street Entrance");
        // put("987654321", "Vidhana Soudha");
    }};

    public static HashMap<String, double[]> loadLocationCoordinates(Context context) {
        if (isDataLoaded) {
            return locationCoordinatesCache;
        }

        String jsonString = loadJsonFromAsset(context, "segments_features.geojson");
        locationCoordinatesCache.clear();

        if (jsonString != null) {
            try {
                JSONObject root = new JSONObject(jsonString);
                JSONArray features = root.getJSONArray("features");

                for (int i = 0; i < features.length(); i++) {
                    JSONObject feature = features.getJSONObject(i);

                    JSONObject properties = feature.getJSONObject("properties");
                    String segmentId = properties.getString("segment_id");
                    String roadType = properties.getString("road_type");

                    // 1. Look up the human-readable name
                    String finalLocationName = MANUAL_NAME_LOOKUP.get(segmentId);

                    if (finalLocationName == null) {
                        // 2. FALLBACK: Use a descriptive technical name if no manual name is found
                        finalLocationName = roadType.substring(0, 1).toUpperCase() + roadType.substring(1) + " Segment: " + segmentId;
                    }

                    JSONObject geometry = feature.getJSONObject("geometry");
                    if (geometry.getString("type").equals("LineString")) {
                        JSONArray coordinates = geometry.getJSONArray("coordinates");
                        if (coordinates.length() > 0) {
                            // GeoJSON uses [Longitude, Latitude] order
                            JSONArray firstCoord = coordinates.getJSONArray(0);
                            double longitude = firstCoord.getDouble(0);
                            double latitude = firstCoord.getDouble(1);

                            // Store Human-Readable Name -> {Lat, Lon}
                            locationCoordinatesCache.put(finalLocationName, new double[]{latitude, longitude});
                        }
                    }
                }
                isDataLoaded = true;
                Log.d(TAG, "Successfully loaded " + locationCoordinatesCache.size() + " locations from GeoJSON.");
            } catch (Exception e) {
                Log.e(TAG, "Error parsing GeoJSON data.", e);
                isDataLoaded = false;
            }
        } else {
            Log.e(TAG, "Failed to load segments_features.geojson from assets.");
            isDataLoaded = false;
        }

        return locationCoordinatesCache;
    }

    private static String loadJsonFromAsset(Context context, String filename) {
        String json = null;
        try {
            InputStream is = context.getAssets().open(filename);
            Scanner scanner = new Scanner(is).useDelimiter("\\A");
            json = scanner.hasNext() ? scanner.next() : null;
            is.close();
        } catch (IOException ex) {
            Log.e(TAG, "Error loading asset file: " + filename, ex);
        }
        return json;
    }
}