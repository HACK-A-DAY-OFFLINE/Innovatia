package com.example.navai;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import android.widget.Button;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import java.util.Arrays;
import java.util.List;

public class MainActivity extends AppCompatActivity {

    private AutoCompleteTextView routeAutoComplete;

    // Hardcoded list of predefined routes
    public static final String[] PREDEFINED_ROUTES = new String[]{
            "Office to Home (Fastest)",
            "Home to Gym (Bike Lane)",
            "Gym to Cafe (Scenic)",
            "City Center Loop"
    };
    
    // Key used to pass the selected route to the MapViewActivity
    public static final String ROUTE_KEY = "PREDEFINED_ROUTE_KEY";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        routeAutoComplete = findViewById(R.id.routeAutoComplete);
        Button confirmButton = findViewById(R.id.confirmButton);

        // --- Setup Route Adapter ---
        ArrayAdapter<String> routeAdapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_dropdown_item_1line,
                PREDEFINED_ROUTES
        );
        routeAutoComplete.setAdapter(routeAdapter);
        routeAutoComplete.setThreshold(1); 

        confirmButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String selectedRoute = routeAutoComplete.getText().toString().trim();

                if (selectedRoute.isEmpty()) {
                    Toast.makeText(MainActivity.this, "Please select a route", Toast.LENGTH_SHORT).show();
                    return;
                }

                // Simple validation to ensure the selected route is in the predefined list
                List<String> validRoutes = Arrays.asList(PREDEFINED_ROUTES);
                if (!validRoutes.contains(selectedRoute)) {
                    Toast.makeText(MainActivity.this, "Invalid route selected", Toast.LENGTH_SHORT).show();
                    return;
                }
                
                // Pass the selected route name to the MapViewActivity
                Intent intent = new Intent(MainActivity.this, MapViewActivity.class);
                intent.putExtra(ROUTE_KEY, selectedRoute);
                startActivity(intent);
            }
        });
    }
}
