# file: data_input_simulator/document_generator.py

from .scenario_loader import ScenarioLoader

class DocumentGenerator:
    """
    Chịu trách nhiệm tạo ra các nguồn dữ liệu dạng văn bản/JSON
    dựa trên một kịch bản đã được tải.
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

    def generate_maintenance_logs(self) -> list:
        """
        Trích xuất và trả về danh sách các bản ghi bảo trì.
        """
        # Đơn giản là lấy dữ liệu đã có sẵn trong config
        return self.config.get('maintenance_logs', [])

    def generate_narrative_report(self) -> dict:
        """
        Trích xuất và trả về báo cáo tường thuật (ví dụ: CVR).
        """
        return self.config.get('narrative_report', {})

    def generate_context_data(self) -> dict:
        """
        Trích xuất và trả về dữ liệu bối cảnh (Thời tiết & ATC).
        """
        return self.config.get('context_data', {})

    def generate_all_documents(self) -> dict:
        """
        Gọi tất cả các hàm generate và trả về một dictionary
        chứa toàn bộ dữ liệu văn bản.
        """
        return {
            "maintenance_logs": self.generate_maintenance_logs(),
            "narrative_report": self.generate_narrative_report(),
            "context_data": self.generate_context_data()
        }

# --- Ví dụ cách sử dụng (kết hợp với ScenarioLoader) ---
if __name__ == '__main__':
    # Đoạn code này chỉ chạy khi bạn thực thi trực tiếp file này
    # Dùng để kiểm tra nhanh

    try:
        # Bước 1: Tải kịch bản
        loader = ScenarioLoader()
        flap_jam_scenario = loader.load('flap_jam')
        
        # Bước 2: Khởi tạo DocumentGenerator với kịch bản đó
        doc_gen = DocumentGenerator(flap_jam_scenario)

        # Bước 3: Tạo và in ra dữ liệu
        all_docs = doc_gen.generate_all_documents()

        print("\n--- Generated Maintenance Logs ---")
        for log in all_docs['maintenance_logs']:
            print(f"- Date: {log['entry_date']}, Report: {log['report']}")

        print("\n--- Generated Narrative Report (CVR) ---")
        for entry in all_docs['narrative_report']['transcript']:
            if 'speaker' in entry:
                print(f"[{entry['relative_timestamp']}] {entry['speaker']}: {entry['dialogue']}")
            else:
                print(f"[{entry['relative_timestamp']}] Sound: {entry['sound']}")

        print("\n--- Generated Context Data ---")
        print(f"Weather: {all_docs['context_data']['weather']}")
        print(f"ATC: {all_docs['context_data']['atc_communication']}")

    except Exception as e:
        print("\n--- AN ERROR OCCURRED ---")
        print(e)
