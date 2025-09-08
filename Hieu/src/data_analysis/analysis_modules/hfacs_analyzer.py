# file: analysis_modules/hfacs_analyzer.py (v2.0 - Multi-Agent)

import json
import argparse
import time
import os

# Thư viện chuyên dụng cho Vertex AI và xác thực Service Account
import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    GenerationConfig,
    SafetySetting,
    HarmCategory,
    HarmBlockThreshold
)
from google.oauth2 import service_account
from google.api_core.exceptions import ResourceExhausted, PermissionDenied, DeadlineExceeded

# *** BƯỚC 1: DI CHUYỂN BAREM VÀO TRONG FILE NÀY ***
HFACS_RUBRIC = {
    # LEVEL 1: UNSAFE ACTS - Điểm cao vì là hành vi trực tiếp
    'L1_ILL_STRUCTURED_DECISIONS': ("Level 1: Unsafe Acts", 30),
    'L1_CHOICE_DECISIONS': ("Level 1: Unsafe Acts", 25),
    'L1_RULE_BASED_DECISIONS': ("Level 1: Unsafe Acts", 20),
    'L1_ATTENTION_FAILURES': ("Level 1: Unsafe Acts", 15),
    'L1_MEMORY_FAILURES': ("Level 1: Unsafe Acts", 15),
    'L1_TECHNIQUE_ERRORS': ("Level 1: Unsafe Acts", 20),
    'L1_MISPERCEPTIONS': ("Level 1: Unsafe Acts", 25),
    'L1_MISJUDGMENTS': ("Level 1: Unsafe Acts", 25),
    'L1_FAILED_TO_COMPLY_MANUALS': ("Level 1: Unsafe Acts", 30),
    'L1_VIOLATED_TRAINING_RULES': ("Level 1: Unsafe Acts", 30),
    'L1_VIOLATION_OF_ORDERS_SOPS': ("Level 1: Unsafe Acts", 35),
    'L1_PERFORMED_UNAUTHORIZED_OPERATION': ("Level 1: Unsafe Acts", 40),
    'L1_ACCEPTED_UNAUTHORIZED_HAZARD': ("Level 1: Unsafe Acts", 40),
    'L1_NOT_CURRENT_QUALIFIED_VIOLATION': ("Level 1: Unsafe Acts", 35),

    # LEVEL 2: PRECONDITIONS - Điểm trung bình vì là yếu tố nền
    'L2_WEATHER': ("Level 2: Preconditions for Unsafe Acts", 15),
    'L2_LIGHTING': ("Level 2: Preconditions for Unsafe Acts", 10),
    'L2_NOISE': ("Level 2: Preconditions for Unsafe Acts", 10),
    'L2_HEAT': ("Level 2: Preconditions for Unsafe Acts", 10),
    'L2_VIBRATION': ("Level 2: Preconditions for Unsafe Acts", 10),
    'L2_EQUIPMENT_AND_CONTROLS': ("Level 2: Preconditions for Unsafe Acts", 20),
    'L2_AUTOMATION_RELIABILITY': ("Level 2: Preconditions for Unsafe Acts", 20),
    'L2_TASK_PROCEDURE_DESIGN': ("Level 2: Preconditions for Unsafe Acts", 25),
    'L2_MANUALS_CHECKLIST_DESIGN': ("Level 2: Preconditions for Unsafe Acts", 25),
    'L2_INTERFACES_AND_DISPLAYS': ("Level 2: Preconditions for Unsafe Acts", 20),
    'L2_STRESS': ("Level 2: Preconditions for Unsafe Acts", 15),
    'L2_COMPLACENCY': ("Level 2: Preconditions for Unsafe Acts", 20),
    'L2_OVERCONFIDENCE': ("Level 2: Preconditions for Unsafe Acts", 20),
    'L2_MENTAL_FATIGUE': ("Level 2: Preconditions for Unsafe Acts", 20),
    'L2_DISTRACTION': ("Level 2: Preconditions for Unsafe Acts", 15),
    'L2_CONFUSION': ("Level 2: Preconditions for Unsafe Acts", 15),
    'L2_PHYSICAL_FATIGUE': ("Level 2: Preconditions for Unsafe Acts", 25),
    'L2_VISUAL_ILLUSIONS': ("Level 2: Preconditions for Unsafe Acts", 15),
    'L2_HYPOXIA': ("Level 2: Preconditions for Unsafe Acts", 30),
    'L2_MEDICAL_ILLNESS': ("Level 2: Preconditions for Unsafe Acts", 20),
    'L2_VISUAL_LIMITATIONS': ("Level 2: Preconditions for Unsafe Acts", 15),
    'L2_HEARING_LIMITATION': ("Level 2: Preconditions for Unsafe Acts", 15),
    'L2_NOT_CURRENT_QUALIFIED_LIMITATION': ("Level 2: Preconditions for Unsafe Acts", 25),
    'L2_INCOMPATIBLE_PHYSICAL_CAPABILITY': ("Level 2: Preconditions for Unsafe Acts", 20),
    'L2_INCOMPATIBLE_INTELLIGENCE_APTITUDE': ("Level 2: Preconditions for Unsafe Acts", 20),
    'L2_FAILED_TO_CONDUCT_ADEQUATE_BRIEF': ("Level 2: Preconditions for Unsafe Acts", 25),
    'L2_LACK_TO_TEAMWORK': ("Level 2: Preconditions for Unsafe Acts", 25),
    'L2_POOR_COMMUNICATION_COORDINATION': ("Level 2: Preconditions for Unsafe Acts", 25),
    'L2_FAILURE_OF_LEADERSHIP': ("Level 2: Preconditions for Unsafe Acts", 30),
    'L2_CREW_REST_REQUIREMENTS': ("Level 2: Preconditions for Unsafe Acts", 20),
    'L2_BOTTLE_TO_BRIEF_RULES': ("Level 2: Preconditions for Unsafe Acts", 20),
    'L2_SELF_MEDICATING': ("Level 2: Preconditions for Unsafe Acts", 25),
    'L2_POOR_DIETARY_PRACTICE': ("Level 2: Preconditions for Unsafe Acts", 10),
    'L2_OVEREXERTION_WHILE_OFF_DUTY': ("Level 2: Preconditions for Unsafe Acts", 10),
    'L2_INADEQUATE_PREPARATION_SKILL': ("Level 2: Preconditions for Unsafe Acts", 25),

    # LEVEL 3: UNSAFE SUPERVISION - Điểm cao vì là lỗi quản lý
    'L3_FAILURE_TO_ADMINISTER_PROPER_TRAINING': ("Level 3: Unsafe Supervision", 35),
    'L3_LACK_OF_PROFESSIONAL_GUIDANCE': ("Level 3: Unsafe Supervision", 30),
    'L3_FAILURE_TO_PROVIDE_OVERSIGHT': ("Level 3: Unsafe Supervision", 35),
    'L3_RISK_OUTWEIGHS_BENEFITS': ("Level 3: Unsafe Supervision", 30),
    'L3_EXCESSIVE_TASKING_WORKLOAD': ("Level 3: Unsafe Supervision", 25),
    'L3_POOR_CREW_PAIRING': ("Level 3: Unsafe Supervision", 25),
    'L3_FAILURE_TO_CORRECT_INAPPROPRIATE_BEHAVIOR': ("Level 3: Unsafe Supervision", 30),
    'L3_FAILURE_TO_CORRECT_A_SAFETY_HAZARD': ("Level 3: Unsafe Supervision", 50),
    'L3_FAILED_TO_ENFORCE_THE_RULES': ("Level 3: Unsafe Supervision", 35),
    'L3_AUTHORIZED_UNNECESSARY_HAZARD': ("Level 3: Unsafe Supervision", 40),
    'L3_AUTHORIZED_UNQUALIFIED_CREW_FOR_FLIGHT': ("Level 3: Unsafe Supervision", 45),

    # LEVEL 4: ORGANIZATIONAL INFLUENCES - Điểm cao nhất vì là lỗi hệ thống
    'L4_HUMAN_RESOURCES': ("Level 4: Organizational Influences", 35),
    'L4_MONETARY_RESOURCES': ("Level 4: Organizational Influences", 40),
    'L4_EQUIPMENT_FACILITY_RESOURCES': ("Level 4: Organizational Influences", 35),
    'L4_STRUCTURE': ("Level 4: Organizational Influences", 30),
    'L4_POLICIES': ("Level 4: Organizational Influences", 40),
    'L4_CULTURE': ("Level 4: Organizational Influences", 60),
    'L4_OPERATIONS_PROCESS': ("Level 4: Organizational Influences", 35),
    'L4_PROCEDURES_PROCESS': ("Level 4: Organizational Influences", 35),
    'L4_OVERSIGHT_PROCESS': ("Level 4: Organizational Influences", 40),
}
ALL_EVIDENCE_TAGS = list(HFACS_RUBRIC.keys())


class HFACSAnalyzer:
    """
    A generic AI agent that runs analysis based on a provided prompt template.
    It is initialized with a specific prompt file and connects to the Vertex AI service.
    Its 'analyze' method takes a dictionary to format the prompt, making it flexible
    for different analysis roles (e.g., Specialist, Adjudicator).
    """
    def __init__(self, project_id, location, credentials_path, prompt_path: str, project_root: str):
        self.model = None
        self.prompt_template = ""
        try:
            # Construct the full path using the provided project_root
            full_prompt_path = os.path.join(project_root, prompt_path)
            with open(full_prompt_path, 'r', encoding='utf-8') as f:
                self.prompt_template = f.read()
            print(f"Prompt loaded successfully from {full_prompt_path}")
        except FileNotFoundError:
            print(f"[ERROR] Prompt file not found at {full_prompt_path}")
            self.model = None
            return
        except Exception as e:
            print(f"[ERROR] Failed to read prompt file {full_prompt_path}: {e}")
            self.model = None
            return

        try:
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            vertexai.init(project=project_id, location=location, credentials=credentials)
            safety_settings = [SafetySetting(category=c, threshold=HarmBlockThreshold.BLOCK_NONE) for c in HarmCategory]
            generation_config = GenerationConfig(temperature=0.0, max_output_tokens=2048) # Increased token limit for complex prompts
            self.model = GenerativeModel("gemini-2.5-flash-lite", safety_settings=safety_settings, generation_config=generation_config)
            print(f"HFACSAnalyzer instance for '{os.path.basename(prompt_path)}' initialized successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to initialize HFACSAnalyzer for '{os.path.basename(prompt_path)}': {e}")
            self.model = None

    def analyze(self, prompt_context: dict, retries=6):
        """
        Performs HFACS analysis by formatting the loaded prompt with the provided context.

        Args:
            prompt_context (dict): A dictionary with keys matching the placeholders
                                   in the prompt template (e.g., {'combined_text': '...', 'ALL_EVIDENCE_TAGS': '...'}).
            retries (int): The number of times to retry on rate limit errors.

        Returns:
            A tuple containing: (winning_level, confidence, level_scores, level_evidence_tags)
            or error information if the analysis fails.
        """
        if not self.model:
            return "API_Error: Model not configured", 0, {}, {}

        try:
            # Ensure all context values are strings to prevent TypeError during formatting
            string_prompt_context = {k: str(v) for k, v in prompt_context.items()}
            prompt_to_send = self.prompt_template.format(**string_prompt_context)
            print(f"DEBUG: Prompt to send (first 500 chars): {prompt_to_send[:500]}...") # Debugging
        except KeyError as e:
            print(f"[ERROR] Missing key in prompt_context for prompt formatting: {e}")
            return f"API_Error: Prompt formatting error", 0, {}, {}
        except TypeError as e: # Catch TypeError specifically for formatting issues
            print(f"[ERROR] TypeError during prompt formatting: {e}. Context: {prompt_context}")
            return f"API_Error: PromptFormattingTypeError", 0, {}, {}

        found_tags_str = ""
        for i in range(retries):
            try:
                response = self.model.generate_content(prompt_to_send)
                if response and hasattr(response, 'text'):
                    found_tags_str = response.text.strip()
                    break
                else:
                    print(f"  -> HFACS Analyzer received an invalid response object. Type: {type(response)}, Content: {response}")
                    # Attempt to get error details if available
                    error_message = "Unknown error"
                    if hasattr(response, 'candidates') and response.candidates:
                        for candidate in response.candidates:
                            if hasattr(candidate, 'finish_reason'):
                                error_message = f"Finish Reason: {candidate.finish_reason}"
                            if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                                error_message += f", Safety Ratings: {candidate.safety_ratings}"
                    elif hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                        error_message = f"Prompt Feedback: {response.prompt_feedback}"
                    
                    print(f"  -> Error details: {error_message}")
                    return "API_Error: InvalidResponse", 0, {}, {"error_details": error_message}
            except PermissionDenied as e:
                print(f"  -> PERMISSION DENIED. Check Project ID, that Vertex AI API is enabled, and that the service account has the 'Vertex AI User' role. Error: {e}")
                return "API_Error: PermissionDenied", 0, {}, {}
            except (ResourceExhausted, DeadlineExceeded) as e: # Catch DeadlineExceeded as well
                wait_time = 2 ** (i + 1)
                error_type = "Rate Limited" if isinstance(e, ResourceExhausted) else "Timeout"
                print(f"  -> HFACS Analyzer {error_type}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                if i == retries - 1:
                    return f"API_Error: Failed after {error_type} retries", 0, {}, {}
            except Exception as e:
                import traceback
                traceback.print_exc()
                return f"API_Error: {type(e).__name__}", 0, {}, {"error": repr(e)}

        level_scores = {"Level 1: Unsafe Acts": 0, "Level 2: Preconditions for Unsafe Acts": 0, "Level 3: Unsafe Supervision": 0, "Level 4: Organizational Influences": 0}
        level_evidence_tags = {level: [] for level in level_scores.keys()}
        
        all_possible_tags = list(HFACS_RUBRIC.keys())
        
        if found_tags_str and found_tags_str.upper() != "NONE":
            # Expecting comma-separated tags or "NONE"
            found_tags = [tag.strip() for tag in found_tags_str.split(',') if tag.strip()]

            for tag in found_tags:
                if tag in all_possible_tags:
                    level_name, points = HFACS_RUBRIC[tag]
                    level_scores[level_name] += points
                    level_evidence_tags[level_name].append(tag)
                else:
                    print(f"[Warning] Tag '{tag}' returned by AI is not in the HFACS_RUBRIC.")

        total_score = sum(level_scores.values())

        if total_score > 0:
            winning_level = max(level_scores, key=level_scores.get)
            confidence_percentage = round((level_scores[winning_level] / total_score) * 100) if total_score > 0 else 0
            return winning_level, confidence_percentage, level_scores, level_evidence_tags
        else:
            return "No Fault", 100, {}, {}


# *** BƯỚC 3: TẠO HÀM MAIN ĐỂ KIỂM THỬ ĐỘC LẬP ***
def main():
    """
    Hàm chính để chạy HFACSAnalyzer từ dòng lệnh, dùng để kiểm thử.
    """
    parser = argparse.ArgumentParser(description="HFACS Analyzer for Aviation Reports.")
    parser.add_argument('--narrative_file', type=str, help='(Test Mode) Path to the narrative_report.json file.')
    parser.add_argument('--maintenance_file', type=str, help='(Test Mode) Path to the maintenance_logs.json file.')
    parser.add_argument('--context_file', type=str, help='(Test Mode) Path to the context_data.json file.')
    parser.add_argument('--project_id', type=str, required=True)
    parser.add_argument('--location', type=str, default='us-central1')
    parser.add_argument('--credentials', type=str, required=True, help='Path to GCP credentials file.')
    parser.add_argument('--prompt_path', type=str, required=True, help='Path to the prompt file for HFACS analysis.')

    args = parser.parse_args()

    analyzer = HFACSAnalyzer(
        project_id=args.project_id,
        location=args.location,
        credentials_path=args.credentials,
        prompt_path=args.prompt_path
    )
    if not analyzer.model:
        print("Exiting due to model initialization failure.")
        return

    if args.narrative_file and args.maintenance_file and args.context_file:
        print("\n--- Running in Standalone Test Mode ---")
        with open(args.narrative_file, 'r', encoding='utf-8') as f:
            narrative_data = json.load(f)
        with open(args.maintenance_file, 'r', encoding='utf-8') as f:
            maintenance_data = json.load(f)
        with open(args.context_file, 'r', encoding='utf-8') as f:
            context_data = json.load(f)

        # This is a simplified formatter for testing purposes.
        # The full orchestrator will handle this more robustly.
        input_text = "NARRATIVE REPORT (CVR):\n"
        if narrative_data and 'transcript' in narrative_data:
            for entry in narrative_data['transcript']:
                if 'speaker' in entry:
                    input_text += f"- {entry['speaker']}: {entry['dialogue']}\n"
                elif 'sound' in entry:
                    input_text += f"- (Sound: {entry['sound']})\n"
        input_text += "\nMAINTENANCE LOGS:\n"
        if maintenance_data:
            for log in maintenance_data:
                input_text += f"- {log['entry_date']}: {log['report']} | Action: {log['action']}\n"
        input_text += "\nCONTEXT DATA:\n"
        if context_data:
            for key, value in context_data.items():
                input_text += f"- {key.replace('_', ' ').title()}: {value}\n"

        # Construct a generic context dictionary for testing.
        # A real run would be orchestrated by the RiskTriageEngine with specific contexts.
        prompt_context = {
            'combined_text': input_text,
            'ALL_EVIDENCE_TAGS': ', '.join(ALL_EVIDENCE_TAGS),
            'original_evidence': input_text, 
            'specialist_findings_json': '{}' # Dummy data for testing
        }

        winning_level, confidence, _, level_evidence_tags = analyzer.analyze(prompt_context)
        
        print("\n--- HFACS ANALYSIS RESULT (Standalone Test) ---")
        print(f"Classification: {winning_level}")
        print(f"Confidence: {confidence}%")
        print(f"Evidence: {level_evidence_tags.get(winning_level, [])}")
        print("-------------------------------------------------")

    else:
        print("For standalone testing, please provide --narrative_file, --maintenance_file, and --context_file.")

if __name__ == '__main__':
    main()