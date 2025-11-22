// MapViewActivity.java (MODIFIED)
package com.example.navai;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import java.util.HashMap;

public class MapViewActivity extends AppCompatActivity {

    private static final String TAG = "MapViewActivity";
    private String source;
    private String destination;
    private String vehicleType;
    private WebView mapWebView;
    private HashMap<String, double[]> locationCoordinates;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_map_view);

        // 1. Load GeoJSON Data (Human-readable name -> Coords)
        locationCoordinates = GeoJsonParserUtility.loadLocationCoordinates(this);

        // 2. Get data
        Bundle extras = getIntent().getExtras();
        if (extras != null) {
            source = extras.getString("SOURCE_KEY");
            destination = extras.getString("DESTINATION_KEY");
            vehicleType = extras.getString("VEHICLE_TYPE_KEY");
        }

        // 3. Setup WebView
        mapWebView = findViewById(R.id.mapWebView);
        WebSettings webSettings = mapWebView.getSettings();
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);

        mapWebView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                Log.d(TAG, "Map Page Finished Loading. Attempting to draw pins.");

                // CRITICAL FIX: Add a short delay to allow Leaflet/Folium to fully initialize
                view.postDelayed(() -> searchAndDrawPins(source, destination), 500);
            }
        });
        mapWebView.loadUrl("file:///android_asset/navai_map.html");


        // 4. Setup Navigation Buttons (Confirm and Change/Back)
        Button confirmLocationsButton = findViewById(R.id.confirmLocationsButton);
        Button changeLocationsButton = findViewById(R.id.changeLocationsButton);

        confirmLocationsButton.setOnClickListener(v -> {
            Intent intent = new Intent(MapViewActivity.this, ConfirmMapActivity.class);
            intent.putExtra("SOURCE_KEY", source);
            intent.putExtra("DESTINATION_KEY", destination);
            intent.putExtra("VEHICLE_TYPE_KEY", vehicleType);
            startActivity(intent);
        });

        changeLocationsButton.setOnClickListener(v -> finish());
    }

    /**
     * Looks up the coordinates by the human-readable name and calls the map's JS function.
     */
    private void searchAndDrawPins(String source, String destination) {
        double[] sourceCoords = locationCoordinates.get(source);
        double[] destCoords = locationCoordinates.get(destination);

        if (sourceCoords != null && destCoords != null) {
            String jsCommand = String.format(
                    "javascript:drawPins('%s', '%s', %f, %f, %f, %f);",
                    source, destination,
                    sourceCoords[0], sourceCoords[1], // Source Lat, Lon
                    destCoords[0], destCoords[1]      // Destination Lat, Lon
            );
            Log.d(TAG, "Executing JS Command: " + jsCommand);

            // *** FIX STARTS HERE ***
            // Use the 2-argument version of evaluateJavascript for compatibility with minSdk 24
            mapWebView.evaluateJavascript(jsCommand, value -> {
                Log.d(TAG, "JS Execution Result: " + value);
            });
            // *** FIX ENDS HERE ***

        } else {
            String message = "Could not find coordinates for: " + (sourceCoords == null ? source : "") + (destCoords == null ? destination : "") + ". Check the input name.";
            Toast.makeText(this, message, Toast.LENGTH_LONG).show();
            Log.e(TAG, message);
            findViewById(R.id.confirmLocationsButton).setEnabled(false);
        }
    }
}