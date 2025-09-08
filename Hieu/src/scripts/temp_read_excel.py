import pandas as pd
import os

excel_path = "g:\\.shortcut-targets-by-id\\1xir7002UReuNXtVU9X7CNhLq45od7PhU\\Python Project\\Hieu\\aviation_accidents\\aviation_accidents_CLASSIFIED_PANEL.xlsx"

try:
    df = pd.read_excel(excel_path)
    
    # Filter for Level 3 scenarios
    level_3_scenarios = df[df['hfacs_level'] == 'Level 3: Unsafe Supervision']
    
    if not level_3_scenarios.empty:
        print("Found Level 3 Scenarios:")
        for index, row in level_3_scenarios.iterrows():
            print(f"--- Scenario Index: {index} ---")
            print(f"Summary: {row.get('Summary', 'N/A')}")
            print(f"HFACS Level: {row.get('hfacs_level', 'N/A')}")
            print(f"HFACS Reasoning: {row.get('hfacs_reasoning', 'N/A')}")
            print("-" * 20)
    else:
        print("No Level 3 scenarios found in the Excel file.")

except FileNotFoundError:
    print(f"Error: Excel file not found at {excel_path}")
except Exception as e:
    print(f"An error occurred: {e}")
