/**
 * ESP32 Battery Switch Monitor
 * 
 * Reads battery switch status and outputs to Jetson GPIO.
 * Simple firmware - no BLE/WiFi needed.
 */

#include <Arduino.h>

// Input pins (battery switches)
const int BAT1_SWITCH_PIN = 26;
const int BAT2_SWITCH_PIN = 27;

// Output pins (to Jetson)
const int BAT1_OUTPUT_PIN = 32;
const int BAT2_OUTPUT_PIN = 33;

// Debounce settings
const unsigned long DEBOUNCE_MS = 50;

// State
bool bat1_state = false;
bool bat2_state = false;
unsigned long bat1_last_change = 0;
unsigned long bat2_last_change = 0;

void setup() {
    Serial.begin(115200);
    Serial.println("ESP32 Battery Monitor");
    
    // Configure input pins with pull-up
    pinMode(BAT1_SWITCH_PIN, INPUT_PULLUP);
    pinMode(BAT2_SWITCH_PIN, INPUT_PULLUP);
    
    // Configure output pins
    pinMode(BAT1_OUTPUT_PIN, OUTPUT);
    pinMode(BAT2_OUTPUT_PIN, OUTPUT);
    
    // Initialize outputs low
    digitalWrite(BAT1_OUTPUT_PIN, LOW);
    digitalWrite(BAT2_OUTPUT_PIN, LOW);
    
    // Read initial state
    bat1_state = !digitalRead(BAT1_SWITCH_PIN);  // Active low switch
    bat2_state = !digitalRead(BAT2_SWITCH_PIN);
    
    digitalWrite(BAT1_OUTPUT_PIN, bat1_state ? HIGH : LOW);
    digitalWrite(BAT2_OUTPUT_PIN, bat2_state ? HIGH : LOW);
    
    Serial.printf("Initial: BAT1=%d, BAT2=%d\n", bat1_state, bat2_state);
}

void loop() {
    unsigned long now = millis();
    
    // Read BAT1 with debounce
    bool bat1_raw = !digitalRead(BAT1_SWITCH_PIN);
    if (bat1_raw != bat1_state) {
        if (now - bat1_last_change > DEBOUNCE_MS) {
            bat1_state = bat1_raw;
            bat1_last_change = now;
            digitalWrite(BAT1_OUTPUT_PIN, bat1_state ? HIGH : LOW);
            Serial.printf("BAT1 changed: %d\n", bat1_state);
        }
    } else {
        bat1_last_change = now;
    }
    
    // Read BAT2 with debounce
    bool bat2_raw = !digitalRead(BAT2_SWITCH_PIN);
    if (bat2_raw != bat2_state) {
        if (now - bat2_last_change > DEBOUNCE_MS) {
            bat2_state = bat2_raw;
            bat2_last_change = now;
            digitalWrite(BAT2_OUTPUT_PIN, bat2_state ? HIGH : LOW);
            Serial.printf("BAT2 changed: %d\n", bat2_state);
        }
    } else {
        bat2_last_change = now;
    }
    
    // Small delay (20ms = 50Hz)
    delay(20);
}
