# file: analysis_modules/anomaly_detector.py (v1.4 - Added Cabin Pressure Alerts)

import pandas as pd
import argparse
import os
from typing import List

class AnomalyDetector:
    """
    Phát hiện các điểm bất thường trong dữ liệu telemetry của chuyến bay
    dựa trên một bộ các quy tắc được định nghĩa trước.
    """
    def __init__(self):
        """
        Khởi tạo detector và định nghĩa các ngưỡng (thresholds) cho các quy tắc.
        """
        print("AnomalyDetector (Rule-Based v1.5 - Adjusted Thresholds & ECAM Alerts) initialized.")
        self.flap_asymmetry_threshold_deg = 2.0 # Adjusted for more sensitivity
        self.hydraulic_pressure_threshold_psi = 900.0 # Adjusted for more sensitivity
        self.g_force_deviation_threshold = 0.3 # Adjusted for more sensitivity

    def _check_flap_asymmetry(self, df: pd.DataFrame) -> tuple[bool, int]:
        df['temp_flap_diff'] = abs(df['left_flap_angle_deg'] - df['right_flap_angle_deg'])
        asymmetric_events = df[df['temp_flap_diff'] > self.flap_asymmetry_threshold_deg]
        del df['temp_flap_diff']
        if not asymmetric_events.empty:
            first_detection_timestamp = int(asymmetric_events.iloc[0]['timestamp'])
            print(f"  -> [RULE CHECK PASSED] Flap asymmetry DETECTED at timestamp: {first_detection_timestamp}s")
            return True, first_detection_timestamp
        return False, -1

    def _check_hydraulic_failure(self, df: pd.DataFrame) -> tuple[bool, int]:
        hydraulic_loss_events = df[df['green_hydraulic_pressure_psi'] < self.hydraulic_pressure_threshold_psi]
        if not hydraulic_loss_events.empty:
            first_detection_timestamp = int(hydraulic_loss_events.iloc[0]['timestamp'])
            print(f"  -> [RULE CHECK PASSED] Green hydraulic pressure loss DETECTED at timestamp: {first_detection_timestamp}s")
            return True, first_detection_timestamp
        return False, -1

    def _check_sensor_discrepancy(self, df: pd.DataFrame) -> tuple[bool, int]:
        discrepancy_events = df[(df['flap_lever_position'] > 0) & (df['right_flap_angle_deg'] > 0) & (df['right_flap_sensor_faulty_output_deg'] == 0)]
        if not discrepancy_events.empty:
            first_detection_timestamp = int(discrepancy_events.iloc[0]['timestamp'])
            print(f"  -> [RULE CHECK PASSED] Sensor discrepancy DETECTED at timestamp: {first_detection_timestamp}s")
            return True, first_detection_timestamp
        return False, -1

    def _check_g_force_anomaly(self, df: pd.DataFrame) -> tuple[bool, int]:
        # Removed time window to check for G-force anomalies throughout the flight
        max_g_force = df['vertical_g_force'].max()
        print(f"  -> [DEBUG] G-Force Check: Max G-force found = {max_g_force:.4f}")
        g_force_events = df[abs(df['vertical_g_force'] - 1.0) > self.g_force_deviation_threshold]
        if not g_force_events.empty:
            first_detection_timestamp = int(g_force_events.iloc[0]['timestamp'])
            print(f"  -> [RULE CHECK PASSED] Significant G-force anomaly DETECTED at timestamp: {first_detection_timestamp}s")
            return True, first_detection_timestamp
        return False, -1

    def _check_critical_ecam_alerts(self, df: pd.DataFrame) -> tuple[bool, int]:
        critical_alerts = ['OVERSPEED', 'ENG 1 FIRE', 'ENG 1 STALL', 'F/CTL FLAP SYS', 'CAB PR SYS 1 FAULT', 'CAB PR EXCESS CAB ALT', 'GEAR NOT DOWN', 'F/CTL FLAPS LOCKED']
        print(f"  -> [DEBUG] ECAM Check: Looking for alerts: {critical_alerts}")
        for alert in critical_alerts:
            try:
                df['alert_present'] = df['ecam_alerts'].apply(lambda x: alert in str(x))
                alert_events = df[df['alert_present'] == True]
                if not alert_events.empty:
                    first_detection_timestamp = int(alert_events.iloc[0]['timestamp'])
                    print(f"  -> [RULE CHECK PASSED] Critical ECAM alert '{alert}' DETECTED at timestamp: {first_detection_timestamp}s")
                    del df['alert_present']
                    return True, first_detection_timestamp
            finally:
                if 'alert_present' in df.columns:
                    del df['alert_present']
        return False, -1

    def _check_motor_current_failure(self, df: pd.DataFrame) -> tuple[bool, int]:
        motor_failure_events = df[(df['timestamp'] > 90) & (df['flap_lever_position'] > 0) & (df['left_flap_motor_current'] == 0.0)]
        if not motor_failure_events.empty:
            first_detection_timestamp = int(motor_failure_events.iloc[0]['timestamp'])
            print(f"  -> [RULE CHECK PASSED] Left flap motor current failure DETECTED at timestamp: {first_detection_timestamp}s")
            return True, first_detection_timestamp
        return False, -1

    def _check_flap_stuck(self, df: pd.DataFrame) -> tuple[bool, int]:
        """More robust check for stuck flaps."""
        # Find where the flap lever position is commanded to a new, non-zero position
        df['lever_change'] = df['flap_lever_position'].diff()
        # We only care about when the lever is moved to a new extended position (1, 2, 3, 4)
        lever_change_points = df[(df['lever_change'] > 0) & (df['flap_lever_position'] > 0)]

        for index, change_point in lever_change_points.iterrows():
            # Define a time window to observe if the flaps react after the command
            start_time = change_point['timestamp']
            end_time = start_time + 4 # Check for 4 seconds after lever change
            time_window = df[(df['timestamp'] > start_time) & (df['timestamp'] <= end_time)]

            if not time_window.empty:
                # Get the flap angle at the moment the lever changed
                initial_flap_angle = df.loc[index, 'left_flap_angle_deg']
                
                # Get the maximum change in flap angle within the time window
                max_angle_change = (time_window['left_flap_angle_deg'] - initial_flap_angle).abs().max()
                
                # If the angle hasn't changed by at least 0.5 degree, it's likely stuck
                if max_angle_change < 0.5:
                    timestamp = int(start_time)
                    print(f"  -> [RULE CHECK PASSED] Flap stuck/unresponsive DETECTED at timestamp: {timestamp}s")
                    # Clean up the temporary column before returning
                    if 'lever_change' in df.columns:
                        del df['lever_change']
                    return True, timestamp

        # Clean up the temporary column if no anomaly is found
        if 'lever_change' in df.columns:
            del df['lever_change']
            
        return False, -1

    def detect(self, telemetry_df: pd.DataFrame) -> list[tuple[str, int]]:
        print("\nStarting anomaly detection process...")
        detected_anomalies = []
        checks = {
            "FLAP_ASYMMETRY": self._check_flap_asymmetry,
            "GREEN_HYDRAULIC_LOSS": self._check_hydraulic_failure,
            "SENSOR_FAILURE": self._check_sensor_discrepancy,
            "G_FORCE_ANOMALY": self._check_g_force_anomaly,
            "CRITICAL_ECAM_ALERT": self._check_critical_ecam_alerts,
            "MOTOR_CURRENT_FAILURE": self._check_motor_current_failure,
            "FLAP_STUCK": self._check_flap_stuck # New check
        }
        for name, check_func in checks.items():
            is_detected, timestamp = check_func(telemetry_df)
            if is_detected:
                detected_anomalies.append((name, timestamp))
        if not detected_anomalies:
            print("No anomalies detected based on the current rules.")
        return detected_anomalies

# main function remains the same