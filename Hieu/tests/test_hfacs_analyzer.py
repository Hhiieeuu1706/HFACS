import os
import sys # Import sys
import textwrap # Added for text wrapping
print(f"DEBUG: Loading test_hfacs_analyzer.py from: {os.path.abspath(__file__)}")

# Define the project root (assuming this script is in the project root)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Add project's src directory to Python path for imports
if os.path.join(PROJECT_ROOT, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
print(f"DEBUG: sys.path after modification: {sys.path}") # Add this line

import json
from src.data_analysis.analysis_modules.hfacs_analyzer import HFACSAnalyzer
from src.data_analysis.analysis_modules.risk_engine import RiskTriageEngine # Import RiskTriageEngine
from typing import Dict, Any
import pandas as pd
SIMULATION_RUNS_DIR = os.path.join(PROJECT_ROOT, "project_outputs", "simulation_runs")
SCENARIOS_DIR = os.path.join(PROJECT_ROOT, "config", "scenarios", "scenarios")

# --- API Configuration ---
PROJECT_ID = "aviation-classifier-sa"
LOCATION = "us-central1"
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, "config", "secrets", "gcloud_credentials.json")
# ---------------------------------------------------------------------------------

def get_scenario_names(scenarios_dir: str) -> list[str]:
    """Gets a list of scenario names from the scenarios directory."""
    scenario_files = [f for f in os.listdir(scenarios_dir) if f.endswith(".json") and f != "desktop.ini" and f != "__init__.py"]
    return sorted([os.path.splitext(f)[0] for f in scenario_files])

def run_test_for_scenario(risk_engine: RiskTriageEngine, scenario_name: str) -> Dict[str, Any]:
    """
    Runs HFACS analysis for a single scenario and compares with ground truth.
    Returns a dictionary containing the detailed results and a match percentage.
    """
    scenario_dir = os.path.join(SIMULATION_RUNS_DIR, scenario_name)
    narrative_path = os.path.join(scenario_dir, "narrative_report.json")
    maintenance_path = os.path.join(scenario_dir, "maintenance_logs.json")
    ground_truth_path = os.path.join(scenario_dir, "ground_truth.json")

    result: Dict[str, Any] = {"scenario_name": scenario_name}

    context_path = os.path.join(scenario_dir, "context_data.json")

    if not (os.path.exists(narrative_path) and os.path.exists(maintenance_path) and os.path.exists(ground_truth_path) and os.path.exists(context_path)):
        result["status"] = "SKIPPED"
        result["message"] = "Missing narrative, maintenance, ground truth, or context data file."
        result["match_percentage"] = 0.0
        print(f"DEBUG (test_hfacs_analyzer): SKIPPING scenario {scenario_name} due to missing files.")
        return result

    print(f"DEBUG (test_hfacs_analyzer): All files exist for scenario {scenario_name}. Proceeding to load data.")
    try:
        with open(narrative_path, 'r', encoding='utf-8') as f:
            narrative_data = json.load(f)
        with open(maintenance_path, 'r', encoding='utf-8') as f:
            maintenance_data = json.load(f)
        with open(context_path, 'r', encoding='utf-8') as f:
            context_data = json.load(f)
        with open(ground_truth_path, 'r', encoding='utf-8') as f:
            ground_truth = json.load(f)

        print(f"DEBUG (test_hfacs_analyzer): Type of narrative_data: {type(narrative_data)}")
        print(f"DEBUG (test_hfacs_analyzer): Narrative data keys: {narrative_data.keys() if isinstance(narrative_data, dict) else 'Not a dict'}")
        print(f"DEBUG (test_hfacs_analyzer): Type of maintenance_data: {type(maintenance_data)}")
        print(f"DEBUG (test_hfacs_analyzer): Maintenance data length: {len(maintenance_data) if isinstance(maintenance_data, list) else 'Not a list'}")
        print(f"DEBUG (test_hfacs_analyzer): Type of context_data: {type(context_data)}")
        print(f"DEBUG (test_hfacs_analyzer): Context data keys: {context_data.keys() if isinstance(context_data, dict) else 'Not a dict'}")

        # Load telemetry data
        telemetry_path = os.path.join(scenario_dir, "telemetry.csv")
        telemetry_data = pd.read_csv(telemetry_path)

        # Prepare simulation_data for RiskTriageEngine
        simulation_data = {
            "scenario_name": scenario_name,
            "narrative_report": narrative_data,
            "maintenance_logs": maintenance_data,
            "context_data": context_data,
            "telemetry": telemetry_data # Pass the loaded DataFrame
        }

        # Perform analysis using RiskTriageEngine
        analysis_report, level_scores_from_engine = risk_engine.analyze_flight(simulation_data)
        
        # Extract results from the analysis_report
        hfacs_level = analysis_report.get("hfacs_level", analysis_report.get("hfacs_root_cause"))
        confidence_str = analysis_report.get("confidence", "0%")
        confidence_score = float(confidence_str.replace("%", ""))
        
        # The new analyze_flight returns final_tags as a string, need to convert back to list for comparison
        # The key is 'reasoning', not 'supporting_evidence'
        reasoning_str = analysis_report.get("reasoning", "NONE")
        hfacs_level_from_report = analysis_report.get("hfacs_level", analysis_report.get("hfacs_root_cause")) # Get the actual level from the report

        if hfacs_level_from_report == "No Fault":
            all_level_evidence_tags = {"Final": []} # No tags if no fault
        else:
            all_level_evidence_tags = {"Final": [tag.strip() for tag in reasoning_str.split(',') if tag.strip() and tag.strip() != "NONE"]}
        # Use the level_scores returned by the engine
        all_level_scores = level_scores_from_engine

        # Extract expected values from ground truth
        expected_level = ground_truth.get("hfacs_analysis", {}).get("winning_level")
        expected_tags = sorted(ground_truth.get("hfacs_analysis", {}).get("evidence_tags", []))

        # Special handling for normal_flight scenario's expected_tags
        if scenario_name == "normal_flight" and "No anomalies detected" in expected_tags:
            expected_tags = []
        
        # Prepare detected tags for comparison
        detected_tags_combined = sorted(list(set(tag for tags in all_level_evidence_tags.values() for tag in tags)))

        # Store results
        result.update({
            "winning_level_got": hfacs_level,
            "winning_level_expected": expected_level,
            "tags_got": detected_tags_combined,
            "tags_expected": expected_tags,
            "scores_per_level": all_level_scores, # This will now contain actual scores
            "tags_per_level": all_level_evidence_tags,
        })

        # Calculate match percentage
        match_percentage = 0.0

        # 1. Winning Level Match (50% of score)
        if hfacs_level == expected_level:
            match_percentage += 50.0

        # 2. Evidence Tags Match (50% of score)
        # Calculate F1-score for tags
        true_positives = len(set(detected_tags_combined) & set(expected_tags))
        false_positives = len(set(detected_tags_combined) - set(expected_tags))
        false_negatives = len(set(expected_tags) - set(detected_tags_combined))

        # Handle case where both detected and expected tags are empty (perfect match)
        if not detected_tags_combined and not expected_tags:
            f1_score = 1.0
        else:
            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
            f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        match_percentage += (f1_score * 50.0) # Scale F1-score to contribute up to 50%

        result["match_percentage"] = round(match_percentage, 2)
        result["status"] = "COMPLETED" # Indicate that analysis was completed

    except Exception as e:
        result["status"] = "ERROR"
        result["message"] = f"An error occurred: {e}"
        result["match_percentage"] = 0.0
    
    return result

def print_results_table(result: Dict[str, Any]):
    """Prints the analysis result for a scenario in a formatted table."""
    scenario_name = result["scenario_name"]
    status = result["status"]
    match_percentage = result.get("match_percentage", 0.0)
    
    total_width = 45 + 9 + 62 + 4 # Adjusted for longer level names
    print("-" * total_width)
    print(f"Scenario: {scenario_name}")
    print(f"Match: {match_percentage:.2f}%") # Display percentage here
    
    if status == "ERROR" or status == "SKIPPED":
        print(f"Status: {status}") # Keep status for error/skipped
        print(f"Message: {result.get('message', 'No details.')}")
        print("-" * total_width)
        return

    # Overall Comparison
    print("-" * total_width)
    print("Overall Comparison:")
    print(f"  - Winning Level:")
    print(f"    - Got:      {result.get('winning_level_got', 'N/A')}")
    print(f"    - Expected: {result.get('winning_level_expected', 'N/A')}")
    print(f"  - Evidence Tags (Combined):")
    
    # Use textwrap for better formatting of long tag strings
    tag_indent = " " * 12 # Indentation for the tags
    wrapped_got_tags = textwrap.fill(
        f"{result.get('tags_got', [])}",
        width=70, # Adjust width as needed
        initial_indent=tag_indent,
        subsequent_indent=tag_indent
    )
    print(f"    - Got: {wrapped_got_tags.lstrip()}") # lstrip to remove initial indent if it's already there

    wrapped_expected_tags = textwrap.fill(
        f"{result.get('tags_expected', [])}",
        width=70, # Adjust width as needed
        initial_indent=tag_indent,
        subsequent_indent=tag_indent
    )
    print(f"    - Expected: {wrapped_expected_tags.lstrip()}") # lstrip to remove initial indent if it's already there
    print("-" * total_width)


def main():
    """Main function to run the interactive test suite."""
    print("--- Initializing HFACS Analyzer Test Suite ---")
    try:
        risk_engine = RiskTriageEngine(
            project_id=PROJECT_ID,
            location=LOCATION,
            credentials_path=CREDENTIALS_PATH
        )
        print("Risk Triage Engine initialized successfully.")
    except Exception as e:
        print(f"Fatal Error: Could not initialize Risk Triage Engine: {e}")
        print("Please check your configuration and credentials. Exiting.")
        return

    scenario_names = get_scenario_names(SCENARIOS_DIR)

    while True:
        # Clear console and display menu
        os.system('cls' if os.name == 'nt' else 'clear')
        print("========== HFACS Analyzer Interactive Test Suite ==========")
        print("Available Scenarios:")
        for i, name in enumerate(scenario_names):
            print(f"  {i+1}. {name}")
        print("\n---------------------------------------------------------")
        print("  A. Test All Scenarios")
        print("  Q. Quit")
        print("=========================================================")

        choice = input("Enter your choice (number, A, or Q): ").strip().lower()

        if choice == 'q':
            print("Exiting test suite. Goodbye!")
            break

        elif choice == 'a':
            print("\n--- Testing All Scenarios ---")
            results = []
            for name in scenario_names:
                print(f"\nRunning test for: {name}")
                result = run_test_for_scenario(risk_engine, name)
                print_results_table(result)
                results.append(result)
            
            # Create output directory if it doesn't exist
            output_dir = os.path.join(PROJECT_ROOT, "outputs", "project_outputs", "test")
            os.makedirs(output_dir, exist_ok=True)

            print("DEBUG: Attempting to save results.json...")
            # Save results to JSON file
            json_output_path = os.path.join(output_dir, "results.json")
            try:
                with open(json_output_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=4)
                print(f"\nDetailed results for all scenarios saved to: {json_output_path}")
            except Exception as e:
                print(f"\n[ERROR] Failed to save results to {json_output_path}: {e}")
            print("DEBUG: Finished attempting to save results.json.")


            print("\n\n--- TEST SUITE SUMMARY ---")
            total_scenarios = len(results)
            completed_scenarios = sum(1 for r in results if r['status'] == 'COMPLETED')
            failed_scenarios = sum(1 for r in results if r['status'] == 'ERROR')
            skipped_scenarios = sum(1 for r in results if r['status'] == 'SKIPPED')
            total_match_percentage = sum(r.get("match_percentage", 0.0) for r in results if r['status'] == 'COMPLETED')
            
            average_match = total_match_percentage / completed_scenarios if completed_scenarios > 0 else 0.0

            print(f"Total Scenarios: {total_scenarios}")
            print(f"  - Completed: {completed_scenarios}")
            print(f"  - Failed:    {failed_scenarios}")
            print(f"  - Skipped:   {skipped_scenarios}")
            print(f"Average Match for Completed Scenarios: {average_match:.2f}%")
            print("--------------------------")

        else:
            try:
                scenario_index = int(choice) - 1
                if 0 <= scenario_index < len(scenario_names):
                    scenario_name = scenario_names[scenario_index]
                    print(f"\n--- Testing Scenario: {scenario_name} ---")
                    result = run_test_for_scenario(risk_engine, scenario_name)
                    print_results_table(result)
                else:
                    print("Error: Invalid scenario number.")
            except ValueError:
                print("Error: Invalid input. Please enter a number, 'A', or 'Q'.")

        # Prompt to continue
        print("")
        continue_choice = input("Do you want to run another test? (Y/N): ").strip().lower()
        if continue_choice != 'y':
            print("Exiting test suite. Goodbye!")
            break

if __name__ == '__main__':
    main()