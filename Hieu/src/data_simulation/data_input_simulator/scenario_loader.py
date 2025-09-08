# file: data_input_simulator/scenario_loader.py (v1.2 - Accepts base_path)

import json
import os

class ScenarioLoader:
    """
    Chịu trách nhiệm đọc và xác thực các file kịch bản từ thư mục scenarios/.
    """
    def __init__(self):
        """
        Khởi tạo loader. Tự động tìm thư mục 'scenarios' dựa trên vị trí của file này.
        """
        # Lấy đường dẫn đến thư mục chứa file này (data_input_simulator)
        _PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        
        # Xây dựng đường dẫn đến thư mục scenarios
        self.scenarios_dir = os.path.join(_PROJECT_ROOT, 'config', 'scenarios', 'scenarios')
        
        if not os.path.isdir(self.scenarios_dir):
            raise FileNotFoundError(
                f"Scenarios directory not found at the expected path: {self.scenarios_dir}\n"
                f"Please ensure the 'scenarios' directory exists in the same directory as scenario_loader.py."
            )
            
        print(f"ScenarioLoader initialized. Reading scenarios from: {self.scenarios_dir}")


    def load(self, scenario_name: str):
        """
        Tải nội dung của một file kịch bản cụ thể.

        Args:
            scenario_name (str): Tên của kịch bản (ví dụ: "flap_jam").
                                 Không cần đuôi .json.

        Returns:
            dict: Một dictionary chứa toàn bộ nội dung của file JSON.
            
        Raises:
            FileNotFoundError: Nếu file kịch bản không tồn tại.
            json.JSONDecodeError: Nếu file không phải là JSON hợp lệ.
            ValueError: Nếu file JSON thiếu các trường bắt buộc.
        """
        file_path = os.path.join(self.scenarios_dir, f"{scenario_name}.json")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Scenario file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                self._validate_scenario_structure(data) # Kiểm tra cấu trúc
                print(f"Successfully loaded and parsed scenario: '{data.get('scenario_name')}'")
                return data
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(f"Error decoding JSON from {file_path}: {e.msg}", e.doc, e.pos)

    def list_scenarios(self) -> list[str]:
        """
        Scans the scenarios/ directory and returns a list of all available scenario names
        (without the .json extension).
        """
        scenarios = []
        for filename in os.listdir(self.scenarios_dir):
            if filename.endswith('.json'):
                scenarios.append(os.path.splitext(filename)[0])
        return sorted(scenarios) # Return sorted list for consistent behavior

    def _validate_scenario_structure(self, data: dict):
        """
        (Private method) Kiểm tra xem kịch bản có chứa các trường bắt buộc hay không.
        """
        required_keys = [
            'scenario_name', 
            'telemetry_events', 
            'maintenance_logs',
            'narrative_report',
            'context_data',
            'ground_truth'
        ]
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Scenario '{data.get('scenario_name')}' is missing required key: '{key}'")
        # print("Scenario structure validated successfully.") # Có thể bỏ comment nếu muốn log chi tiết hơn


# --- Ví dụ cách sử dụng (để test) ---
if __name__ == '__main__':
    import sys

    try:
        loader = ScenarioLoader()
        
        if len(sys.argv) > 1:
            scenario_name_from_arg = sys.argv[1]
            print(f"Attempting to load scenario from command line argument: {scenario_name_from_arg}")
            loaded_scenario = loader.load(scenario_name_from_arg)
            print("\n--- Scenario Loaded Successfully ---")
            print(f"Name: {loaded_scenario['scenario_name']}")
            print(f"Ground Truth Tags: {loaded_scenario['ground_truth']['hfacs_analysis']['evidence_tags']}")
        else:
            print("No scenario name provided as a command-line argument. Loading 'flap_jam' for demonstration.")
            flap_jam_scenario = loader.load('flap_jam')
            print("\n--- Test Load Successful (Default) ---")
            print(f"Name: {flap_jam_scenario['scenario_name']}")
            print(f"Ground Truth Tags: {flap_jam_scenario['ground_truth']['hfacs_analysis']['evidence_tags']}")

    except Exception as e:
        print("\n--- AN ERROR OCCURRED ---")
        print(e)