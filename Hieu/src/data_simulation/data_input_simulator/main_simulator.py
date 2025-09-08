# file: data_input_simulator/main_simulator.py (v1.3 - Simplified, relies on PYTHONPATH)

import os
import argparse
import json
import random
import sys # Added import sys

print("DEBUG: main_simulator.py started.") # Added this line to check execution

# *** ĐÃ XÓA: Toàn bộ logic sys.path đã được gỡ bỏ. ***
# Script này giờ đây phụ thuộc vào việc PYTHONPATH được thiết lập đúng bởi file batch.

from src.data_simulation.data_input_simulator.scenario_loader import ScenarioLoader
from src.data_simulation.data_input_simulator.telemetry_generator import TelemetryGenerator, plot_scenario_telemetry
from src.data_simulation.data_input_simulator.document_generator import DocumentGenerator
from src.data_simulation.data_input_simulator.ground_truth_generator import GroundTruthGenerator
from src.data_analysis.analysis_modules.hfacs_analyzer import HFACSAnalyzer, HFACS_RUBRIC # New import

# Add project root to sys.path for module imports
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Câu lệnh import chuẩn, sẽ hoạt động khi PYTHONPATH được thiết lập đúng.

class ScenarioSimulator:
    """
    Module "nhạc trưởng" điều phối toàn bộ quá trình mô phỏng.
    """
    def __init__(self, scenario_name: str, hfacs_analyzer: HFACSAnalyzer):
        self.scenario_name = scenario_name
        self.config = None
        self.simulation_data = {}
        self.loader = ScenarioLoader()
        self.hfacs_analyzer = hfacs_analyzer

    def run(self):
        print(f"--- [START] Running simulation for scenario: '{self.scenario_name}' ---")
        self.config = self.loader.load(self.scenario_name)
        telemetry_gen = TelemetryGenerator(self.config)
        doc_gen = DocumentGenerator(self.config)
        truth_gen = GroundTruthGenerator(self.config)
        print("\n[1/4] Generating Telemetry Data...")
        telemetry_data = telemetry_gen.generate()
        print("\n[2/4] Generating Document Data...")
        document_data = doc_gen.generate_all_documents()

        # Perform HFACS classification on the narrative report
        narrative_report_text = document_data["narrative_report"]
        print("\n[2.5/4] Classifying Narrative Report with HFACS...")
        combined_text = f"""Narrative Report:
{document_data['narrative_report']}

Maintenance Logs:
{document_data['maintenance_logs']}

Context Data:
{document_data['context_data']}"""

        hfacs_level, hfacs_confidence, level_scores, level_evidence_tags = self.hfacs_analyzer.analyze(
            {
                "combined_text": combined_text,
                "ALL_EVIDENCE_TAGS": ", ".join(HFACS_RUBRIC.keys())
            }
        )
        score_breakdown_parts = []
        level_names = ["Unsafe Acts", "Preconditions for Unsafe Acts", "Unsafe Supervision", "Organizational Influences"]
        for i, name in enumerate(level_names):
            level_key = f"Level {i+1}: {name}"
            score = level_scores.get(level_key, 0)
            score_breakdown_parts.append(f"L{i+1}({score})")

        score_breakdown = "/".join(score_breakdown_parts)
        hfacs_reasoning = f"{score_breakdown} | Evidence: {level_evidence_tags.get(hfacs_level, [])}"

        print(f"  -> Classified as: {hfacs_level} (Confidence: {hfacs_confidence}%)")
        print(f"  -> Reasoning: {hfacs_reasoning}")

        print("\n[3/4] Generating Ground Truth Data...")
        ground_truth_data = truth_gen.generate()
        self.simulation_data = {
            "telemetry": telemetry_data,
            "maintenance_logs": document_data["maintenance_logs"],
            "narrative_report": document_data["narrative_report"],
            "context_data": document_data["context_data"],
            "ground_truth": ground_truth_data,
            "scenario_name": self.scenario_name,
            "hfacs_level": hfacs_level,
            "hfacs_confidence": hfacs_confidence,
            "hfacs_reasoning": hfacs_reasoning
        }
        print("\n[4/4] Assembling final data package...")
        print("--- [COMPLETE] Simulation finished successfully. ---")
    
    def get_data(self) -> dict:
        return self.simulation_data

    def save_outputs(self, output_dir: str):
        print(f"DEBUG: Entering save_outputs. output_dir: '{output_dir}'")
        if not self.simulation_data:
            print("Error: No simulation data to save. Please run the simulation first.")
            return
        print(f"\n--- Saving simulation outputs to '{output_dir}' ---")
        os.makedirs(output_dir, exist_ok=True)
        telemetry_path = os.path.join(output_dir, 'telemetry.csv')
        try:
            self.simulation_data['telemetry'].to_csv(telemetry_path, index=False)
        except Exception as e:
            print(f"ERROR: Failed to save telemetry to {telemetry_path}: {e}")

        for key, data in self.simulation_data.items():
            if key != 'telemetry':
                file_path = os.path.join(output_dir, f'{key}.json')
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4)
                except Exception as e:
                    print(f"ERROR: Failed to save {key} to {file_path}: {e}")
        
        print(f"--- All simulation outputs saved to '{output_dir}' ---")

def main():
    # ... (Nội dung hàm main giữ nguyên) ...
    print("DEBUG: main() function started.") # Added this line
    parser = argparse.ArgumentParser(description="Data Input Simulator for Aviation Safety Scenarios.")
    parser.add_argument('--scenario', type=str, required=True, help='Name of the scenario to run (e.g., "flap_jam") or "random" to pick one automatically.')
    parser.add_argument('--output', type=str, default=None, help='(Optional) Directory path to save the output files.')
    parser.add_argument('--project_id', type=str, required=True, help='GCP Project ID for Vertex AI.')
    parser.add_argument('--location', type=str, default='us-central1', help='GCP Location for Vertex AI.')
    parser.add_argument('--credentials', type=str, required=True, help='Path to GCP credentials JSON file.')
    parser.add_argument('--prompt_path', type=str, required=True, help='Path to the prompt file for HFACS analysis.')
    args = parser.parse_args()
    print(f"DEBUG: args.output received: '{args.output}'") # Added this line

    # Handle "random" scenario selection
    if args.scenario == "random":
        print("Random mode selected. Picking a scenario...")
        loader = ScenarioLoader() # Create an instance of ScenarioLoader
        available_scenarios = loader.list_scenarios() # Call the new method
        if not available_scenarios:
            print("[ERROR] No scenarios found in the 'scenarios/' directory. Exiting.")
            return
        chosen_scenario = random.choice(available_scenarios) # Pick one randomly
        print(f"Randomly chosen scenario: '{chosen_scenario}'")
        args.scenario = chosen_scenario # Update args.scenario for the rest of the logic

    try:
        hfacs_analyzer = HFACSAnalyzer(
            project_id=args.project_id,
            location=args.location,
            credentials_path=args.credentials,
                prompt_path=args.prompt_path, # Use the path from the command-line argument
                project_root=_PROJECT_ROOT # Pass project root
        )
        if not hfacs_analyzer.model:
            print("[ERROR] HFACSAnalyzer could not be initialized. Exiting.")
            return

        simulator = ScenarioSimulator(scenario_name=args.scenario, hfacs_analyzer=hfacs_analyzer)
        simulator.run()

        # Get the simulation data after running
        simulation_results = simulator.get_data()

        # Call plot_scenario_telemetry to generate the chart
        plot_scenario_telemetry(
            telemetry_data=simulation_results["telemetry"],
            scenario_name=simulation_results["scenario_name"],
            scenario_config=simulator.config, # simulator.config holds the scenario config
            output_dir=_PROJECT_ROOT, # Pass the main project root
            hfacs_level=simulation_results["hfacs_level"],
            hfacs_confidence=simulation_results["hfacs_confidence"],
            hfacs_reasoning=simulation_results["hfacs_reasoning"]
        )

        if args.output:
            print(f"DEBUG: Attempting to save outputs to {args.output} and generate plots.")
            simulator.save_outputs(output_dir=args.output)
    except FileNotFoundError as e:
        print(f"\n[ERROR] Could not find scenario file: {e}")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging

if __name__ == '__main__':
    main()


# Add project root to sys.path for module imports
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Câu lệnh import chuẩn, sẽ hoạt động khi PYTHONPATH được thiết lập đúng.

class ScenarioSimulator:
    """
    Module "nhạc trưởng" điều phối toàn bộ quá trình mô phỏng.
    """
    def __init__(self, scenario_name: str, hfacs_analyzer: HFACSAnalyzer):
        self.scenario_name = scenario_name
        self.config = None
        self.simulation_data = {}
        self.loader = ScenarioLoader()
        self.hfacs_analyzer = hfacs_analyzer

    def run(self):
        print(f"--- [START] Running simulation for scenario: '{self.scenario_name}' ---")
        self.config = self.loader.load(self.scenario_name)
        telemetry_gen = TelemetryGenerator(self.config)
        doc_gen = DocumentGenerator(self.config)
        truth_gen = GroundTruthGenerator(self.config)
        print("\n[1/4] Generating Telemetry Data...")
        telemetry_data = telemetry_gen.generate()
        print("\n[2/4] Generating Document Data...")
        document_data = doc_gen.generate_all_documents()

        # Perform HFACS classification on the narrative report
        narrative_report_text = document_data["narrative_report"]
        print("\n[2.5/4] Classifying Narrative Report with HFACS...")
        combined_text = f"""Narrative Report:
{document_data['narrative_report']}

Maintenance Logs:
{document_data['maintenance_logs']}

Context Data:
{document_data['context_data']}"""

        hfacs_level, hfacs_confidence, level_scores, level_evidence_tags = self.hfacs_analyzer.analyze(
            {
                "combined_text": combined_text,
                "ALL_EVIDENCE_TAGS": ", ".join(HFACS_RUBRIC.keys())
            }
        )
        score_breakdown_parts = []
        level_names = ["Unsafe Acts", "Preconditions for Unsafe Acts", "Unsafe Supervision", "Organizational Influences"]
        for i, name in enumerate(level_names):
            level_key = f"Level {i+1}: {name}"
            score = level_scores.get(level_key, 0)
            score_breakdown_parts.append(f"L{i+1}({score})")

        score_breakdown = "/".join(score_breakdown_parts)
        hfacs_reasoning = f"{score_breakdown} | Evidence: {level_evidence_tags.get(hfacs_level, [])}"

        print(f"  -> Classified as: {hfacs_level} (Confidence: {hfacs_confidence}%)")
        print(f"  -> Reasoning: {hfacs_reasoning}")

        print("\n[3/4] Generating Ground Truth Data...")
        ground_truth_data = truth_gen.generate()
        self.simulation_data = {
            "telemetry": telemetry_data,
            "maintenance_logs": document_data["maintenance_logs"],
            "narrative_report": document_data["narrative_report"],
            "context_data": document_data["context_data"],
            "ground_truth": ground_truth_data,
            "scenario_name": self.scenario_name,
            "hfacs_level": hfacs_level,
            "hfacs_confidence": hfacs_confidence,
            "hfacs_reasoning": hfacs_reasoning
        }
        print("\n[4/4] Assembling final data package...")
        print("--- [COMPLETE] Simulation finished successfully. ---")
    
    def get_data(self) -> dict:
        return self.simulation_data

    def save_outputs(self, output_dir: str):
        print(f"DEBUG: Entering save_outputs. output_dir: '{output_dir}'")
        if not self.simulation_data:
            print("Error: No simulation data to save. Please run the simulation first.")
            return
        print(f"\n--- Saving simulation outputs to '{output_dir}' ---")
        os.makedirs(output_dir, exist_ok=True)
        telemetry_path = os.path.join(output_dir, 'telemetry.csv')
        try:
            self.simulation_data['telemetry'].to_csv(telemetry_path, index=False)
        except Exception as e:
            print(f"ERROR: Failed to save telemetry to {telemetry_path}: {e}")

        for key, data in self.simulation_data.items():
            if key != 'telemetry':
                file_path = os.path.join(output_dir, f'{key}.json')
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4)
                except Exception as e:
                    print(f"ERROR: Failed to save {key} to {file_path}: {e}")
        
        print(f"--- All simulation outputs saved to '{output_dir}' ---")

def main():
    # ... (Nội dung hàm main giữ nguyên) ...
    print("DEBUG: main() function started.") # Added this line
    parser = argparse.ArgumentParser(description="Data Input Simulator for Aviation Safety Scenarios.")
    parser.add_argument('--scenario', type=str, required=True, help='Name of the scenario to run (e.g., "flap_jam") or "random" to pick one automatically.')
    parser.add_argument('--output', type=str, default=None, help='(Optional) Directory path to save the output files.')
    parser.add_argument('--project_id', type=str, required=True, help='GCP Project ID for Vertex AI.')
    parser.add_argument('--location', type=str, default='us-central1', help='GCP Location for Vertex AI.')
    parser.add_argument('--credentials', type=str, required=True, help='Path to GCP credentials JSON file.')
    parser.add_argument('--prompt_path', type=str, required=True, help='Path to the prompt file for HFACS analysis.')
    args = parser.parse_args()
    print(f"DEBUG: args.output received: '{args.output}'") # Added this line

    # Handle "random" scenario selection
    if args.scenario == "random":
        print("Random mode selected. Picking a scenario...")
        loader = ScenarioLoader() # Create an instance of ScenarioLoader
        available_scenarios = loader.list_scenarios() # Call the new method
        if not available_scenarios:
            print("[ERROR] No scenarios found in the 'scenarios/' directory. Exiting.")
            return
        chosen_scenario = random.choice(available_scenarios) # Pick one randomly
        print(f"Randomly chosen scenario: '{chosen_scenario}'")
        args.scenario = chosen_scenario # Update args.scenario for the rest of the logic

    try:
        hfacs_analyzer = HFACSAnalyzer(
            project_id=args.project_id,
            location=args.location,
            credentials_path=args.credentials,
                prompt_path=args.prompt_path, # Use the path from the command-line argument
                project_root=_PROJECT_ROOT # Pass project root
        )
        if not hfacs_analyzer.model:
            print("[ERROR] HFACSAnalyzer could not be initialized. Exiting.")
            return

        simulator = ScenarioSimulator(scenario_name=args.scenario, hfacs_analyzer=hfacs_analyzer)
        simulator.run()

        # Get the simulation data after running
        simulation_results = simulator.get_data()

        # Call plot_scenario_telemetry to generate the chart
        plot_scenario_telemetry(
            telemetry_data=simulation_results["telemetry"],
            scenario_name=simulation_results["scenario_name"],
            scenario_config=simulator.config, # simulator.config holds the scenario config
            output_dir=_PROJECT_ROOT, # Pass the main project root
            hfacs_level=simulation_results["hfacs_level"],
            hfacs_confidence=simulation_results["hfacs_confidence"],
            hfacs_reasoning=simulation_results["hfacs_reasoning"]
        )

        if args.output:
            print(f"DEBUG: Attempting to save outputs to {args.output} and generate plots.")
            simulator.save_outputs(output_dir=args.output)
    except FileNotFoundError as e:
        print(f"\n[ERROR] Could not find scenario file: {e}")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging

if __name__ == '__main__':
    main()