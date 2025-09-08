import pandas as pd
import os
import matplotlib.pyplot as plt
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

# ==============================================================================
# BƯỚC 1: IMPORT CÁC THƯ VIỆN (Không thay đổi)
# ==============================================================================
print("--- BƯỚC 1: Đang import các thư viện ---")

# =============================================================================
# BƯỚC 2: CẤU HÌNH API, BAREM CHẤM ĐIỂM, VÀ HÀM CHỨC NĂNG
# =============================================================================
print("\n--- BƯỚC 2: Đang cấu hình API, Barem và các hàm chức năng ---")

# *** THÔNG TIN CẦN THAY ĐỔI (Đảm bảo chính xác Project ID) ***
PROJECT_ID = "aviation-classifier-sa"
LOCATION = "us-central1"
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_PATH, "..", "gcloud_credentials.json")

# *** BƯỚC 2.1: BAREM CHẤM ĐIỂM DỰA TRÊN CẤU TRÚC HFACS BẠN CUNG CẤP ***
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
    
    print("   -> Vertex AI SDK đã khởi tạo thành công.")
except Exception as e:
    print(f"   -> LỖI CẤU HÌNH API: {repr(e)}")

def classify_hfacs_structured(summary_text: str, retries=6):
    prompt_template = f"""
You are an expert HFACS analyst. Your task is to classify the provided flight report according to the HFACS framework.

**IMPORTANT: First, determine if any actual error or unsafe condition exists. Many reports describe normal, routine flights with no errors. If there is no clear evidence of an error, violation, or unsafe condition, you MUST return "NONE". Do not infer errors from standard operational language.**

If, and only if, you find clear evidence of errors, perform a comprehensive, multi-level analysis.

**Critical Thinking Guidance (Updated):**
- Prioritize direct evidence: Only select tags that are directly supported by text in the CVR, Maintenance Logs, Context Data, or investigation notes. Avoid inferring psychological states (like L2_CONFUSION or L2_STRESS) unless explicitly stated.
- Elevate Organizational Factors: Pay highest attention to evidence of organizational decisions or policies (e.g., "training was removed", "policy to extend maintenance intervals"). These are often the ultimate root cause and should always be tagged if present.

**Analysis Process (Chain of Thought):**
1.  **Analyze for Level 1 Evidence:** Read the summary and identify any evidence of direct operator errors or violations (Unsafe Acts).
2.  **Analyze for Level 2 Evidence:** Read the summary and identify any evidence of preconditions (Environmental Factors, Condition of Employees, etc.). Pay attention to technical descriptions of failures (e.g., "flap jammed", "hydraulic pressure lost").
3.  **Analyze for Level 3 Evidence:** Read the summary and identify any evidence of supervisory failures (e.g., inadequate oversight, failure to correct known problems).
4.  **Analyze for Level 4 Evidence:** Read the summary and identify any evidence of organizational influences (e.g., policies, culture, resource management).
5.  **Synthesize:** Combine all the evidence tags you found from all four levels into a single list.

Here is the list of all possible HFACS categories:
{ALL_EVIDENCE_TAGS}

**OUTPUT REQUIREMENT (VERY STRICT):**
- After completing your multi-level analysis, return a SINGLE LINE of text containing ONLY the identified category TAGS from ALL levels, separated by commas.
- If you find no relevant evidence for any category after checking all levels, return the word "NONE".
- DO NOT add any explanation or summary. Just the final list of tags.

**Example:**
Summary: "The aircraft stalled and crashed during takeoff. The investigation found the crew had not configured the flaps correctly, a step that was missed during their pre-flight checks. The airline had a history of rushing crews, leading to procedural shortcuts."
Your output: L1_TECHNIQUE_ERRORS, L2_INADEQUATE_PREPARATION_SKILL, L4_CULTURE

Combined Flight Report to analyze:
---
{summary_text}
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
        except (ResourceExhausted, PermissionDenied):
            wait_time = 2 ** (i + 1)
            tqdm.write(f"\n   -> Gặp lỗi Rate Limit/Permission. Đang đợi {wait_time} giây... (lần thử {i+2}/{retries})")
            time.sleep(wait_time)
            if i == retries - 1:
                return "API_Error: Failed after retries", 0, "Rate limit"
        except Exception as e:
            return f"API_Error: {type(e).__name__}", 0, repr(e)

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

# =============================================================================
# BƯỚC 3: XỬ LÝ DỮ LIỆU
# =============================================================================
print("\n--- BƯỚC 3: Đang đọc và xử lý dữ liệu ---")
file_path = os.path.join(BASE_PATH, "..", "aviation_accidents", "aviation_accidents.xlsx")
df = pd.DataFrame() 

if model:
    try:
        df = pd.read_excel(file_path)
        print(f"   -> Đã đọc thành công {len(df)} dòng từ file Excel.")
        print("   -> Bắt đầu quá trình phân loại theo cấu trúc HFACS...")
        
        results_list = []
        for index, row in tqdm(df.iterrows(), total=df.shape[0], desc="   Classifying"):
            summary = row['Summary']
            
            hfacs_level, confidence_score, reasoning = classify_hfacs_structured(summary, retries=6)
            
            results_list.append((hfacs_level, confidence_score, reasoning))
            
            short_level_display = hfacs_level.split(':')[0] if ':' in hfacs_level else hfacs_level
            
            score_breakdown_display = ""
            if '|' in reasoning:
                score_breakdown_display = reasoning.split('|')[0].strip().replace('/', ' ')
            
            error_detail = ""
            if "API_Error" in hfacs_level:
                error_detail = f" | Chi tiết lỗi: {reasoning}"

            console_output = f"   [Dòng {index+1}/{len(df)}] -> {short_level_display} (Conf: {confidence_score}%) | {score_breakdown_display}{error_detail}"
            
            tqdm.write(console_output)
            
            time.sleep(1.2)

        print("\n\n   -> Quá trình phân loại đã hoàn tất!")
        df['hfacs_level'] = [r[0] for r in results_list]
        df['hfacs_confidence'] = [r[1] for r in results_list]
        df['hfacs_reasoning'] = [r[2] for r in results_list]
        print("   -> Đã gán kết quả phân loại vào DataFrame.")

    except Exception as e:
        print(f"   -> LỖI NGHIÊM TRỌNG trong quá trình xử lý: {repr(e)}")
else:
    print("   -> Bỏ qua BƯỚC 3 do lỗi cấu hình API.")


# =============================================================================
# BƯỚC 4: TỔNG HỢP VÀ VẼ BIỂU ĐỒ
# =============================================================================
if not df.empty and 'hfacs_level' in df.columns:
    print("\n--- BƯỚC 4: Đang tạo biểu đồ thống kê ---")
    category_order = [
        'Other/Uncategorized', 'Level 1: Unsafe Acts', 'Level 2: Preconditions for Unsafe Acts',
        'Level 3: Unsafe Supervision', 'Level 4: Organizational Influences'
    ]
    
    api_errors = df[~df['hfacs_level'].str.startswith(('Level', 'Other/'), na=False)]
    if not api_errors.empty:
      print(f"   -> Cảnh báo: Phát hiện {len(api_errors)} lỗi định dạng hoặc lỗi API trong quá trình xử lý.")
      print("   -> Thống kê chi tiết lỗi:\n", df.loc[api_errors.index, 'hfacs_level'].value_counts())

    valid_results_df = df[df['hfacs_level'].str.startswith(('Level', 'Other/'), na=False)].copy()
    valid_results_df['hfacs_confidence'] = pd.to_numeric(valid_results_df['hfacs_confidence'], errors='coerce').fillna(0)
    category_counts = valid_results_df['hfacs_level'].value_counts().reindex(category_order, fill_value=0)
    avg_confidence_per_category = valid_results_df.groupby('hfacs_level')['hfacs_confidence'].mean().reindex(category_order, fill_value=0)

    plt.figure(figsize=(12, 7))
    ax = plt.gca()
    bars = ax.bar(category_counts.index, category_counts.values, color='skyblue', width=0.6)
    
    for bar, avg_conf in zip(bars, avg_confidence_per_category):
        height = bar.get_height()
        if height > 0 and pd.notna(avg_conf):
            ax.text(bar.get_x() + bar.get_width() / 2, height, 
                    f'Avg Conf: {avg_conf:.1f}%',
                    ha='center', va='bottom', fontsize=9, color='darkblue')

    plt.title('Phân loại tai nạn theo Cấu trúc HFACS (Explainable AI Method)', fontsize=16)
    plt.ylabel('Number of Accidents', fontsize=12)
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    plot_path = os.path.join(BASE_PATH, "..", "aviation_accidents", "classification_chart_structured.png")
    plt.savefig(plot_path)
    print(f"   -> Biểu đồ đã được lưu tại: {plot_path}")
    
    # plt.show()

# =============================================================================
# BƯỚC 5: LƯU KẾT QUẢ
# =============================================================================
if not df.empty and 'hfacs_level' in df.columns:
    print("\n--- BƯỚC 5: Đang lưu kết quả ra file Excel ---")
    output_path = os.path.join(BASE_PATH, "..", "aviation_accidents", "aviation_accidents_CLASSIFIED_STRUCTURED.xlsx")
    try:
        df_to_save = df[['Date', 'Time', 'Location', 'Operator', 'Route', 'AC Type', 'Summary', 
                         'hfacs_level', 'hfacs_confidence', 'hfacs_reasoning']]
        df_to_save.to_excel(output_path, index=False)
        print(f"   -> Đã lưu thành công file kết quả tại: {output_path}")
    except Exception as e:
        print(f"   -> Lỗi khi lưu file: {repr(e)}")

print("--- TOÀN BỘ QUÁ TRÌNH ĐÃ HOÀN TẤT ---")