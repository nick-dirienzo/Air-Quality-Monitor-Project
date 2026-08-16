import os
import csv
import time
import serial
import threading
from collections import Counter
from pms5003 import PMS5003
from datetime import datetime
from enviroplus import gas

# === CONFIGURATION ===
SENSOR1_PORT = '/dev/ttyUSB0'
SENSOR2_PORT = '/dev/ttyUSB1'
BAUD_RATE = 9600
CSV_DIRECTORY = './AQ_Data'
CSV_FILENAME = 'pilot_study_data.csv'
LOOP_INTERVAL_SECONDS = 60
TON_CORRECTION_FACTOR = 60 / 63
NH3_BASELINE_RESISTANCE = 20000  # Change this to your measured baseline R0 in Ohms
NH3_A = 0.7823
NH3_K = 0.5368
# ============

# Sensor 1 = NO2 Sensor (Left Side - USB Port Labelled '1')
# Sensor 2 = SO2 Sensor (Right Side - USB Port Labelled '2')

# === LOCATION INFO ===
LOCATION_NAME = "Location"
LATITUDE = "<latitude>"
LONGITUDE = "<longitude>"
# ======================

# Ensure CSV directory exists
os.makedirs(CSV_DIRECTORY, exist_ok=True)
csv_file_path = os.path.join(CSV_DIRECTORY, CSV_FILENAME)

# === Define CSV header ===
column_names = [
    "Time", "Month", "Day", "Year",
    "Location", "Latitude", "Longitude",
    "Sensor 1 - ID", "Sensor 1 - Gas Concentration (PPB)", "Sensor 1 - Temperature (°C)",
    "Sensor 1 - Relative Humidity (%)", "Sensor 1 - ADC_G (Gas)", "Sensor 1 - ADC_T (Temp)",
    "Sensor 1 - ADC_H (RH)", "Sensor 1 - Ton", "Sensor 1 - Ton Corrected", "Sensor 1 - QC",
    "Sensor 2 - ID", "Sensor 2 - Gas Concentration (PPB)", "Sensor 2 - Temperature (°C)",
    "Sensor 2 - Relative Humidity (%)", "Sensor 2 - ADC_G (Gas)", "Sensor 2 - ADC_T (Temp)",
    "Sensor 2 - ADC_H (RH)", "Sensor 2 - Ton", "Sensor 2 - Ton Corrected", "Sensor 2 - QC",
    "PMS5003 - PM1.0 CF=1", "PMS5003 - PM2.5 CF=1", "PMS5003 - PM10 CF=1",
    "PMS5003 - PM1.0 ATM", "PMS5003 - PM2.5 ATM", "PMS5003 - PM10 ATM",
    "PMS5003 - >0.3um", ">0.5um", ">1.0um", ">2.5um", ">5.0um", ">10um",
    "NH3 - Baseline Resistance (Ω)", "NH3 - Current Resistance (Ω)", "NH3 - Estimated PPM"
]

# === QC FUNCTION ===
def qc_flag(sensor_values):
    if all(val in ("N/A", "ERROR") for val in sensor_values):
        return "❌ No Response"
    if any(val in ("N/A", "ERROR") for val in sensor_values):
        return "⚠️ Incomplete"
    try:
        gas = float(sensor_values[1])
        temp = float(sensor_values[2])
        rh = float(sensor_values[3])
    except (ValueError, IndexError):
        return "⚠️ Unreadable"
    if gas < 0 or temp < -50 or temp > 80 or rh < 0 or rh > 100:
        return "⚠️ Out of Range"
    return "✅ OK"
# =============================

# === SENSOR READER FUNCTION ===
def read_sensor(serial_obj, result_dict, label):
    try:
        # Time of measurement
        result_dict[f"{label}_time"] = time.strftime('%H:%M:%S')

        # Send measurement command and read response
        serial_obj.write(b'\r\n')
        measurement = serial_obj.readline().decode(errors='ignore').strip()
        values = measurement.split(',') if measurement else ["N/A"] * 6
        try:
            values[2] = str(round(float(values[2]) / 100, 2))  # Temp
            values[3] = str(round(float(values[3]) / 100, 2))  # RH
        except (IndexError, ValueError):
            pass
        result_dict[f"{label}_values"] = values
        serial_obj.write(b'e\n')
        eeprom = serial_obj.readlines()
        decoded = [line.decode(errors='ignore').strip() for line in eeprom]
        ton_line = decoded[3] if len(decoded) >= 4 else ""
        ton_value = ton_line.split(',')[-1].strip().replace("Ton ", "") if "Ton" in ton_line else "N/A"
        try:
            ton_corr = round(float(ton_value) * TON_CORRECTION_FACTOR, 2)
        except ValueError:
            ton_corr = "N/A"
        result_dict[f"{label}_ton"] = ton_value
        result_dict[f"{label}_ton_corrected"] = str(ton_corr)
    except Exception as e:
        print(f"❌ Error reading from {label}: {e}")
        result_dict[f"{label}_values"] = ["ERROR"] * 6
        result_dict[f"{label}_ton"] = "N/A"
        result_dict[f"{label}_ton_corrected"] = "N/A"

# === MAIN ROUTINE ===
try:
    print("🔌 Connecting to sensors...")
    ser1 = serial.Serial(SENSOR1_PORT, BAUD_RATE, timeout=3)
    ser2 = serial.Serial(SENSOR2_PORT, BAUD_RATE, timeout=3)
    pms5003 = PMS5003()
    print("✅ Serial ports opened!")

    # Live QC Counters
    qc_summary_s1 = Counter()
    qc_summary_s2 = Counter()

    with open(csv_file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(column_names)

        while True:
            start_time = time.time()
            sensor_data = {}

            # Get date/time metadata
            now = time.localtime()
            timestamp = time.strftime('%H:%M:%S', now)
            month = time.strftime('%m', now)
            day = time.strftime('%d', now)
            year = time.strftime('%Y', now)

            # Launch threads for Sensor 1 and Sensor 2
            t1 = threading.Thread(target=read_sensor, args=(ser1, sensor_data, "s1"))
            t2 = threading.Thread(target=read_sensor, args=(ser2, sensor_data, "s2"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            # Prepare row
            v1 = sensor_data.get("s1_values", ["N/A"] * 6)
            v2 = sensor_data.get("s2_values", ["N/A"] * 6)
            ton1 = sensor_data.get("s1_ton", "N/A")
            ton2 = sensor_data.get("s2_ton", "N/A")
            ton1c = sensor_data.get("s1_ton_corrected", "N/A")
            ton2c = sensor_data.get("s2_ton_corrected", "N/A")
            qc1 = qc_flag(v1)
            qc2 = qc_flag(v2)

            # Update Counters
            qc_summary_s1[qc1] += 1
            qc_summary_s2[qc2] += 1

            # Read PMS5003 as string and parse manually
            pms_raw = str(pms5003.read())
            lines = pms_raw.splitlines()
            parsed = {}
            for line in lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    parsed[key.strip()] = value.strip()

            pms_row = [
                parsed.get("PM1.0 ug/m3 (ultrafine particles)", "N/A"),
                parsed.get("PM2.5 ug/m3 (combustion particles, organic compounds, metals)", "N/A"),
                parsed.get("PM10 ug/m3  (dust, pollen, mould spores)", "N/A"),
                parsed.get("PM1.0 ug/m3 (atmos env)", "N/A"),
                parsed.get("PM2.5 ug/m3 (atmos env)", "N/A"),
                parsed.get("PM10 ug/m3 (atmos env)", "N/A"),
                parsed.get(">0.3um in 0.1L air", "N/A"),
                parsed.get(">0.5um in 0.1L air", "N/A"),
                parsed.get(">1.0um in 0.1L air", "N/A"),
                parsed.get(">2.5um in 0.1L air", "N/A"),
                parsed.get(">5.0um in 0.1L air", "N/A"),
                parsed.get(">10um in 0.1L air", "N/A")
            ]

            # Read NH3 sensor
            try:
                nh3_resistance = gas.read_all().nh3
                nh3_ppm = round((nh3_resistance / (NH3_BASELINE_RESISTANCE * NH3_A)) ** (-1 / NH3_K), 4)
            except Exception as e:
                print(f"❌ NH3 read error: {e}")
                nh3_resistance = "N/A"
                nh3_ppm = "N/A"

            row = [
                timestamp, month, day, year,
                LOCATION_NAME, LATITUDE, LONGITUDE,
                *v1, ton1, ton1c, qc1,
                *v2, ton2, ton2c, qc2,
                *pms_row,
                NH3_BASELINE_RESISTANCE, nh3_resistance, nh3_ppm
            ]

            # Print Summary
            print("📊 QC Summary so far:")
            print(f"Sensor 1: {dict(qc_summary_s1)}")
            print(f"Sensor 2: {dict(qc_summary_s2)}")

            # Print to terminal
            print(f"\n{timestamp} | Sensor 1: {v1} | Ton: {ton1} | Ton Corrected: {ton1c} | QC: {qc1}")
            print(f"{timestamp} | Sensor 2: {v2} | Ton: {ton2} | Ton Corrected: {ton2c} | QC: {qc2}")
            print(f"{timestamp} | PMS5003 parsed data: {pms_row}")
            print(f"{timestamp} | NH₃ resistance: {nh3_resistance} Ohms → Estimated PPM: {nh3_ppm}")
            print("Writing to CSV...\n")

            # Write to file
            writer.writerow(row)
            csvfile.flush()

            # Wait until next interval
            elapsed = time.time() - start_time
            wait_time = max(0, LOOP_INTERVAL_SECONDS - elapsed)
            print(f"Loop duration: {elapsed:.2f} seconds")
            print(f"Loop complete. Sleeping for {wait_time:.2f} seconds.\n" + "-"*60)
            time.sleep(wait_time)

except KeyboardInterrupt:
    print("Stopping script. Closing serial ports.")
    ser1.close()
    ser2.close()