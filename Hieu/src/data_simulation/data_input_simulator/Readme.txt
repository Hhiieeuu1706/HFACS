data_input_simulator/
├── __init__.py
├── main_simulator.py       # File chính để chạy, chứa class ScenarioSimulator
├── scenario_loader.py      # Module để đọc và phân tích file kịch bản
├── telemetry_generator.py  # Module sinh dữ liệu cảm biến
├── document_generator.py   # Module sinh dữ liệu văn bản
├── ground_truth_generator.py # Module tạo "sự thật"
└── scenarios/                # Thư mục chứa các file kịch bản
    ├── __init__.py
    ├── flap_jam.json
    ├── hydraulic_failure.json
    ├── sensor_failure.json
    └── mechanical_asymmetry.json