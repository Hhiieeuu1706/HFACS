import os
import sys
import time
import random
import webbrowser
from threading import Thread, Event, Timer
from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO

# --- Matplotlib Backend Configuration ---
# This is a CRITICAL fix. It prevents matplotlib from trying to use a GUI backend
# (like Tkinter) in a background thread, which causes the "main thread is not in main loop" error.
import matplotlib
matplotlib.use('Agg')

# --- Path Management ---
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.data_simulation.data_input_simulator.scenario_loader import ScenarioLoader
from src.data_simulation.data_input_simulator.telemetry_generator import TelemetryGenerator, plot_scenario_telemetry
from src.data_simulation.data_input_simulator.document_generator import DocumentGenerator
from src.data_simulation.data_input_simulator.ground_truth_generator import GroundTruthGenerator
from src.data_analysis.analysis_modules.anomaly_detector import AnomalyDetector
from src.data_analysis.analysis_modules.hfacs_analyzer import HFACSAnalyzer, HFACS_RUBRIC

# --- Flask App Setup ---
app = Flask(__name__)
print("DEBUG: Flask app created.")
socketio = SocketIO(app, async_mode='eventlet')
print("DEBUG: SocketIO initialized.")
thread = None
thread_stop_event = Event()

# --- Expert Upgrade Config ---
ANOMALY_PRIORITY_MAP = {
    "GREEN_HYDRAULIC_LOSS": "HIGH",
    "FLAP_STUCK": "HIGH",
    "G_FORCE_ANOMALY": "HIGH",
    "CRITICAL_ECAM_ALERT": "HIGH",
    "DEFAULT": "MEDIUM"
}

ANOMALY_FRIENDLY_NAMES = {
    "GREEN_HYDRAULIC_LOSS": "Green Hydraulic System Loss",
    "FLAP_STUCK": "Flap Stuck/Unresponsive",
    "G_FORCE_ANOMALY": "Unusual G-Force Detected",
    "CRITICAL_ECAM_ALERT": "Critical ECAM Alert",
    "FLAP_ASYMMETRY": "Flap Asymmetry",
    "MOTOR_CURRENT_FAILURE": "Flap Motor Current Failure",
    "SENSOR_FAILURE": "Sensor Failure",
    "ENGINE_VIBRATION_EXCEEDANCE": "Engine Vibration Exceedance",
    "ENGINE_EGT_EXCEEDANCE": "Engine EGT Exceedance",
    "CABIN_ALTITUDE_EXCEEDANCE": "Cabin Altitude Exceedance",
    "G_FORCE_EXCEEDANCE": "G-Force Exceedance",
}

ANOMALY_PROCEDURES = {
    "GREEN_HYDRAULIC_LOSS": [
        "1. Notify Flight Crew of System Loss.",
        "2. Advise on available alternate airports.",
        "3. Coordinate with Maintenance Control."
    ],
    "FLAP_STUCK": [
        "1. Notify Flight Crew of Flap Malfunction.",
        "2. Advise on flapless landing procedures.",
        "3. Prepare for emergency services on arrival."
    ],
    "G_FORCE_ANOMALY": [
        "1. Notify Flight Crew of G-Force Exceedance.",
        "2. Advise on smooth flight path adjustments.",
        "3. Log event for post-flight inspection."
    ],
    "CRITICAL_ECAM_ALERT": [
        "1. Acknowledge ECAM alert with Flight Crew.",
        "2. Monitor system parameters closely.",
        "3. Prepare for relevant emergency procedures."
    ],
    "DEFAULT": [
        "1. Monitor system parameters.",
        "2. Await further instructions from Flight Crew."
    ]
}

# G-Force monitoring thresholds
MAX_G_FORCE_THRESHOLD = 1.5
MIN_G_FORCE_THRESHOLD = 0.5

# --- Simulation Logic (v4.0 - Full Expert Integration) ---
def get_flight_phase(timestamp: float) -> str:
    if timestamp < 5: return "TAXI/TAKEOFF"
    elif timestamp < 20: return "CLIMB"
    elif timestamp < 90: return "CRUISE"
    elif timestamp < 115: return "DESCENT"
    elif timestamp < 125: return "FINAL APPROACH"
    elif timestamp < 135: return "LANDED / ROLLOUT"
    else: return "SHUTDOWN"

def run_simulation():
    speed_multiplier = 2.0
    flight_id = "VN-A688"

    scenarios_path = os.path.join(_PROJECT_ROOT, 'config', 'scenarios', 'scenarios')
    print(f"DEBUG: Scenarios path: {scenarios_path}")
    try:
        all_scenarios = [f.replace('.json', '') for f in os.listdir(scenarios_path) if f.endswith('.json') and f != 'normal_flight.json']
        print(f"DEBUG: Found scenarios: {all_scenarios}")
        scenario_name = random.choice(all_scenarios)
    except Exception as e:
        print(f"DEBUG: Scenario loading failed with error: {e}")
        socketio.emit('update', {'error': f"Scenario loading failed: {e}"})
        return

    loader = ScenarioLoader()
    config = loader.load(scenario_name)
    print(f"DEBUG: Scenario config loaded for: {scenario_name}")
    telemetry_gen = TelemetryGenerator(config)
    full_telemetry_df = telemetry_gen.generate()
    print(f"DEBUG: Telemetry generated. Shape: {full_telemetry_df.shape}")
    anomaly_detector = AnomalyDetector()
    all_anomalies = anomaly_detector.detect(full_telemetry_df.copy())

    # Generate and save the telemetry plot for the current scenario
    # --- GCP Configuration (Replace with your actual values) ---
    GCP_PROJECT_ID = "aviation-classifier-sa"  # Replace with your GCP Project ID
    GCP_LOCATION = "us-central1"
    GCP_CREDENTIALS_PATH = os.path.join(_PROJECT_ROOT, 'config', 'secrets', 'gcloud_credentials.json')
    HFACS_PROMPT_PATH = os.path.join(_PROJECT_ROOT, 'config', 'prompts', 'prompts', 'hfacs_analyzer_prompt.txt')

    try:
        hfacs_analyzer = HFACSAnalyzer(
            project_id=GCP_PROJECT_ID,
            location=GCP_LOCATION,
            credentials_path=GCP_CREDENTIALS_PATH,
            prompt_path=HFACS_PROMPT_PATH,
            project_root=_PROJECT_ROOT
        )
        if not hfacs_analyzer.model:
            print("[ERROR] HFACSAnalyzer could not be initialized. Check GCP credentials and project settings.")
            socketio.emit('update', {'error': "HFACSAnalyzer initialization failed."})
            return
    except Exception as e:
        print(f"[ERROR] HFACSAnalyzer initialization failed: {e}")
        socketio.emit('update', {'error': f"HFACSAnalyzer initialization failed: {e}"})
        return

    doc_gen = DocumentGenerator(config)
    ground_truth_gen = GroundTruthGenerator(config)

    print("\n[2/4] Generating Document Data...")
    document_data = doc_gen.generate_all_documents()

    # Perform HFACS classification on the narrative report
    narrative_report_text = document_data["narrative_report"]
    print("\n[2.5/4] Classifying Narrative Report with HFACS...")
    combined_text = f"""Narrative Report:
{document_data['narrative_report']}

Maintenance Logs:
{document_data['maintenance_logs']}

Context Data:
{document_data['context_data']}"""

    hfacs_level, hfacs_confidence, level_scores, level_evidence_tags = hfacs_analyzer.analyze(
        {
            "combined_text": combined_text,
            "ALL_EVIDENCE_TAGS": ", ".join(HFACS_RUBRIC.keys())
        }
    )
    score_breakdown_parts = []
    level_names = ["Unsafe Acts", "Preconditions for Unsafe Acts", "Unsafe Supervision", "Organizational Influences"]
    for i, name in enumerate(level_names):
        level_key = f"Level {i+1}: {name}"
        score = level_scores.get(level_key, 0)
        score_breakdown_parts.append(f"L{i+1}({score})")

    score_breakdown = "/".join(score_breakdown_parts)
    hfacs_reasoning = f"{score_breakdown} | Evidence: {level_evidence_tags.get(hfacs_level, [])}"

    print(f"  -> Classified as: {hfacs_level} (Confidence: {hfacs_confidence}%)")
    print(f"  -> Reasoning: {hfacs_reasoning}")

    # Generate and save the telemetry plot for the current scenario
    plot_scenario_telemetry(
        telemetry_data=full_telemetry_df,
        scenario_name=scenario_name,
        scenario_config=config, # Pass the scenario config
        output_dir=os.path.join(_PROJECT_ROOT, 'outputs'), # Pass the main project root
        hfacs_level=hfacs_level,
        hfacs_confidence=hfacs_confidence,
        hfacs_reasoning=hfacs_reasoning
    )

    # Emit HFACS results to frontend
    socketio.emit('hfacs_results', {
        'hfacs_level': hfacs_level,
        'hfacs_confidence': hfacs_confidence,
        'hfacs_reasoning': hfacs_reasoning
    })

    print("\n[3/4] Generating Ground Truth Data...")
    ground_truth_data = ground_truth_gen.generate()
    # You can choose to save ground_truth_data or emit it if needed
    print("\n[4/4] Assembling final data package...")
    print("--- [COMPLETE] Simulation finished successfully. ---")

    socketio.emit('scenario_loaded', {'scenario_name': scenario_name.replace('_', ' ').title()})
    socketio.emit('simulation_metadata', {
        'max_timestamp': int(full_telemetry_df['timestamp'].max()),
        'max_altitude': int(full_telemetry_df['altitude_ft'].max() * 1.1),
        'max_airspeed': int(full_telemetry_df['airspeed_kts'].max() * 1.1)
    })
    time.sleep(1)

    triggered_anomalies = []
    flight_status = "GREEN"
    g_force_exceedance_logged = False

    for index, row in full_telemetry_df.iterrows():
        if thread_stop_event.is_set(): break

        current_time = int(row['timestamp'])
        current_g_force = round(row['vertical_g_force'], 2)

        data = {
            "timestamp": current_time,
            "phase": get_flight_phase(current_time),
            "altitude": int(row['altitude_ft']),
            "airspeed": int(row['airspeed_kts']),
            "g_force": current_g_force,
            "occ_messages": [],
            "efb_messages": [],
            "procedures": []
        }

        # Check for G-Force Exceedance
        if (current_g_force > MAX_G_FORCE_THRESHOLD or current_g_force < MIN_G_FORCE_THRESHOLD) and not g_force_exceedance_logged:
            g_force_exceedance_logged = True # Log only once per exceedance event
            anomaly_name = "G_FORCE_EXCEEDANCE"
            priority = ANOMALY_PRIORITY_MAP.get(anomaly_name, "MEDIUM")
            if priority == "HIGH": flight_status = "RED"
            elif flight_status != "RED": flight_status = "YELLOW"
            
            chart_name = scenario_name if "normal" not in scenario_name else "normal_flight"
            chart_url = f"/outputs/project_outputs/analysis_charts/telemetry_chart_{chart_name}.png"

            data['anomaly_details'] = {
                "name": anomaly_name,
                "friendly_name": ANOMALY_FRIENDLY_NAMES.get(anomaly_name, anomaly_name.replace('_', ' ')),
                "timestamp": current_time,
                "altitude": data['altitude'],
                "airspeed": data['airspeed'],
                "g_force": data['g_force'],
                "priority": priority,
                "chart_url": chart_url
            }
            data['procedures'].extend(ANOMALY_PROCEDURES.get(anomaly_name, ANOMALY_PROCEDURES["DEFAULT"]))

        newly_triggered = [a for a in all_anomalies if a[1] == current_time and a not in triggered_anomalies]
        if newly_triggered:
            triggered_anomalies.extend(newly_triggered)
            anomaly_name = newly_triggered[0][0]
            priority = ANOMALY_PRIORITY_MAP.get(anomaly_name, "MEDIUM")
            
            if priority == "HIGH": flight_status = "RED"
            elif flight_status != "RED": flight_status = "YELLOW"

            chart_name = scenario_name if "normal" not in scenario_name else "normal_flight"
            chart_url = f"/outputs/project_outputs/analysis_charts/telemetry_chart_{chart_name}.png"

            data['anomaly_details'] = {
                "name": anomaly_name,
                "friendly_name": ANOMALY_FRIENDLY_NAMES.get(anomaly_name, anomaly_name.replace('_', ' ')),
                "timestamp": current_time,
                "altitude": data['altitude'],
                "airspeed": data['airspeed'],
                "g_force": data['g_force'],
                "priority": priority,
                "chart_url": chart_url
            }
            data['procedures'].extend(ANOMALY_PROCEDURES.get(anomaly_name, ANOMALY_PROCEDURES["DEFAULT"]))

        data['flight_status'] = flight_status

        if triggered_anomalies:
            for anomaly_name, ts in triggered_anomalies:
                priority = ANOMALY_PRIORITY_MAP.get(anomaly_name, "MEDIUM")
                prefix = "CRITICAL ALERT" if priority == "HIGH" else "ALERT"
                data['occ_messages'].append(f"[{flight_id} | OCC] {prefix}: {ANOMALY_FRIENDLY_NAMES.get(anomaly_name, anomaly_name.replace('_', ' '))} at {ts}s. Engineering review required.")
                efb_map = {
                    "FLAP_ASYMMETRY": "[ECAM] F/CTL FLAP SYS FAULT",
                    "GREEN_HYDRAULIC_LOSS": "[ECAM] HYD G SYS LO PR",
                    "SENSOR_FAILURE": "[ECAM] F/CTL FLAP/SLAT FAULT",
                    "G_FORCE_ANOMALY": "[WARNING] UNUSUAL G-LOAD DETECTED",
                    "MOTOR_CURRENT_FAILURE": "[ECAM] L FLAP MOTOR FAULT",
                    "FLAP_STUCK": "[ECAM] F/CTL FLAPS LOCKED"
                }
                data['efb_messages'].append(efb_map.get(anomaly_name, f"[ALERT] {anomaly_name}"))
            data['efb_messages'].append("[ACTION] Refer to QRH")
        else:
            data['occ_messages'].append(f"[{flight_id} | OCC] All systems nominal.")
            data['efb_messages'].append("[STATUS] SYSTEMS NORMAL")

        print(f"DEBUG: Emitting data for timestamp: {current_time}")
        socketio.emit('update', data)
        socketio.sleep(1 / speed_multiplier)

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')
@app.route('/outputs/<path:path>')
def send_output_files(path):
    # FIX: The 'path' variable already contains 'project_outputs/...'.
    # We only need to specify the root 'outputs' directory to serve from.
    # The original implementation incorrectly created a duplicate path.
    outputs_dir = os.path.join(_PROJECT_ROOT, 'outputs')
    return send_from_directory(outputs_dir, path)

@socketio.on('connect')
def connect(auth=None):
    global thread
    # Simulation no longer starts automatically on connect
    # It will be triggered by a client-side event (e.g., button click)

@socketio.on('start_simulation')
def start_simulation_event():
    global thread
    print("Received start_simulation event. Starting new simulation thread.")
    # Stop any existing simulation thread
    if thread is not None and thread.is_alive():
        thread_stop_event.set()
        thread.join() # Wait for the old thread to finish
        thread_stop_event.clear()

    # Start a new simulation thread
    thread = socketio.start_background_task(run_simulation)

@socketio.on('disconnect')
def disconnect():
    print('Client disconnected', request.sid)

def open_browser():
    webbrowser.open_new_tab("http://127.0.0.1:5003")

if __name__ == '__main__':
    print("--- Starting Live Dashboard Web Server ---")
    Timer(1, open_browser).start()
    socketio.run(app, host='127.0.0.1', port=5003, debug=True)