# test_anomaly_detector.py

import os
import pandas as pd
import json
from analysis_modules.anomaly_detector import AnomalyDetector

# Define the project root (assuming this script is in the project root)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SIMULATION_RUNS_DIR = os.path.join(PROJECT_ROOT, "outputs", "project_outputs", "simulation_runs")

def run_test_for_scenario(scenario_name: str) -> tuple[str, str, str]:
    """
    Runs anomaly detection for a single scenario and compares with ground truth.
    Returns (scenario_name, "PASSED" or "FAILED" or "SKIPPED", "Reason")
    """
    scenario_dir = os.path.join(SIMULATION_RUNS_DIR, scenario_name)
    telemetry_path = os.path.join(scenario_dir, "telemetry.csv")
    ground_truth_path = os.path.join(scenario_dir, "ground_truth.json")

    if not os.path.exists(telemetry_path) or not os.path.exists(ground_truth_path):
        return scenario_name, "SKIPPED", "Telemetry or Ground Truth file not found."

    try:
        telemetry_df = pd.read_csv(telemetry_path)
        with open(ground_truth_path, 'r', encoding='utf-8') as f:
            ground_truth = json.load(f)

        detector = AnomalyDetector()
        detected_anomalies = detector.detect(telemetry_df)

        expected_anomaly = ground_truth.get("is_anomaly", False)
        
        test_status = "FAILED"
        reason = ""

        if expected_anomaly:
            if detected_anomalies:
                # For now, just check if any anomaly is detected when expected
                # A more robust test would check specific anomaly types and timestamps
                test_status = "PASSED"
                reason = f"Anomaly expected and detected: {detected_anomalies}"
            else:
                test_status = "FAILED"
                reason = "Anomaly expected but NOT detected."
        else: # No anomaly expected
            if not detected_anomalies:
                test_status = "PASSED"
                reason = "No anomaly expected and none detected."
            else:
                test_status = "FAILED"
                reason = f"No anomaly expected but detected: {detected_anomalies}"
        
        return scenario_name, test_status, reason

    except Exception as e:
        return scenario_name, "ERROR", f"An error occurred: {e}"

def main():
    print("=== Running Anomaly Detector Tests ===")
    
    # Get all scenario directories
    scenario_names = [d for d in os.listdir(SIMULATION_RUNS_DIR) if os.path.isdir(os.path.join(SIMULATION_RUNS_DIR, d))]
    
    results = []
    for scenario_name in sorted(scenario_names): # Sort for consistent output
        print(f"Testing scenario: {scenario_name}...")
        scenario_name, status, reason = run_test_for_scenario(scenario_name)
        results.append((scenario_name, status, reason))
    
    print("\n=== Test Summary ===")
    all_passed = True
    for scenario_name, status, reason in results:
        print(f"Testing {scenario_name}... {status}")
        if status != "PASSED":
            all_passed = False
            if reason:
                print(f"  Reason: {reason}")
    
    print("\n=====================")
    if all_passed:
        print("ALL ANOMALY DETECTOR TESTS PASSED!")
    else:
        print("SOME ANOMALY DETECTOR TESTS FAILED or ENCOUNTERED ERRORS.")
    print("=====================")

if __name__ == '__main__':
    main()