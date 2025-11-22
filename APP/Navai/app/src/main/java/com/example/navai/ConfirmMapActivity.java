package com.example.navai;

import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

public class ConfirmMapActivity extends AppCompatActivity {

    private String source;
    private String destination;
    private String vehicleType;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_confirm_map);

        Bundle extras = getIntent().getExtras();
        if (extras != null) {
            source = extras.getString("SOURCE_KEY");
            destination = extras.getString("DESTINATION_KEY");
            vehicleType = extras.getString("VEHICLE_TYPE_KEY");

            // You can display source/destination/vehicleType here if needed
        }

        Button searchRouteButton = findViewById(R.id.searchRouteButton);
        searchRouteButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                // In a real application, this is where you would call the routing algorithm.
                // For now, it's a placeholder.
                Toast.makeText(ConfirmMapActivity.this,
                        "Searching for route from " + source + " to " + destination + " for " + vehicleType,
                        Toast.LENGTH_LONG).show();
            }
        });
    }
}