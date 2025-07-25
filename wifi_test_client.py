#!/usr/bin/env python3
import os
import re
import time
import socket
import subprocess
from datetime import datetime
import pytz  # Add this import
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET  # Import config

# Get hostname as device ID
device_id = socket.gethostname()

# Connect to InfluxDB
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

def get_wifi_stats():
    try:
        iw_output = subprocess.check_output("iw wlan0 link", shell=True).decode()
        rssi = None
        ssid = None
        bssid = None  # MAC address of the connected AP
        for line in iw_output.split("\n"):
            if "signal:" in line:
                rssi = int(line.strip().split()[1])
            if "SSID:" in line:
                ssid = line.strip().split(":", 1)[1].strip()
            if "Connected to" in line:
                bssid = line.strip().split()[-1]
        return ssid, rssi, bssid
    except Exception as e:
        print("Error getting wifi stats:", e)
        return None, None, None

def run_ping_test(target="8.8.8.8"):
    try:
        output = subprocess.check_output(f"ping -c 4 {target}", shell=True).decode()
        for line in output.split("\n"):
            if "avg" in line:
                return float(line.split('/')[4])
    except Exception as e:
        print("Error in ping test:", e)
    return None

def run_speedtest():
    try:
        result = subprocess.check_output("speedtest-cli --secure --simple", shell=True).decode()
        download = upload = None
        for line in result.split("\n"):
            if "Download" in line:
                download = float(line.split()[1])
            if "Upload" in line:
                upload = float(line.split()[1])
        return download, upload
    except Exception as e:
        print("Error running speedtest:", e)
        return None, None

def log_data():
    ssid, rssi, bssid = get_wifi_stats()
    getserial = os.popen('snmpget -v 2c -c private 10.42.0.2 .1.3.6.1.4.1.17713.22.1.1.1.4.0')
    readserial = getserial.read()
    serial_number = re.findall(r'"(.*?)"', readserial)[0]
    ping = run_ping_test()
#    download, upload = run_speedtest()

    # Set timezone to Australia/Melbourne
    melbourne_tz = pytz.timezone("Australia/Melbourne")
    timestamp = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(melbourne_tz)

    point = Point("wifi_test") \
        .tag("serial_number", serial_number) \
        .tag("device", device_id) \
        .tag("ssid", ssid or "unknown") \
        .tag("bssid", bssid or "unknown") \
        .field("rssi", rssi if rssi is not None else -100) \
        .field("ping_ms", ping if ping is not None else 0.0) \
        .time(timestamp)
#        .field("download_mbps", download if download else 0.0) \
#        .field("upload_mbps", upload if upload else 0.0) \

    write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
    print(f"Logged data at {timestamp}")

if __name__ == "__main__":
    while True:
        log_data()
        time.sleep(60)  # Wait 5 minutes between tests
