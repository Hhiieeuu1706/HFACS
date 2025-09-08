# file: data_input_simulator/ground_truth_generator.py

from .scenario_loader import ScenarioLoader

class GroundTruthGenerator:
    """
    Chịu trách nhiệm trích xuất thông tin "sự thật" (ground truth)
    từ một kịch bản đã được tải. Dữ liệu này sẽ được dùng để
    đánh giá hiệu suất của các mô hình AI.
    """
    def __init__(self, scenario_config: dict):
        """
        Khởi tạo generator với cấu hình của một kịch bản cụ thể.

        Args:
            scenario_config (dict): Đối tượng dictionary chứa toàn bộ
                                    thông tin kịch bản từ file JSON.
        """
        if not isinstance(scenario_config, dict):
            raise TypeError("scenario_config must be a dictionary.")
        self.config = scenario_config

    def generate(self) -> dict:
        """
        Trích xuất và trả về toàn bộ đối tượng ground truth từ kịch bản.
        
        Bao gồm thông tin để kiểm thử cả Anomaly Detector và HFACS Classifier.

        Returns:
            dict: Một dictionary chứa thông tin "sự thật".
                  Ví dụ: 
                  {
                      "is_anomaly": True,
                      "anomaly_timestamp": 3600,
                      "hfacs_analysis": {
                          "winning_level": "Level 3: Unsafe Supervision",
                          "evidence_tags": ["L3_TAG", "L2_TAG"]
                      }
                  }
        """
        # Đơn giản là lấy toàn bộ khối 'ground_truth' từ file config
        ground_truth_data = self.config.get('ground_truth', {})

        # (Tùy chọn) Có thể thêm bước kiểm tra để đảm bảo các trường cần thiết tồn tại
        if 'is_anomaly' not in ground_truth_data or 'hfacs_analysis' not in ground_truth_data:
            raise ValueError("Ground truth data is missing required keys ('is_anomaly', 'hfacs_analysis').")
            
        return ground_truth_data

# --- Ví dụ cách sử dụng (kết hợp với ScenarioLoader) ---
if __name__ == '__main__':
    # Đoạn code này chỉ chạy khi bạn thực thi trực tiếp file này

    try:
        # Bước 1: Tải kịch bản
        loader = ScenarioLoader()
        flap_jam_scenario = loader.load('flap_jam')
        
        # Bước 2: Khởi tạo GroundTruthGenerator với kịch bản đó
        truth_gen = GroundTruthGenerator(flap_jam_scenario)

        # Bước 3: Tạo và in ra dữ liệu "sự thật"
        ground_truth = truth_gen.generate()

        print("\n--- Generated Ground Truth ---")
        print(f"Is Anomaly: {ground_truth['is_anomaly']}")
        print("HFACS Analysis:")
        print(f"  -> Winning Level: {ground_truth['hfacs_analysis']['winning_level']}")
        print(f"  -> Expected Evidence Tags: {ground_truth['hfacs_analysis']['evidence_tags']}")

    except Exception as e:
        print("\n--- AN ERROR OCCURRED ---")
        print(e)
