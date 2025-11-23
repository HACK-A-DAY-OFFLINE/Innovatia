// MapViewActivity.java (MODIFIED)
package com.example.navai;

import android.os.Bundle;
import android.util.Log;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashMap;

public class MapViewActivity extends AppCompatActivity {

    private static final String TAG = "MapViewActivity";
    private WebView mapWebView;
    private String routeCoordinatesJson;
    private String sourceName;
    private String destinationName;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_map_view);

        // 1. Get route data from Intent
        Bundle extras = getIntent().getExtras();
        if (extras != null) {
            routeCoordinatesJson = extras.getString("ROUTE_COORDINATES_JSON");
            sourceName = extras.getString("SOURCE_NAME_KEY", "Source");
            destinationName = extras.getString("DESTINATION_NAME_KEY", "Destination");
        }

        if (routeCoordinatesJson == null || routeCoordinatesJson.isEmpty()) {
            Toast.makeText(this, "Error: No route data received.", Toast.LENGTH_LONG).show();
            Log.e(TAG, "No route coordinates received.");
            finish();
            return;
        }

        // 2. Setup WebView
        mapWebView = findViewById(R.id.mapWebView);
        WebSettings webSettings = mapWebView.getSettings();
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);

        // Wait for the map to load before executing JS
        mapWebView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                // Call the JavaScript function to draw the route and pins
                drawRouteOnMap(routeCoordinatesJson);
            }
        });

        // Load the HTML file from the 'assets' folder
        mapWebView.loadUrl("file:///android_asset/navai_map.html");
    }

    /**
     * Executes the JavaScript function to draw the route and pins on the map.
     */
    private void drawRouteOnMap(String routeJson) {
        try {
            JSONObject apiResponse = new JSONObject(routeJson);
            JSONArray routeCoordsArray = apiResponse.getJSONArray("route_coordinates");

            if (routeCoordsArray.length() < 2) {
                Toast.makeText(this, "Route too short to draw.", Toast.LENGTH_LONG).show();
                return;
            }

            // Extract Start and End coordinates from the route array
            JSONArray start = routeCoordsArray.getJSONArray(0);
            JSONArray end = routeCoordsArray.getJSONArray(routeCoordsArray.length() - 1);

            double sLat = start.getDouble(0);
            double sLon = start.getDouble(1);
            double dLat = end.getDouble(0);
            double dLon = end.getDouble(1);

            // 1. Draw Pins
            String pinCommand = String.format(
                    "javascript:drawPins('%s', '%s', %f, %f, %f, %f);",
                    sourceName, destinationName, sLat, sLon, dLat, dLon
            );
            mapWebView.evaluateJavascript(pinCommand, null);

            // 2. Draw Route (pass the whole JSON array)
            // JSON.stringify will ensure the array is correctly passed to JS
            String routeCommand = String.format(
                    "javascript:drawRoute(%s);",
                    routeCoordsArray.toString()
            );
            mapWebView.evaluateJavascript(routeCommand, null);

            Log.d(TAG, "Route and Pins JS commands executed.");

        } catch (Exception e) {
            Log.e(TAG, "Error processing or executing JS for route: " + e.getMessage(), e);
            Toast.makeText(this, "Error processing route data for map.", Toast.LENGTH_LONG).show();
        }
    }
}