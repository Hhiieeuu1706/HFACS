import os
import time
from tqdm.auto import tqdm

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
from google.api_core.exceptions import ResourceExhausted, PermissionDenied

# *** THÔNG TIN CẦN THAY ĐỔI (Đảm bảo chính xác Project ID) ***
PROJECT_ID = "aviation-classifier-sa"
LOCATION = "us-central1"
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_PATH, "..", "gcloud_credentials.json") # Adjusted path for credentials
print(f"DEBUG: CREDENTIALS_PATH: {CREDENTIALS_PATH}") # Added debug print

# *** BAREM CHẤM ĐIỂM DỰA TRÊN CẤU TRÚC HFACS BẠN CUNG CẤP ***
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
    'L1_NOT_CURRENT_QUALIFIED_VIOLATION': ("Level 2: Preconditions for Unsafe Acts", 35), # This was L1 in original, moved to L2 as per HFACS structure

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
    'L3_FAILURE_TO_CORRECT_A_SAFETY_HAZARD': ("Level 3: Unsafe Supervision", 40),
    'L3_FAILED_TO_ENFORCE_THE_RULES': ("Level 3: Unsafe Supervision", 35),
    'L3_AUTHORIZED_UNNECESSARY_HAZARD': ("Level 3: Unsafe Supervision", 40),
    'L3_AUTHORIZED_UNQUALIFIED_CREW_FOR_FLIGHT': ("Level 3: Unsafe Supervision", 45),

    # LEVEL 4: ORGANIZATIONAL INFLUENCES - Điểm cao nhất vì là lỗi hệ thống
    'L4_HUMAN_RESOURCES': ("Level 4: Organizational Influences", 35),
    'L4_MONETARY_RESOURCES': ("Level 4: Organizational Influences", 40),
    'L4_EQUIPMENT_FACILITY_RESOURCES': ("Level 4: Organizational Influences", 35),
    'L4_STRUCTURE': ("Level 4: Organizational Influences", 30),
    'L4_POLICIES': ("Level 4: Organizational Influences", 40),
    'L4_CULTURE': ("Level 4: Organizational Influences", 45),
    'L4_OPERATIONS_PROCESS': ("Level 4: Organizational Influences", 35),
    'L4_PROCEDURES_PROCESS': ("Level 4: Organizational Influences", 35),
    'L4_OVERSIGHT_PROCESS': ("Level 4: Organizational Influences", 40),
}
ALL_EVIDENCE_TAGS = list(HFACS_RUBRIC.keys())

model = None 
try:
    credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)
    vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
    safety_settings = [SafetySetting(category=c, threshold=HarmBlockThreshold.BLOCK_NONE) for c in HarmCategory]
    generation_config = GenerationConfig(temperature=0.0, max_output_tokens=512)
    
    model = GenerativeModel("gemini-2.5-flash-lite", safety_settings=safety_settings, generation_config=generation_config)
    
    print("   -> Vertex AI SDK đã khởi tạo thành công trong hfacs_classifier.")
    print(f"DEBUG: Model object after init: {model}") # Added debug print
except Exception as e:
    print(f"   -> LỖI CẤU HÌNH API trong hfacs_classifier: {repr(e)}")
    print(f"DEBUG: Model object after failed init: {model}") # Added debug print

def _format_input_text_from_simulator(narrative_report: dict, maintenance_logs: list) -> str:
    """
    Định dạng dữ liệu đầu vào từ simulator thành một chuỗi văn bản duy nhất cho prompt.
    """
    input_text = "NARRATIVE REPORT (CVR):\n"
    if narrative_report and 'transcript' in narrative_report:
        for entry in narrative_report['transcript']:
            if 'speaker' in entry:
                input_text += f"- {entry['speaker']}: {entry['dialogue']}\n"
            elif 'sound' in entry:
                input_text += f"- (Sound: {entry['sound']})\n"
    
    input_text += "\nMAINTENANCE LOGS:\n"
    if maintenance_logs:
        for log in maintenance_logs:
            input_text += f"- {log['entry_date']}: {log['report']} | Action: {log['action']}\n"
    
    return input_text

def classify_hfacs_structured(narrative_report: dict, maintenance_logs: list, retries=6):
    print(f"DEBUG: classify_hfacs_structured received narrative_report (first 100 chars): {str(narrative_report)[:100]}...") # Added debug print
    print(f"DEBUG: classify_hfacs_structured received maintenance_logs: {maintenance_logs}") # Added debug print
    
    combined_text = _format_input_text_from_simulator(narrative_report, maintenance_logs)
    print(f"DEBUG: Combined text for prompt (first 200 chars): {combined_text[:200]}...") # Added debug print

    prompt_template = f"""
    You are an expert HFACS analyst. Your task is to perform a comprehensive, multi-level analysis of the provided reports.

    **Analysis Process (Chain of Thought):**
    1.  **Analyze for Level 1 Evidence:** Read the reports and identify any evidence of direct operator errors or violations (Unsafe Acts).
    2.  **Analyze for Level 2 Evidence:** Read the reports and identify any evidence of preconditions (Environmental Factors, Condition of Employees, etc.). Pay attention to technical descriptions of failures (e.g., "flap jammed", "hydraulic pressure lost").
    3.  **Analyze for Level 3 Evidence:** Read the reports, especially the Maintenance Logs, and identify any evidence of supervisory failures (e.g., inadequate oversight, failure to correct known problems).
    4.  **Analyze for Level 4 Evidence:** Read the reports and identify any evidence of organizational influences (e.g., policies, culture, resource management).
    5.  **Synthesize:** Combine all the evidence tags you found from all four levels into a single list.

    Here is the list of all possible HFACS categories:
    {', '.join(ALL_EVIDENCE_TAGS)}

    **OUTPUT REQUIREMENT (VERY STRICT):**
    - After completing your multi-level analysis, return a SINGLE LINE of text containing ONLY the identified category TAGS from ALL levels, separated by commas.
    - If you find no relevant evidence for any category after checking all levels, return the word "NONE".
    - DO NOT add any explanation or summary. Just the final list of tags.

    **Example:**
    Summary: "CVR: 'The controls feel sluggish.' Maintenance Log: 'Pilot reported sluggish controls, technician could not replicate. Attributed to cold weather.'"
    Your output: L2_EQUIPMENT_AND_CONTROLS, L3_FAILURE_TO_CORRECT_A_SAFETY_HAZARD

    Combined Reports to analyze:
    ---
    {combined_text}
    ---
    """
    if model is None:
        return "API_Error: Model not configured", 0, ""

    found_tags_str = ""
    for i in range(retries):
        try:
            response = model.generate_content(prompt_template)
            found_tags_str = response.text.strip()
            break
        except (ResourceExhausted, PermissionDenied) as e:
            wait_time = 2 ** (i + 1)
            tqdm.write(f"\n   -> Gặp lỗi Rate Limit/Permission. Đang đợi {wait_time} giây... (lần thử {i+2}/{retries+1})")
            time.sleep(wait_time)
            if i == retries - 1:
                return "API_Error: Failed after retries", 0, "Rate limit"
        except Exception as e:
            return f"API_Error: {type(e).__name__}", 0, repr(e)

    print(f"DEBUG: Model raw output (found_tags_str): '{found_tags_str}'") # Added debug print
    # Step 2: Python tính điểm và quyết định
    level_scores = {"Level 1: Unsafe Acts": 0, "Level 2: Preconditions for Unsafe Acts": 0, "Level 3: Unsafe Supervision": 0, "Level 4: Organizational Influences": 0}
    level_evidence_tags = {level: [] for level in level_scores.keys()}
    
    if found_tags_str and found_tags_str.upper() != "NONE":
        found_tags = [tag.strip() for tag in found_tags_str.split(',') if tag.strip() in ALL_EVIDENCE_TAGS]
        for tag in found_tags:
            level_name, points = HFACS_RUBRIC[tag]
            level_scores[level_name] += points
            level_evidence_tags[level_name].append(tag)
    
    total_score = sum(level_scores.values())

    if total_score > 0:
        winning_level = max(level_scores, key=level_scores.get)
        confidence_percentage = round((level_scores[winning_level] / total_score) * 100) if total_score > 0 else 0
        
        score_breakdown = "/".join([f"L{i+1}({level_scores[f'Level {i+1}: {name}']})" for i, name in enumerate(["Unsafe Acts", "Preconditions for Unsafe Acts", "Unsafe Supervision", "Organizational Influences"])])
        reasoning_str = f"{score_breakdown} | Evidence: {level_evidence_tags[winning_level]}"
        
        return winning_level, confidence_percentage, reasoning_str
    else:
        return "Other/Uncategorized", 100, "No evidence tags identified by AI."
