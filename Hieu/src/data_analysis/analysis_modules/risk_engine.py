# file: analysis_modules/risk_engine.py (v1.0)
import os
print(f"DEBUG: Loading risk_engine.py from: {os.path.abspath(__file__)}")

import sys
import argparse
from datetime import datetime
import json

# Import các module cần thiết
from data_simulation.data_input_simulator.main_simulator import ScenarioSimulator
from .anomaly_detector import AnomalyDetector
from .hfacs_analyzer import HFACSAnalyzer, ALL_EVIDENCE_TAGS

# --- Logic tự nhận biết đường dẫn để import các module khác ---
# Đảm bảo rằng script này có thể được chạy độc lập
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

class RiskTriageEngine:
    """
    Orchestrates the analysis workflow using a panel of AI experts.
    It coordinates the AnomalyDetector and multiple HFACSAnalyzer instances
    to produce a consolidated risk assessment.
    """
    def __init__(self, project_id: str, location: str, credentials_path: str):
        """
        Initializes the Risk Triage Engine and its sub-analysis modules.
        """
        print("Initializing Risk Triage Engine with HFACS Expert Panel...")
        self.anomaly_detector = AnomalyDetector()

        # Initialize four HFACSAnalyzer instances, each with a distinct role and prompt
        try:
            # Each specialist gets a specific prompt file.
            # The file path is constructed relative to the project root.
            self.general_analyst = HFACSAnalyzer(
                project_id=project_id,
                location=location,
                credentials_path=credentials_path,
                prompt_path="config/prompts/prompts/general_analyst_prompt.txt",
                project_root=_PROJECT_ROOT # Pass project root
            )
            self.tech_ops_specialist = HFACSAnalyzer(
                project_id=project_id,
                location=location,
                credentials_path=credentials_path,
                prompt_path="config/prompts/prompts/tech_ops_specialist_prompt.txt",
                project_root=_PROJECT_ROOT # Pass project root
            )
            self.maint_org_specialist = HFACSAnalyzer(
                project_id=project_id,
                location=location,
                credentials_path=credentials_path,
                prompt_path="config/prompts/prompts/maint_org_specialist_prompt.txt",
                project_root=_PROJECT_ROOT # Pass project root
            )
            self.final_adjudicator = HFACSAnalyzer(
                project_id=project_id,
                location=location,
                credentials_path=credentials_path,
                prompt_path="config/prompts/prompts/adjudicator_prompt.txt",
                project_root=_PROJECT_ROOT # Pass project root
            )
        except Exception as e:
            # Catch potential errors during initialization (e.g., file not found)
            raise ConnectionError(f"Failed to initialize one or more HFACSAnalyzer instances: {e}")

        # Verify that all AI models were initialized correctly.
        if not all([
            self.general_analyst.model,
            self.tech_ops_specialist.model,
            self.maint_org_specialist.model,
            self.final_adjudicator.model
        ]):
            raise ConnectionError("One or more HFACSAnalyzer models failed to initialize. "
                                  "Check API credentials, paths, and permissions.")
        
        print("Risk Triage Engine initialized successfully.")

    def _format_hfacs_input(self, narrative, maint_logs, context):
        """Helper to format the combined text for analysis."""
        narrative_text = ""
        if narrative and 'transcript' in narrative:
            for entry in narrative['transcript']:
                if 'speaker' in entry:
                    narrative_text += f"- {entry['speaker']}: {entry['dialogue']}\n"
                elif 'sound' in entry:
                    narrative_text += f"- (Sound: {entry['sound']})\n"
        
        logs_text = ""
        if maint_logs:
            for log in maint_logs:
                logs_text += f"- {log['entry_date']}: {log['report']} | Action: {log['action']}\n"

        context_text = ""
        if context:
            for key, value in context.items():
                context_text += f"- {key.replace('_', ' ').title()}: {value}\n"
        
        return (
            f"NARRATIVE REPORT (CVR):\n{narrative_text}\n"
            f"MAINTENANCE LOGS:\n{logs_text}\n"
            f"CONTEXT DATA:\n{context_text}"
        )

    def analyze_flight(self, simulation_data: dict):
        """
        Executes the full S-D-E-A analysis chain using the multi-agent panel.
        """
        print("\n" + "="*80)
        print(f"=== STARTING RISK ANALYSIS FOR SCENARIO: {simulation_data['scenario_name']} ===")
        print("="*80)

        # --- SENSE & DETECT ---
        print("\n[PHASE 1: SENSE & DETECT]")
        print("Running Anomaly Detector on telemetry data...")
        detected_anomalies = self.anomaly_detector.detect(simulation_data['telemetry'])

        # --- TRIAGE & EXPLAIN ---
        print("\n[PHASE 2: TRIAGE & EXPLAIN]")
        if not detected_anomalies:
            print("Conclusion: No anomalies detected. Flight profile appears normal.")
            report = {
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "scenario": simulation_data['scenario_name'],
                "what_happened": "No anomalies detected.",
                "hfacs_root_cause": "No Fault",
                "confidence": "100%",
                "reasoning": "",
                "intermediate_findings": {}
            }
            level_scores = {"Level 1: Unsafe Acts": 0, "Level 2: Preconditions for Unsafe Acts": 0, "Level 3: Unsafe Supervision": 0, "Level 4: Organizational Influences": 0}
            print("\n--- FINAL RISK REPORT ---")
            print(f"Scenario: {report['scenario']}")
            print(f"What Happened: {report['what_happened']}")
            print(f"HFACS Root Cause: {report['hfacs_root_cause']}")
            print(f"Confidence: {report['confidence']}")
            print("--- END OF REPORT ---")
            print("="*80)
            return report, level_scores

        print("ALERT! Anomaly detected. Triggering deep analysis with AI Expert Panel...")

        # Step A: Prepare Combined Reports (original_evidence)
        narrative_report = simulation_data.get('narrative_report', {})
        maintenance_logs = simulation_data.get('maintenance_logs', [])
        
        original_evidence_string = "NARRATIVE REPORT (CVR):\n"
        if narrative_report and 'transcript' in narrative_report:
            for entry in narrative_report['transcript']:
                if 'speaker' in entry:
                    original_evidence_string += f"- {entry['speaker']}: {entry['dialogue']}\n"
                elif 'sound' in entry:
                    original_evidence_string += f"- (Sound: {entry['sound']})\n"
        
        original_evidence_string += "\nMAINTENANCE LOGS:\n"
        if maintenance_logs:
            for log in maintenance_logs:
                original_evidence_string += f"- {log['entry_date']}: {log['report']} | Action: {log['action']}\n"

        # The input for the specialists includes all context
        combined_reports_input = self._format_hfacs_input(
            narrative_report,
            maintenance_logs,
            simulation_data.get('context_data', {})
        )
        
        # Step B: Run Specialized Analysts
        print("\n[Step B: Running Specialized Analysts...]")
        
        # Prepare common context for specialists
        common_specialist_context = {
            'combined_text': combined_reports_input,
            'ALL_EVIDENCE_TAGS': ', '.join(ALL_EVIDENCE_TAGS) # Provide all possible tags
        }

        _, _, _, general_tags_dict = self.general_analyst.analyze(common_specialist_context)
        general_tags = [tag for tags in general_tags_dict.values() for tag in tags]
        print(f" -> General Analyst found: {general_tags}")

        _, _, _, tech_ops_tags_dict = self.tech_ops_specialist.analyze(common_specialist_context)
        tech_ops_tags = [tag for tags in tech_ops_tags_dict.values() for tag in tags]
        print(f" -> Tech/Ops Specialist found: {tech_ops_tags}")

        _, _, _, maint_org_tags_dict = self.maint_org_specialist.analyze(common_specialist_context)
        maint_org_tags = [tag for tags in maint_org_tags_dict.values() for tag in tags]
        print(f" -> Maint/Org Specialist found: {maint_org_tags}")

        # Step C: Format Specialist Findings for Adjudicator
        specialist_findings_dict = {
            "General Analyst": general_tags,
            "Tech/Ops Specialist": tech_ops_tags,
            "Maint/Org Specialist": maint_org_tags
        }
        specialist_findings_json_string = json.dumps(specialist_findings_dict, indent=4)

        # Step D: Run Final Adjudicator
        print("\n[Step D: Running Final Adjudicator...]")
        adjudicator_context = {
            'original_evidence': original_evidence_string,
            'specialist_findings_json': specialist_findings_json_string
        }
        final_level, final_conf, final_level_scores, final_reasoning_dict = self.final_adjudicator.analyze(adjudicator_context)
        final_reasoning = [tag for tags in final_reasoning_dict.values() for tag in tags]

        # Update Final Report
        print("\n--- FINAL RISK REPORT ---")
        report = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "scenario": simulation_data['scenario_name'],
            "what_happened": "Anomaly detected in telemetry data.",
            "hfacs_level": final_level,
            "confidence": f"{final_conf}%",
            "reasoning": ", ".join(final_reasoning) if final_reasoning else "NONE",
            "intermediate_findings": specialist_findings_dict
        }

        print(f"Scenario: {report['scenario']}")
        print(f"What Happened: {report['what_happened']}")
        print(f"HFACS Level (Final): {report['hfacs_level']}")
        print(f"Confidence (Final): {report['confidence']}")
        print(f"Reasoning (Final Tags): {report['reasoning']}")
        print("\n--- Intermediate Specialist Findings ---")
        print(json.dumps(report['intermediate_findings'], indent=2))
        return report, final_level_scores


def main():
    """
    Hàm chính để chạy một luồng demo hoàn chỉnh từ đầu đến cuối.
    """
    parser = argparse.ArgumentParser(description="Full Demo of the Aviation Risk Triage Engine.")
    parser.add_argument('--scenario', type=str, default='random', help='Name of the scenario to run, or "random".')
    
    # Lấy các tham số cấu hình từ script phân loại cũ để tránh lặp lại
    # Đây là cách làm tốt để giữ cho code DRY (Don't Repeat Yourself)
    # Bạn chỉ cần đảm bảo các biến này được định nghĩa ở đâu đó
    PROJECT_ID = "aviation-classifier-sa"
    LOCATION = "us-central1"
    # Giả định thư mục gốc của dự án
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, "config", "secrets", "gcloud_credentials.json")
    
    args = parser.parse_args()

    try:
        # --- BƯỚC 1: TẠO DỮ LIỆU MÔ PHỎNG ---
        print("--- [DEMO STEP 1] Generating simulation data... ---")
        simulator = ScenarioSimulator(scenario_name=args.scenario)
        simulator.run()
        simulation_output = simulator.get_data()

        # --- BƯỚC 2: KHỞI TẠO VÀ CHẠY RISK ENGINE ---
        print("\n--- [DEMO STEP 2] Initializing and running analysis engine... ---")
        risk_engine = RiskTriageEngine(
            project_id=PROJECT_ID,
            location=LOCATION,
            credentials_path=CREDENTIALS_PATH
        )
        risk_engine.analyze_flight(simulation_output)

    except Exception:
        print("\n[FATAL ERROR] The demo failed to run.")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()