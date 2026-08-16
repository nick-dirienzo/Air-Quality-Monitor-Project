import time
from datetime import datetime
from enviroplus import gas

# === CONFIGURATION ===
BASELINE_DURATION_MINUTES = 30         # Total time to run
READ_INTERVAL_SECONDS = 5              # Sample every 5 seconds
DISCARD_FIRST_MINUTES = 10             # Minutes to discard from start
num_readings = (BASELINE_DURATION_MINUTES * 60) // READ_INTERVAL_SECONDS
discard_count = (DISCARD_FIRST_MINUTES * 60) // READ_INTERVAL_SECONDS

# === STORAGE ===
resistance_readings = []
timestamps = []

def current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

print(f"Starting NH₃ baseline collection for {BASELINE_DURATION_MINUTES} minutes...")
print(f"Sampling every {READ_INTERVAL_SECONDS} seconds ({num_readings} readings total)")
print(f"Discarding first {DISCARD_FIRST_MINUTES} minutes ({discard_count} readings) for warm-up\n")

try:
    for i in range(num_readings):
        readings = gas.read_all()
        nh3_resistance = readings.nh3

        resistance_readings.append(nh3_resistance)
        timestamps.append(current_time())

        print(f"[{timestamps[-1]}] Reading {i+1}/{num_readings} → NH₃ resistance: {nh3_resistance:.2f} Ohms")

        time.sleep(READ_INTERVAL_SECONDS)

    # === FINAL BASELINE RESULT ===
    usable_readings = resistance_readings[discard_count:]
    if usable_readings:
        r0 = sum(usable_readings) / len(usable_readings)
        print("\n Baseline complete!")
        print(f"NH₃ baseline resistance (R₀): {r0:.2f} Ohms (from last {len(usable_readings)} readings)")
    else:
        print("\n Not enough data collected after discarding warm-up period.")

except KeyboardInterrupt:
    print("\n Baseline collection interrupted.")

except Exception as e:
    print(f"Error: {e}")