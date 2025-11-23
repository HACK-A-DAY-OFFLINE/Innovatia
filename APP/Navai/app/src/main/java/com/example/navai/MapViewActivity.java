package com.example.navai;

import android.os.Bundle;
import android.util.Log;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.appcompat.app.AppCompatActivity;

public class MapViewActivity extends AppCompatActivity {

    private static final String TAG = "MapViewActivity";
    private WebView mapWebView;
    private String selectedRoute;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_map_view);

        // 1. Get the selected route from the Intent
        Bundle extras = getIntent().getExtras();
        if (extras != null) {
            selectedRoute = extras.getString(MainActivity.ROUTE_KEY, "City Center Loop"); // Default route
            Log.d(TAG, "Selected Route: " + selectedRoute);
        } else {
            selectedRoute = "City Center Loop";
        }

        // 2. Setup WebView
        mapWebView = findViewById(R.id.mapWebView);
        WebSettings webSettings = mapWebView.getSettings();
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);

        // Use a WebViewClient to know when the page has finished loading
        mapWebView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                // 3. Once the map is loaded, call the JavaScript function to draw the route
                if (selectedRoute != null) {
                    // Pass the route name/key directly to the JavaScript function
                    String jsCommand = String.format("javascript:drawPredefinedRoute('%s');", selectedRoute);
                    Log.d(TAG, "Executing JS Command: " + jsCommand);

                    // Execute the JS command
                    mapWebView.evaluateJavascript(jsCommand, value -> {
                        Log.d(TAG, "JS Execution Result: " + value);
                    });
                }
            }
        });

        // 4. Load the HTML file from the 'assets' folder
        mapWebView.loadUrl("file:///android_asset/navai_map.html");
    }
}
