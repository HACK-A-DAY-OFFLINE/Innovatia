package com.example.navai;

import android.content.Intent;
import android.os.AsyncTask;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

public class ConfirmMapActivity extends AppCompatActivity {

    private static final String TAG = "ConfirmMapActivity";
    // TODO: Change this to the actual IP address/port where your Python API is running
    // If running on your local machine, use your machine's IP, or 10.0.2.2 for emulator loopback
    private static final String API_BASE_URL = "http://10.0.2.2:5000/api/route";

    private String sourceName;
    private String destinationName;
    private String vehicleType;
    private double sourceLat, sourceLon, destLat, destLon;

    private TextView routeDetailsTextView;
    private ProgressBar progressBar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_confirm_map);

        routeDetailsTextView = findViewById(R.id.routeDetailsTextView); // Assuming this exists in layout
        progressBar = findViewById(R.id.progressBar); // Assuming this exists in layout
        Button searchRouteButton = findViewById(R.id.searchRouteButton);

        Bundle extras = getIntent().getExtras();
        if (extras != null) {
            sourceName = extras.getString("SOURCE_NAME_KEY");
            destinationName = extras.getString("DESTINATION_NAME_KEY");
            vehicleType = extras.getString("VEHICLE_TYPE_KEY");
            sourceLat = extras.getDouble("SOURCE_LAT");
            sourceLon = extras.getDouble("SOURCE_LON");
            destLat = extras.getDouble("DESTINATION_LAT");
            destLon = extras.getDouble("DESTINATION_LON");

            // Display details to the user
            routeDetailsTextView.setText(
                    String.format("Route Details:\nSource: %s\nDestination: %s\nVehicle: %s",
                            sourceName, destinationName, vehicleType)
            );
        } else {
            Toast.makeText(this, "Missing route parameters.", Toast.LENGTH_LONG).show();
            finish();
            return;
        }

        searchRouteButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                new FetchRouteTask().execute(sourceLat, sourceLon, destLat, destLon);
            }
        });
    }

    /**
     * AsyncTask to handle network operations for fetching the route.
     */
    private class FetchRouteTask extends AsyncTask<Double, Void, String> {

        @Override
        protected void onPreExecute() {
            progressBar.setVisibility(View.VISIBLE);
            Toast.makeText(ConfirmMapActivity.this, "Calculating best route...", Toast.LENGTH_SHORT).show();
        }

        @Override
        protected String doInBackground(Double... params) {
            double sLat = params[0];
            double sLon = params[1];
            double dLat = params[2];
            double dLon = params[3];

            try {
                // Build the URL with URL-encoded parameters
                String urlString = API_BASE_URL +
                        "?source_lat=" + sLat +
                        "&source_lon=" + sLon +
                        "&dest_lat=" + dLat +
                        "&dest_lon=" + dLon +
                        "&vehicle=" + URLEncoder.encode(vehicleType, StandardCharsets.UTF_8.name());

                Log.d(TAG, "API URL: " + urlString);

                URL url = new URL(urlString);
                HttpURLConnection connection = (HttpURLConnection) url.openConnection();
                connection.setRequestMethod("GET");
                connection.setConnectTimeout(10000); // 10 seconds
                connection.setReadTimeout(10000);    // 10 seconds

                int responseCode = connection.getResponseCode();

                if (responseCode == HttpURLConnection.HTTP_OK) {
                    BufferedReader in = new BufferedReader(new InputStreamReader(connection.getInputStream()));
                    String inputLine;
                    StringBuilder content = new StringBuilder();
                    while ((inputLine = in.readLine()) != null) {
                        content.append(inputLine);
                    }
                    in.close();
                    connection.disconnect();
                    return content.toString();
                } else {
                    Log.e(TAG, "API Request failed. Response Code: " + responseCode);
                    // Read error stream for more details
                    BufferedReader errorReader = new BufferedReader(new InputStreamReader(connection.getErrorStream()));
                    StringBuilder errorContent = new StringBuilder();
                    String errorLine;
                    while ((errorLine = errorReader.readLine()) != null) {
                        errorContent.append(errorLine);
                    }
                    errorReader.close();
                    Log.e(TAG, "API Error Body: " + errorContent.toString());

                    return null;
                }
            } catch (Exception e) {
                Log.e(TAG, "Network Error: " + e.getMessage(), e);
                return null;
            }
        }

        @Override
        protected void onPostExecute(String result) {
            progressBar.setVisibility(View.GONE);

            if (result != null && !result.isEmpty()) {
                Log.d(TAG, "API Response: " + result);

                // Launch MapViewActivity with the raw JSON route data
                Intent intent = new Intent(ConfirmMapActivity.this, MapViewActivity.class);
                intent.putExtra("ROUTE_COORDINATES_JSON", result);
                intent.putExtra("SOURCE_NAME_KEY", sourceName);
                intent.putExtra("DESTINATION_NAME_KEY", destinationName);
                startActivity(intent);
                finish(); // Close this activity

            } else {
                Toast.makeText(ConfirmMapActivity.this,
                        "Failed to find route. Check API server connection.",
                        Toast.LENGTH_LONG).show();
            }
        }
    }
}