import pandas as pd
import os
import json
import matplotlib.pyplot as plt
import time
from tqdm.auto import tqdm
from datetime import datetime

# Import RiskTriageEngine (which contains the HFACS Expert Panel setup)
from analysis_modules.risk_engine import RiskTriageEngine
from analysis_modules.hfacs_analyzer import ALL_EVIDENCE_TAGS

# --- Configuration ---
PROJECT_ID = "aviation-classifier-sa"
LOCATION = "us-central1"

# Determine PROJECT_ROOT dynamically
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)

CREDENTIALS_PATH = os.path.join(_PROJECT_ROOT, "gcloud_credentials.json")
EXCEL_INPUT_PATH = os.path.join(_PROJECT_ROOT, "aviation_accidents", "aviation_accidents.xlsx")
EXCEL_OUTPUT_PATH = os.path.join(_PROJECT_ROOT, "aviation_accidents", "aviation_accidents_CLASSIFIED_PANEL.xlsx")
CHART_OUTPUT_PATH = os.path.join(_PROJECT_ROOT, "aviation_accidents", "classification_chart_panel.png")

# --- Helper Function to Analyze Summary with Expert Panel ---
def analyze_summary_with_panel(risk_engine: RiskTriageEngine, summary_text: str) -> dict:
    """
    Analyzes a summary text using the HFACS Expert Panel, bypassing anomaly detection.
    """
    # Construct minimal simulation_data for _format_hfacs_input
    # This ensures the text is formatted correctly for the prompts
    narrative_report = {"transcript": [{"speaker": "Summary", "dialogue": summary_text}]}
    maintenance_logs = []
    context_data = {}

    combined_reports_input = risk_engine._format_hfacs_input(
        narrative_report,
        maintenance_logs,
        context_data
    )

    # Create a shared context for the specialists
    specialist_context = {
        'combined_text': combined_reports_input,
        'ALL_EVIDENCE_TAGS': ', '.join(ALL_EVIDENCE_TAGS)
    }

    # Step B: Run Specialized Analysts
    # We directly call the analyze method of each specialist
    _, _, _, general_tags_dict = risk_engine.general_analyst.analyze(specialist_context)
    general_tags = [tag for tags in general_tags_dict.values() for tag in tags]

    _, _, _, tech_ops_tags_dict = risk_engine.tech_ops_specialist.analyze(specialist_context)
    tech_ops_tags = [tag for tags in tech_ops_tags_dict.values() for tag in tags]

    _, _, _, maint_org_tags_dict = risk_engine.maint_org_specialist.analyze(specialist_context)
    maint_org_tags = [tag for tags in maint_org_tags_dict.values() for tag in tags]


    # Step C: Format Specialist Findings for Adjudicator
    specialist_findings_dict = {
        "General Analyst": general_tags,
        "Tech/Ops Specialist": tech_ops_tags,
        "Maint/Org Specialist": maint_org_tags
    }
    specialist_findings_json_string = json.dumps(specialist_findings_dict, indent=4)

    # Step D: Run Final Adjudicator
    adjudicator_context = {
        'original_evidence': combined_reports_input, # Use combined_reports_input as original_evidence
        'specialist_findings_json': specialist_findings_json_string,
        'ALL_EVIDENCE_TAGS': ', '.join(ALL_EVIDENCE_TAGS)
    }
    final_level, final_conf, _, final_reasoning_dict = risk_engine.final_adjudicator.analyze(adjudicator_context)
    final_reasoning = [tag for tags in final_reasoning_dict.values() for tag in tags]

    return {
        "hfacs_level": final_level,
        "hfacs_confidence": final_conf,
        "hfacs_reasoning": ", ".join(final_reasoning) if final_reasoning else "NONE",
        "intermediate_findings": specialist_findings_dict
    }

# --- Main Execution --- 
def main():
    print("--- Starting HFACS Expert Panel Analysis for Excel Data ---")

    # 1. Initialize RiskTriageEngine (which sets up the expert panel)
    try:
        risk_engine = RiskTriageEngine(
            project_id=PROJECT_ID,
            location=LOCATION,
            credentials_path=CREDENTIALS_PATH
        )
        print("   -> HFACS Expert Panel (RiskTriageEngine) initialized successfully.")
    except Exception as e:
        print(f"   -> LỖI: Không thể khởi tạo Hội đồng chuyên gia HFACS: {e}")
        print("   -> Vui lòng kiểm tra cấu hình và thông tin xác thực của bạn. Đang thoát.")
        return

    # 2. Read Excel file
    df = pd.DataFrame()
    try:
        df = pd.read_excel(EXCEL_INPUT_PATH)
        print(f"   -> Đã đọc thành công {len(df)} dòng từ file Excel: {EXCEL_INPUT_PATH}")
    except FileNotFoundError:
        print(f"   -> LỖI: Không tìm thấy file Excel tại: {EXCEL_INPUT_PATH}")
        return
    except Exception as e:
        print(f"   -> LỖI khi đọc file Excel: {e}")
        return

    # 3. Process each summary using the expert panel
    print("   -> Bắt đầu quá trình phân loại bằng Hội đồng chuyên gia...")
    results_list = []
    for index, row in tqdm(df.iterrows(), total=df.shape[0], desc="   Phân loại"):
        summary = row.get('Summary', '') # Use .get() for safety
        
        if not summary or pd.isna(summary):
            results_list.append({
                "hfacs_level": "No Summary",
                "hfacs_confidence": 0,
                "hfacs_reasoning": "NONE",
                "intermediate_findings": {}
            })
            tqdm.write(f"   [Dòng {index+1}] -> Bỏ qua: Không có tóm tắt.")
            continue

        try:
            analysis_result = analyze_summary_with_panel(risk_engine, summary)
            results_list.append(analysis_result)
            
            short_level_display = analysis_result['hfacs_level'].split(':')[0] if ':' in analysis_result['hfacs_level'] else analysis_result['hfacs_level']
            tqdm.write(f"   [Dòng {index+1}] -> {short_level_display} (Conf: {analysis_result['hfacs_confidence']}%) | Tags: {analysis_result['hfacs_reasoning']}")
            time.sleep(3) # Add a delay to avoid API rate limits

        except Exception as e:
            results_list.append({
                "hfacs_level": "API_Error",
                "hfacs_confidence": 0,
                "hfacs_reasoning": f"Lỗi: {e}",
                "intermediate_findings": {}
            })
            tqdm.write(f"   [Dòng {index+1}] -> LỖI API: {e}")
            time.sleep(3) # Still add delay on error

    print("\n   -> Quá trình phân loại đã hoàn tất!")

    # 4. Add results to DataFrame
    df_results = pd.DataFrame(results_list)
    df = pd.concat([df, df_results], axis=1)
    print("   -> Đã gán kết quả phân loại vào DataFrame.")

    # 5. Save results to new Excel file
    try:
        df_to_save = df.copy()
        # Ensure all columns from original df are present, plus new ones
        df_to_save.to_excel(EXCEL_OUTPUT_PATH, index=False)
        print(f"   -> Đã lưu thành công file kết quả tại: {EXCEL_OUTPUT_PATH}")
    except Exception as e:
        print(f"   -> LỖI khi lưu file Excel: {e}")

    # 6. Generate and save chart
    print("\n--- Đang tạo biểu đồ thống kê ---")
    category_order = [
        'No Summary', 'No Fault', 'Level 1: Unsafe Acts', 'Level 2: Preconditions for Unsafe Acts',
        'Level 3: Unsafe Supervision', 'Level 4: Organizational Influences', 'API_Error'
    ]
    
    # Filter out rows that are not valid HFACS levels for charting, but keep API_Error and No Summary
    valid_results_df = df[df['hfacs_level'].isin(category_order)].copy()
    valid_results_df['hfacs_confidence'] = pd.to_numeric(valid_results_df['hfacs_confidence'], errors='coerce').fillna(0)
    category_counts = valid_results_df['hfacs_level'].value_counts().reindex(category_order, fill_value=0)
    avg_confidence_per_category = valid_results_df.groupby('hfacs_level')['hfacs_confidence'].mean().reindex(category_order, fill_value=0)

    plt.figure(figsize=(14, 8))
    ax = plt.gca()
    bars = ax.bar(category_counts.index, category_counts.values, color='skyblue', width=0.6)
    
    for bar, avg_conf in zip(bars, avg_confidence_per_category):
        height = bar.get_height()
        if height > 0 and pd.notna(avg_conf):
            ax.text(bar.get_x() + bar.get_width() / 2, height, 
                    f'Avg Conf: {avg_conf:.1f}%',
                    ha='center', va='bottom', fontsize=9, color='darkblue')

    plt.title('Phân loại tai nạn theo Cấu trúc HFACS (Hội đồng chuyên gia AI)', fontsize=16)
    plt.ylabel('Số lượng sự cố', fontsize=12)
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout() # Adjust layout to prevent labels from overlapping
    
    try:
        plt.savefig(CHART_OUTPUT_PATH)
        print(f"   -> Biểu đồ đã được lưu tại: {CHART_OUTPUT_PATH}")
    except Exception as e:
        print(f"   -> LỖI khi lưu biểu đồ: {e}")
    
    # plt.show() # Uncomment to display chart immediately

    print("--- TOÀN BỘ QUÁ TRÌNH ĐÃ HOÀN TẤT ---")

if __name__ == '__main__':
    main()