import csv
import os
import time
from datetime import datetime

class Logger:
    def __init__(self):
        self.recording = False
        self.record_start_time = None
        self.pressure_log_path = None
        self.valve_log_path = None

    def start(self):
        self.recording = True
        self.record_start_time = time.perf_counter()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = os.path.dirname(os.path.abspath(__file__))
        self.pressure_log_path = os.path.join(log_dir, f"pressure_{ts}.csv")
        self.valve_log_path = os.path.join(log_dir, f"valves_{ts}.csv")
        with open(self.pressure_log_path, 'w', newline='') as f:
            csv.writer(f).writerow(["time_elapsed", "P1_Pressurant_bar", "P2_OxidiserTank_bar", "P3_Injector_bar"])
        with open(self.valve_log_path, 'w', newline='') as f:
            csv.writer(f).writerow(["time_elapsed", "Solenoid_Valve_1", "Solenoid_Valve_2", "Servo_Valve_1"])

    def stop(self):
        self.recording = False
        self.record_start_time = None

    def log_pressures(self, values):
        if not self.recording or not self.pressure_log_path:
            return
        elapsed = round(time.perf_counter() - self.record_start_time, 4)
        with open(self.pressure_log_path, 'a', newline='') as f:
            csv.writer(f).writerow([elapsed] + [f"{v:.4f}" for v in values])

    def log_valve_state(self, valve_states):
        if not self.recording or not self.valve_log_path:
            return
        elapsed = round(time.perf_counter() - self.record_start_time, 4)
        with open(self.valve_log_path, 'a', newline='') as f:
            csv.writer(f).writerow([
                elapsed,
                "OPEN" if valve_states[0] else "CLOSED",
                "OPEN" if valve_states[1] else "CLOSED",
                "OPEN" if valve_states[2] else "CLOSED",
            ])