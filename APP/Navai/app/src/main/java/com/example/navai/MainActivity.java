// MainActivity.java (MODIFIED)
package com.example.navai;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import android.widget.Button;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.textfield.TextInputEditText;

import java.util.ArrayList;
import java.util.List;

public class MainActivity extends AppCompatActivity {

    private AutoCompleteTextView sourceAutoComplete;
    private AutoCompleteTextView destinationAutoComplete;
    private AutoCompleteTextView vehicleTypeAutoComplete;

    // Hardcoded locations for auto-complete simulation
    // NOTE: In a real app, you would fetch these from GeoJsonParserUtility or a database.
    private final String[] locationNames = new String[] {
            "MG Road", "Cubbon Park", "Koramangala", "Indiranagar", "Electronic City",
            "Silk Board Junction", "Shivajinagar"
    };

    // Placeholder coordinates for the above locations (lat, lon)
    private final double[][] locationCoords = new double[][] {
            {12.9757, 77.6074}, // MG Road
            {12.9759, 77.5946}, // Cubbon Park
            {12.9352, 77.6245}, // Koramangala
            {12.9738, 77.6406}, // Indiranagar
            {12.8465, 77.6655}, // Electronic City
            {12.9359, 77.6256}, // Silk Board Junction
            {12.9839, 77.6033}  // Shivajinagar
    };

    // Helper to get coordinates by name
    private double[] getCoordsByName(String name) {
        for (int i = 0; i < locationNames.length; i++) {
            if (locationNames[i].equalsIgnoreCase(name)) {
                return locationCoords[i];
            }
        }
        return null;
    }


    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // Assuming your activity_main.xml uses these IDs/Widgets now
        sourceAutoComplete = findViewById(R.id.sourceAutoComplete);
        destinationAutoComplete = findViewById(R.id.destinationAutoComplete);
        vehicleTypeAutoComplete = findViewById(R.id.vehicleTypeAutoComplete);
        Button confirmButton = findViewById(R.id.confirmButton);

        // --- 1. Vehicle Type Adapter (Original) ---
        String[] vehicleTypes = new String[]{"Sedan", "SUV", "Truck", "Bike"};
        ArrayAdapter<String> vehicleAdapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_dropdown_item_1line,
                vehicleTypes
        );
        vehicleTypeAutoComplete.setAdapter(vehicleAdapter);


        // --- 2. Location Adapter ---
        ArrayAdapter<String> locationAdapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_dropdown_item_1line,
                locationNames
        );

        // Apply Location Adapter to Source and Destination
        sourceAutoComplete.setAdapter(locationAdapter);
        destinationAutoComplete.setAdapter(locationAdapter);
        sourceAutoComplete.setThreshold(1); // Start suggesting after 1 character
        destinationAutoComplete.setThreshold(1);


        confirmButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String sourceName = sourceAutoComplete.getText().toString().trim();
                String destinationName = destinationAutoComplete.getText().toString().trim();
                String vehicleType = vehicleTypeAutoComplete.getText().toString().trim();

                if (sourceName.isEmpty() || destinationName.isEmpty() || vehicleType.isEmpty()) {
                    Toast.makeText(MainActivity.this, "Please fill all fields", Toast.LENGTH_SHORT).show();
                    return;
                }

                double[] sourceCoords = getCoordsByName(sourceName);
                double[] destCoords = getCoordsByName(destinationName);

                if (sourceCoords == null || destCoords == null) {
                    Toast.makeText(MainActivity.this, "Please select a valid location from the suggestions.", Toast.LENGTH_LONG).show();
                    return;
                }

                // Launch ConfirmMapActivity with all necessary details including coordinates
                Intent intent = new Intent(MainActivity.this, ConfirmMapActivity.class);

                intent.putExtra("SOURCE_NAME_KEY", sourceName);
                intent.putExtra("DESTINATION_NAME_KEY", destinationName);
                intent.putExtra("VEHICLE_TYPE_KEY", vehicleType);

                // Pass coordinates for the API call in the next activity
                intent.putExtra("SOURCE_LAT", sourceCoords[0]);
                intent.putExtra("SOURCE_LON", sourceCoords[1]);
                intent.putExtra("DESTINATION_LAT", destCoords[0]);
                intent.putExtra("DESTINATION_LON", destCoords[1]);

                startActivity(intent);
            }
        });
    }
}