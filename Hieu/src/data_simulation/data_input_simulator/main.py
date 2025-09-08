# file: main.py (v1.0 - Central Control Panel)
# ruff: noqa: E402

import sys
import os
import argparse
import pandas as pd
import random # Added back import for random


# --- Logic tự nhận biết đường dẫn ---
# Đảm bảo các module con có thể được import từ bất cứ đâu
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.data_simulation.data_input_simulator.main_simulator import ScenarioSimulator
from src.data_simulation.data_input_simulator.scenario_loader import ScenarioLoader
from src.data_analysis.analysis_modules.anomaly_detector import AnomalyDetector
from src.data_analysis.analysis_modules.hfacs_analyzer import HFACSAnalyzer
from src.data_analysis.analysis_modules.risk_engine import RiskTriageEngine
from src.data_analysis.analysis_modules.plotting_utils import plot_telemetry_and_report # New import

# --- Cấu hình Toàn cục ---
# Di chuyển các biến cấu hình ra đây để dễ quản lý
PROJECT_ID = "aviation-classifier-sa"
LOCATION = "us-central1"
CREDENTIALS_PATH = os.path.join(_PROJECT_ROOT, "gcloud_credentials.json")


def health_check():
    """
    Thực hiện kiểm tra sức khỏe của từng module cốt lõi.
    """
    print("\n" + "="*50)
    print("=== RUNNING SYSTEM HEALTH CHECKS ===")
    print("="*50)
    
    # Check 1: Data Input Simulator
    print("\n[CHECK 1/3] Testing Data Input Simulator...")
    try:
        simulator = ScenarioSimulator(scenario_name='flap_jam')
        simulator.run()
        data = simulator.get_data()
        assert isinstance(data['telemetry'], pd.DataFrame), "Telemetry data is not a DataFrame."
        assert not data['telemetry'].empty, "Telemetry data is empty."
        assert 'narrative_report' in data, "Narrative report is missing."
        print(" -> Data Input Simulator: PASSED")
    except Exception as e:
        print(f" -> Data Input Simulator: FAILED\n   Reason: {e}")
        return False

    # Check 2: Anomaly Detector
    print("\n[CHECK 2/3] Testing Anomaly Detector...")
    try:
        detector = AnomalyDetector()
        anomalies = detector.detect(data['telemetry'])
        assert isinstance(anomalies, list), "Detector output is not a list."
        # Trong kịch bản flap_jam, phải phát hiện được lỗi
        assert len(anomalies) > 0, "Detector failed to find anomaly in flap_jam scenario."
        print(" -> Anomaly Detector: PASSED")
    except Exception as e:
        print(f" -> Anomaly Detector: FAILED\n   Reason: {e}")
        return False

    # Check 3: HFACS Analyzer (and API connection)
    print("\n[CHECK 3/3] Testing HFACS Analyzer & API Connection...")
    try:
        analyzer = HFACSAnalyzer(PROJECT_ID, LOCATION, CREDENTIALS_PATH)
        if not analyzer.model:
             raise ConnectionError("Gemini-2.5-flash-lite model could not be initialized.")
        level, conf, reason = analyzer.analyze(
            (data['narrative_report'], data['maintenance_logs'])
        )
        assert "Level" in level, "HFACS Analyzer did not return a valid level."
        assert isinstance(conf, int), "Confidence score is not an integer."
        print(" -> HFACS Analyzer & API: PASSED")
    except Exception as e:
        print(f" -> HFACS Analyzer & API: FAILED\n   Reason: {e}")
        return False
        
    print("\n" + "="*50)
    print("=== HEALTH CHECK COMPLETE: ALL SYSTEMS OPERATIONAL ===")
    print("="*50)
    return True


def run_full_demo(scenario: str):
    """
    Chạy một luồng demo hoàn chỉnh từ đầu đến cuối.
    """
    print("\n" + "="*50)
    print("=== RUNNING FULL DEMO ===")
    print("="*50)

    try:
        # Handle "random" scenario selection
        if scenario == "random":
            print("Random mode selected. Picking a scenario...")
            loader = ScenarioLoader() # Create an instance of ScenarioLoader
            available_scenarios = loader.list_scenarios() # Call the new method
            if not available_scenarios:
                print("[ERROR] No scenarios found in the 'scenarios/' directory. Exiting.")
                return
            chosen_scenario = random.choice(available_scenarios) # Pick one randomly
            print(f"Randomly chosen scenario: '{chosen_scenario}'")
            scenario = chosen_scenario # Update scenario for the rest of the logic

        # --- BƯỚC 1: TẠO DỮ LIỆU MÔ PHỎNG ---
        print("\n--- [DEMO STEP 1] Generating simulation data... ---")
        # Initialize HFACSAnalyzer here and pass it to ScenarioSimulator
        hfacs_analyzer_instance = HFACSAnalyzer(PROJECT_ID, LOCATION, CREDENTIALS_PATH)
        if not hfacs_analyzer_instance.model:
            raise ConnectionError("HFACSAnalyzer model could not be initialized for demo.")

        simulator = ScenarioSimulator(scenario_name=scenario, hfacs_analyzer=hfacs_analyzer_instance)
        simulator.run()
        simulation_output = simulator.get_data()
        print("--- Simulation data generated successfully. ---")


        # --- BƯỚC 2: KHỞI TẠO VÀ CHẠY RISK ENGINE ---
        print("\n--- [DEMO STEP 2] Initializing and running analysis engine... ---")
        risk_engine = RiskTriageEngine(
            project_id=PROJECT_ID,
            location=LOCATION,
            credentials_path=CREDENTIALS_PATH
        )
        final_report = risk_engine.analyze_flight(simulation_output)

        if final_report:
            print("\n--- FINAL RISK REPORT (from main.py) ---")
            for key, value in final_report.items():
                print(f"  {key.replace('_', ' ').title()}: {value}")
            print("----------------------------------------")

            # --- BƯỚC 3: TẠO BIỂU ĐỒ KẾT HỢP ---
            print("\n--- [DEMO STEP 3] Generating combined telemetry and risk report chart... ---")
            plot_telemetry_and_report(
                telemetry_data=simulation_output['telemetry'],
                report=final_report,
                output_dir=os.path.join(_PROJECT_ROOT, "project_outputs", "analysis_charts"),
                scenario_name=scenario
            )
            print("--- Combined chart generated successfully. ---")
        else:
            print("\n--- No anomalies detected, skipping report and chart generation. ---")

    except Exception as e:
        print(f"\n[FATAL ERROR] The demo failed to run: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Central Control Panel for the Aviation Safety Analysis System.",
        formatter_class=argparse.RawTextHelpFormatter # Để hiển thị help text đẹp hơn
    )
    
    parser.add_argument(
        'mode',
        type=str,
        choices=['check', 'demo'],
        help="""
The mode to run:
'check' - Perform a health check of all system modules.
'demo'  - Run a full end-to-end simulation and analysis demo."""
    )
    
    parser.add_argument(
        '--scenario',
        type=str,
        default='random',
        help="For 'demo' mode: the name of the scenario to run, or 'random' (default)."
    )
    
    args = parser.parse_args()

    if args.mode == 'check':
        health_check()
    elif args.mode == 'demo':
        run_full_demo(scenario=args.scenario)
