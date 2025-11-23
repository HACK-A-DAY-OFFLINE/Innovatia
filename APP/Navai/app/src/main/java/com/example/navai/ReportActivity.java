package com.example.navai;

import android.os.Bundle;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.appbar.MaterialToolbar;

import java.util.ArrayList;
import java.util.List;

public class ReportActivity extends AppCompatActivity {

    private AutoCompleteTextView locationAutoComplete;
    private AutoCompleteTextView issueTypeAutoComplete;
    private EditText descriptionEditText;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_report);

        // Setup Toolbar
        MaterialToolbar toolbar = findViewById(R.id.reportToolbar);
        toolbar.setNavigationOnClickListener(v -> finish()); // Allows 'back' navigation

        // Initialize Views
        locationAutoComplete = findViewById(R.id.reportLocationAutoComplete);
        issueTypeAutoComplete = findViewById(R.id.issueTypeAutoComplete);
        descriptionEditText = findViewById(R.id.descriptionEditText);
        Button submitReportButton = findViewById(R.id.submitReportButton);

        // --- 1. Location Suggestions Adapter ---
        // Reuse the location names from the GeoJSON utility for the report location
        List<String> locationNames = new ArrayList<>(
                GeoJsonParserUtility.loadLocationCoordinates(this).keySet()
        );

        ArrayAdapter<String> locationAdapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_dropdown_item_1line,
                locationNames
        );
        locationAutoComplete.setAdapter(locationAdapter);
        locationAutoComplete.setThreshold(1);

        // --- 2. Issue Type Adapter ---
        String[] issueTypes = new String[]{"Pothole", "Minor Accident", "Major Accident", "Road Closure", "Hazard"};
        ArrayAdapter<String> issueAdapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_dropdown_item_1line,
                issueTypes
        );
        issueTypeAutoComplete.setAdapter(issueAdapter);

        // --- 3. Submit Button Listener ---
        submitReportButton.setOnClickListener(v -> {
            String location = locationAutoComplete.getText().toString().trim();
            String issue = issueTypeAutoComplete.getText().toString().trim();
            String description = descriptionEditText.getText().toString().trim();

            if (location.isEmpty() || issue.isEmpty()) {
                Toast.makeText(this, "Please select a location and issue type.", Toast.LENGTH_SHORT).show();
                return;
            }

            // In a real application, you would send this data to a database (e.g., Firestore)
            // along with the user's ID, current time, and coordinates of the location.
            Toast.makeText(this, "Report of '" + issue + "' at " + location + " submitted successfully!", Toast.LENGTH_LONG).show();

            // Clear fields and navigate back to Main Activity
            finish();
        });
    }
}