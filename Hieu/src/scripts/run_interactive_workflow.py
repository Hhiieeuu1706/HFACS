import os
import sys
import subprocess
import time
import json # Added for saving JSON output
import pandas as pd # Added for reading telemetry data

# --- Pre-computation and Imports ---
# Add project root to Python path to ensure modules are found
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.test_hfacs_analyzer import (
    get_scenario_names,
    run_test_for_scenario,
    print_results_table,
    RiskTriageEngine
)
from src.data_simulation.data_input_simulator.telemetry_generator import plot_scenario_telemetry
from src.data_simulation.data_input_simulator.scenario_loader import ScenarioLoader # Needed to load scenario config for plotting

# --- Configuration ---
SCENARIOS_DIR = os.path.join(PROJECT_ROOT, "config", "scenarios", "scenarios")
PROMPT_PATH = os.path.join(PROJECT_ROOT, "config", "prompts", "prompts", "hfacs_analyzer_prompt.txt")
TEST_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "project_outputs", "test") # Added for saving analysis results

# Match the API and credentials config from the test script
PROJECT_ID = "aviation-classifier-sa"
LOCATION = "us-central1"
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, "config", "secrets", "gcloud_credentials.json")
# -----------------------------------------------------------------------

def run_simulation(scenario_name: str) -> bool:
    """
    Runs the data input simulator for a single scenario using a subprocess.
    Returns True on success, False on failure.
    """
    print(f"\n--- Running Simulation for: {scenario_name} ---")
    output_dir = os.path.join(PROJECT_ROOT, "project_outputs", "simulation_runs", scenario_name)
    
    # Construct the command to run the simulator module
    command = [
        sys.executable,  # Use the current python interpreter
        "-m", "src.data_simulation.data_input_simulator.main_simulator",
        "--scenario", scenario_name,
        "--output", output_dir,
        "--project_id", PROJECT_ID,
        "--location", LOCATION,
        "--credentials", CREDENTIALS_PATH,
        "--prompt_path", PROMPT_PATH
    ]
    
    try:
        # We use subprocess.run which waits for the command to complete.
        # Setting cwd ensures that relative paths inside the simulator work as expected.
        result = subprocess.run(
            command, 
            check=True, 
            capture_output=True, 
            text=True, 
            cwd=PROJECT_ROOT,
            encoding='utf-8' # Explicitly set encoding
        )
        print(f"Simulation for '{scenario_name}' completed successfully.")
        print(result.stdout) # Uncommented for detailed simulation output
        return True
    except subprocess.CalledProcessError as e:
        print(f"--- ERROR: Simulation failed for scenario '{scenario_name}'. ---")
        print(f"Return Code: {e.returncode}")
        # Print stderr to see the actual Python error
        print(f"Error Output:\n{e.stderr}")
        print("-----------------------------------------------------------------")
        return False
    except FileNotFoundError:
        print("--- ERROR: 'python' command not found. ---")
        print("Please ensure Python is installed and in your system's PATH.")
        return False


def wait_for_simulation_files(scenario_name: str, timeout: int = 30) -> bool:
    """
    Waits for all necessary simulation output files to exist.

    Args:
        scenario_name (str): The name of the scenario.
        timeout (int): Maximum time to wait in seconds.

    Returns:
        bool: True if all files are found, False if timeout is reached.
    """
    print(f"--- Waiting for simulation output files for '{scenario_name}'... ---")
    start_time = time.time()
    scenario_dir = os.path.join(PROJECT_ROOT, "project_outputs", "simulation_runs", scenario_name)
    
    required_files = [
        "narrative_report.json",
        "maintenance_logs.json",
        "ground_truth.json",
        "context_data.json",
        "telemetry.csv"
    ]
    
    while time.time() - start_time < timeout:
        all_files_exist = True
        for filename in required_files:
            if not os.path.exists(os.path.join(scenario_dir, filename)):
                all_files_exist = False
                break
        
        if all_files_exist:
            print("--- All simulation files found. Proceeding with analysis. ---")
            return True
            
        time.sleep(1) # Wait 1 second before checking again

    print(f"--- ERROR: Timed out after {timeout} seconds waiting for simulation files. ---")
    return False

def run_full_workflow_for_scenario(scenario_name: str, risk_engine: RiskTriageEngine):
    """Runs the complete workflow (simulation + analysis) for one scenario."""
    # Step 1: Run the simulation
    simulation_success = run_simulation(scenario_name)
    
    # Step 2: If simulation is successful, wait for files and run the analysis
    if simulation_success:
        # Wait for the output files to be created with a timeout
        files_are_ready = wait_for_simulation_files(scenario_name)
        
        if files_are_ready:
            print(f"--- Running Analysis for: {scenario_name} ---")
            analysis_result = run_test_for_scenario(risk_engine, scenario_name)
            print_results_table(analysis_result)
        else:
            # If files are not ready after timeout, create a failure result
            analysis_result = {
                "scenario_name": scenario_name,
                "status": "ERROR",
                "message": "Analysis skipped because simulation output files were not found after timeout.",
                "match_percentage": 0.0
            }
            print_results_table(analysis_result)

        # Save analysis result to JSON file in project_outputs/test
        os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)
        output_file_path = os.path.join(TEST_OUTPUT_DIR, f"analysis_result_{scenario_name}.json")
        try:
            with open(output_file_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, indent=4)
            print(f"Analysis result saved to: {output_file_path}")
        except Exception as e:
            print(f"ERROR: Could not save analysis result to {output_file_path}: {e}")
        
        # --- Plotting with final analysis results ---
        print(f"--- Generating plot for: {scenario_name} ---")
        try:
            # Load telemetry data
            simulation_output_dir = os.path.join(PROJECT_ROOT, "project_outputs", "simulation_runs", scenario_name)
            telemetry_path = os.path.join(simulation_output_dir, 'telemetry.csv')
            telemetry_data = pd.read_csv(telemetry_path)

            # Load scenario config
            loader = ScenarioLoader()
            scenario_config = loader.load(scenario_name)

            # Extract final HFACS results from analysis_result
            final_hfacs_level = analysis_result.get('winning_level_got', 'N/A')
            final_hfacs_confidence = int(analysis_result.get('match_percentage', 0.0))

            scores_per_level = analysis_result.get('scores_per_level', {})
            score_breakdown_parts = []
            level_order = [
                "Level 1: Unsafe Acts",
                "Level 2: Preconditions for Unsafe Acts",
                "Level 3: Unsafe Supervision",
                "Level 4: Organizational Influences"
            ]
            for i, level_name_full in enumerate(level_order):
                score = scores_per_level.get(level_name_full, 0)
                level_short = f"L{i+1}"
                score_breakdown_parts.append(f"{level_short}({score})")
            score_breakdown_str = "/".join(score_breakdown_parts)

            tags_got_str = ", ".join(analysis_result.get('tags_got', []))
            final_hfacs_reasoning = f"{score_breakdown_str} | Evidence: {tags_got_str}"

            # Pass the PROJECT_ROOT to the plotting function
            plot_scenario_telemetry(
                telemetry_data,
                scenario_name,
                scenario_config,
                PROJECT_ROOT, # Pass project root
                final_hfacs_level,
                final_hfacs_confidence,
                final_hfacs_reasoning
            )
            print(f"Plot generated for {scenario_name}.")
        except Exception as e:
            print(f"ERROR: Could not generate plot for {scenario_name}: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for debugging
        
        return analysis_result
    else:
        print(f"Skipping analysis for '{scenario_name}' due to simulation failure.")
        return {
            "scenario_name": scenario_name,
            "status": "ERROR",
            "message": "Simulation failed.",
            "match_percentage": 0.0
        }

def run_sync_mode(risk_engine, scenario_names):
    """Runs the workflow in sync mode, waiting for the web dashboard."""
    print("--- Running in Sync Mode: Waiting for Web Dashboard ---")
    sync_file_path = os.path.join(PROJECT_ROOT, 'outputs', 'current_scenario.txt')
    
    # Wait for the sync file to be created by the web app
    timeout = 60  # Wait for 60 seconds max
    start_time = time.time()
    scenario_file_found = False
    while time.time() - start_time < timeout:
        if os.path.exists(sync_file_path):
            print(f"Sync file found at: {sync_file_path}")
            scenario_file_found = True
            break
        time.sleep(1) # Wait 1 second before checking again

    if not scenario_file_found:
        print(f"Error: Timed out waiting for sync file at {sync_file_path}")
        return

    try:
        with open(sync_file_path, 'r') as f:
            scenario_name = f.read().strip()
        print(f"Found scenario '{scenario_name}' from web dashboard.")
        if scenario_name in scenario_names:
            run_full_workflow_for_scenario(scenario_name, risk_engine)
            # Clean up the sync file after processing
            os.remove(sync_file_path)
            print(f"Finished processing and cleaned up sync file.")
        else:
            print(f"Error: Scenario '{scenario_name}' found in sync file, but is not a valid scenario.")
    except Exception as e:
        print(f"An error occurred during sync mode: {e}")

def main():
    """Main function to run the interactive workflow."""
    # --- Argument Parsing for Sync Mode ---
    is_sync_mode = '--sync' in sys.argv

    print("--- Initializing HFACS Interactive Workflow ---")
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

    if is_sync_mode:
        run_sync_mode(risk_engine, scenario_names)
        return # Exit after sync mode is done

    # --- Interactive Menu Loop (if not in sync mode) ---
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("========== HFACS Interactive Workflow ==========")
        print("Choose an option to run both Simulation & Analysis:")
        for i, name in enumerate(scenario_names):
            print(f"  {i+1}. {name}")
        print("\n--------------------------------------------------")
        print("  S. Run Scenario from Web Dashboard (Manual Sync)")
        print("  A. Run All Scenarios")
        print("  Q. Quit")
        print("==================================================")

        choice = input("Enter your choice (number, S, A, or Q): ").strip().lower()

        if choice == 'q':
            print("Exiting workflow. Goodbye!")
            break

        elif choice == 's':
            print("\n--- Running Scenario from Web Dashboard ---")
            sync_file_path = os.path.join(PROJECT_ROOT, 'outputs', 'current_scenario.txt')
            try:
                with open(sync_file_path, 'r') as f:
                    scenario_name = f.read().strip()
                print(f"Found scenario '{scenario_name}' from web dashboard.")
                if scenario_name in scenario_names:
                    run_full_workflow_for_scenario(scenario_name, risk_engine)
                else:
                    print(f"Error: Scenario '{scenario_name}' found in sync file, but is not a valid scenario.")
            except FileNotFoundError:
                print(f"Error: Sync file not found at {sync_file_path}")
                print("Please run the web dashboard first to generate a scenario.")
            except Exception as e:
                print(f"An error occurred: {e}")

        elif choice == 'a':
            print("\n--- Running Full Workflow for All Scenarios ---")
            all_results = []
            for name in scenario_names:
                result = run_full_workflow_for_scenario(name, risk_engine)
                all_results.append(result)
                print(f"--- Finished processing {name} ---")
                time.sleep(5) # Add delay between scenarios to avoid API rate limits

            print("\n\n--- FINAL WORKFLOW SUMMARY ---")
            total = len(all_results)
            completed = sum(1 for r in all_results if r['status'] == 'COMPLETED')
            failed = sum(1 for r in all_results if r['status'] == 'ERROR')
            
            print(f"Total Scenarios Processed: {total}")
            print(f"  - Succeeded: {completed}")
            print(f"  - Failed:    {failed}")
            print("------------------------------")

            # Display detailed results table
            print("\n--- DETAILED SCENARIO RESULTS ---")
            print("| {:<30} | {:<10} | {:<10} | {:<15} | {:<15} |".format("Scenario Name", "Status", "Match %", "Actual Level", "Expected Level"))
            print("|{:-<32}|{:-<12}|{:-<12}|{:-<17}|{:-<17}|".format("", "", "", "", ""))
            for r in all_results:
                scenario_name = r['scenario_name']
                status = r['status']
                match_percentage = f"{r.get('match_percentage', 0.0):.2f}%" if status == 'COMPLETED' else 'N/A'
                actual_level = r.get('winning_level_got', 'N/A') if status == 'COMPLETED' else 'N/A'
                expected_level = r.get('winning_level_expected', 'N/A') if status == 'COMPLETED' else 'N/A'
                print("| {:<30} | {:<10} | {:<10} | {:<15} | {:<15} |".format(scenario_name, status, match_percentage, actual_level, expected_level))
            print("|{:-<32}|{:-<12}|{:-<12}|{:-<17}|{:-<17}|".format("", "", "", "", ""))
            print("----------------------------------------------------------------------------------------------------")

        else:
            try:
                scenario_index = int(choice) - 1
                if 0 <= scenario_index < len(scenario_names):
                    scenario_name = scenario_names[scenario_index]
                    run_full_workflow_for_scenario(scenario_name, risk_engine)
                else:
                    print("Error: Invalid scenario number.")
            except ValueError:
                print("Error: Invalid input. Please enter a number, 'S', 'A', or 'Q'.")

        print("")
        continue_choice = input("Do you want to run another workflow? (Y/N): ").strip().lower()
        if continue_choice != 'y':
            print("Exiting workflow. Goodbye!")
            break



if __name__ == '__main__':
    main()
