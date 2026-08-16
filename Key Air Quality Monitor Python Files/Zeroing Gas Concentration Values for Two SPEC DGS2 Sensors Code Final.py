import serial
import time
from datetime import datetime

# List of serial ports the SPEC sensors are connected to
# === CONFIGURATION ===
SENSOR_PORTS = ['/dev/ttyUSB0', '/dev/ttyUSB1']  # Modify as needed
BAUD_RATE = 9600  # Typical for DGS2 sensors
# =====================

# Sensor SN of XXXXXX = NO2 Sensor
# Sensor SN of XXXXXX = SO2 Sensor
# Sensor SN of XXXXXX = H2S Sensor

def current_time(): # A function to get the current time in a specific format
    return datetime.now().strftime('%Y-%m-%d %H-%M-%S') # Format: YYYY-MM-DD HH:MM:SS

def read_measurements(ser, count=5, delay=1, label_prefix=''): # A function to read measurements from the sensor
    """Take 'count' readings at intervals, labeling and timestamping each"""
    readings = [] # List to store readings
    for i in range(count): # Loop to take 'count' readings
        ser.write(b'\r\n')  # Send single-read command
        time.sleep(delay) # Wait for the sensor to respond
        response = ser.read_all().decode('utf-8', errors='ignore').strip() # Read the response
        label = f"{count - i if label_prefix == 'Before' else i + 1} second{'s' if count - i != 1 else ''} {'before' if label_prefix == 'Before' else 'after'}" # Label for the reading
        timestamp = current_time() # Get the current time
        readings.append((label, timestamp, response)) # Append the reading to the list
    return readings # Return the list of readings

def zero_sensor_and_measure(port): # A function to zero the sensor and take measurements
    try: # Open the serial port
        with serial.Serial(port, BAUD_RATE, timeout=2) as ser: # Open the serial port
            print(f"n--- {port}: Collecting 5 baseline measurements before zeroing ---") # Collect baseline measurements
            before_readings = read_measurements(ser, count=5, delay=1, label_prefix='Before') # Read 5 measurements before zeroing

            zero_time = current_time() # Get the current time for zeroing
            print(f"{port}: Sending Zero (Z) command at {zero_time}...") # Send zeroing command
            ser.write(b'Z\r') # Send zeroing command
            time.sleep(1) # Wait for the sensor to process the command
            ser.reset_input_buffer()  # <-- Flush any leftover confirmation from zeroing

            print(f"{port}: Collecting 5 measurements after zeroing...") # Collect measurements after zeroing
            after_readings = read_measurements(ser, count=5, delay=1, label_prefix='After') # Read 5 measurements after zeroing

            # Display all readings
            print(f"\nResults for {port}:") # Print the results
            for label, timestamp, r in before_readings: # Loop through the before readings
                print(f"  {label} @ {timestamp}: {r}") # Print the before readings
            print(f"  >>> Zeroing command sent at: {zero_time}") # Print the zeroing command time
            for label, timestamp, r in after_readings: # Loop through the after readings
                print(f"  {label} @ {timestamp}: {r}") # Print the after readings

    except serial.SerialException as e: # Handle serial port exceptions
        print(f"Error with {port}: {e}") # Print the error message

if __name__ == "__main__": # Main function to execute the script
    for port in SENSOR_PORTS: # Loop through each sensor port
        zero_sensor_and_measure(port) # Call the zeroing and measurement function