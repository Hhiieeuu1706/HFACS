# file: data_input_simulator/telemetry_generator.py (v1.8 - Extended Flight)

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt

class TelemetryGenerator:
    """
    Chịu trách nhiệm tạo ra dữ liệu telemetry (time-series) cho một chuyến bay.
    """
    def __init__(self, scenario_config: dict):
        self.config = scenario_config
        self.total_flight_seconds = 135  # Increased from 120 to 135
        self.data_frequency_hz = 1

    def generate(self) -> pd.DataFrame:
        normal_profile = self._create_normal_flight_profile()
        final_data = self._inject_events(normal_profile)
        return final_data

    def _create_normal_flight_profile(self) -> pd.DataFrame:
        print("Creating normal flight profile...")
        num_points = self.total_flight_seconds * self.data_frequency_hz
        timestamps = np.arange(num_points)
        
        altitude = np.zeros(num_points)
        climb_phase = (timestamps >= 5) & (timestamps < 20)
        cruise_phase = (timestamps >= 20) & (timestamps < 90)
        descent_phase = (timestamps >= 90) & (timestamps < 125) # Descent to touchdown
        landed_phase = (timestamps >= 125) # On ground
        
        altitude[climb_phase] = np.linspace(0, 35000, np.sum(climb_phase))
        altitude[cruise_phase] = 35000
        altitude[descent_phase] = np.linspace(35000, 0, np.sum(descent_phase))
        altitude[landed_phase] = 0 # Stay at 0 altitude after landing

        flap_lever_position = np.zeros(num_points, dtype=int)
        left_flap_angle_deg = np.zeros(num_points)
        right_flap_angle_deg = np.zeros(num_points)

        # Flap schedule adjusted for the new timeline
        flap_schedule = [(95, 100, 1, 10.0), (100, 105, 2, 15.0), (105, 110, 3, 22.0), (110, 120, 4, 27.0)]

        for start_ts, end_ts, target_pos, target_angle in flap_schedule:
            lever_indices = (timestamps >= start_ts) & (timestamps < end_ts)
            flap_lever_position[lever_indices] = target_pos
            deployment_indices = (timestamps >= start_ts) & (timestamps <= end_ts)
            if np.sum(deployment_indices) > 0:
                start_angle = left_flap_angle_deg[deployment_indices.argmax() - 1] if deployment_indices.argmax() > 0 else 0.0
                current_angles = np.linspace(start_angle, target_angle, np.sum(deployment_indices))
                left_flap_angle_deg[deployment_indices] = current_angles
                right_flap_angle_deg[deployment_indices] = current_angles

        last_target_angle = flap_schedule[-1][3]
        left_flap_angle_deg[timestamps >= flap_schedule[-1][1]] = last_target_angle
        right_flap_angle_deg[timestamps >= flap_schedule[-1][1]] = last_target_angle

        df = pd.DataFrame({
            'timestamp': timestamps,
            'altitude_ft': altitude.astype(int),
            'airspeed_kts': self._simulate_airspeed(timestamps, flap_lever_position),
            'roll_angle_deg': np.random.normal(0, 0.1, num_points),
            'flap_lever_position': flap_lever_position,
            'left_flap_angle_deg': left_flap_angle_deg,
            'right_flap_angle_deg': right_flap_angle_deg,
            'green_hydraulic_pressure_psi': np.full(num_points, 3000.0),
            'autopilot_status': np.ones(num_points, dtype=int),
            'ptu_status': np.zeros(num_points, dtype=int),
            'right_flap_sensor_normal_output_deg': np.zeros(num_points),
            'right_flap_sensor_faulty_output_deg': np.zeros(num_points),
            'left_flap_sensor_faulty_output_deg': np.zeros(num_points),
            'asymmetry_sensor_delta_deg': np.zeros(num_points),
            'vertical_g_force': np.full(num_points, 1.0),
            'left_flap_motor_current': np.full(num_points, 10.0),
            'cabin_altitude_ft': np.full(num_points, 8000.0),
            'rate_of_climb_fpm': np.zeros(num_points),
            'engine_1_vibration_n1': np.random.normal(0.1, 0.02, num_points),
            'engine_1_egt_degc': np.full(num_points, 450.0),
            'ecam_alerts': [[] for _ in range(num_points)]
        })
        
        df.loc[landed_phase, 'vertical_g_force'] = 1.2 # Touchdown G-force spike
        df.loc[timestamps > 126, 'vertical_g_force'] = 1.0 # Back to normal G

        df['right_flap_sensor_normal_output_deg'] = df['right_flap_angle_deg'].copy()
        df['right_flap_sensor_faulty_output_deg'] = df['right_flap_angle_deg'].copy()
        df['left_flap_sensor_faulty_output_deg'] = df['left_flap_angle_deg'].copy()
        df['asymmetry_sensor_delta_deg'] = abs(df['left_flap_angle_deg'] - df['right_flap_angle_deg'])
        df['rate_of_climb_fpm'] = np.diff(df['altitude_ft'], prepend=0) / np.diff(df['timestamp'], prepend=1) * 60

        return df

    def _simulate_airspeed(self, timestamps: np.ndarray, flap_lever_position: np.ndarray) -> np.ndarray:
        airspeed = np.zeros_like(timestamps, dtype=float)
        climb_phase_end_ts = 20
        cruise_phase_end_ts = 90
        approach_phase_start_ts = 90
        touchdown_ts = 125
        full_stop_ts = 135

        cruise_speed = 280
        landing_speed = 140

        for i, ts in enumerate(timestamps):
            if ts < climb_phase_end_ts:
                airspeed[i] = np.interp(ts, [0, climb_phase_end_ts], [0, cruise_speed])
            elif ts < cruise_phase_end_ts:
                airspeed[i] = cruise_speed
            elif ts >= approach_phase_start_ts and ts < touchdown_ts:
                airspeed[i] = np.interp(ts, [approach_phase_start_ts, touchdown_ts], [cruise_speed, landing_speed])
            elif ts >= touchdown_ts and ts <= full_stop_ts:
                airspeed[i] = np.interp(ts, [touchdown_ts, full_stop_ts], [landing_speed, 0])
        
        airspeed[airspeed < 0] = 0
        return airspeed.astype(int)

    def _inject_events(self, df: pd.DataFrame) -> pd.DataFrame:
        events = self.config.get('telemetry_events', [])
        if not events:
            return df

        for event in events:
            start_index = -1
            trigger_condition = event.get('trigger_condition')

            if trigger_condition.startswith("flap_lever_position moves to"):
                target_pos = int(trigger_condition.split(' to ')[1])
                trigger_indices = df.index[df['flap_lever_position'] == target_pos]
                if not trigger_indices.empty:
                    start_index = trigger_indices[0]
            elif trigger_condition == "random_time_in_phase":
                valid_phases = event.get('valid_flight_phases', ['CRUISE'])
                if 'CLIMB' in valid_phases:
                    start_index = np.random.randint(5, 20)
                elif 'CRUISE' in valid_phases:
                    start_index = np.random.randint(25, 85)
                else: # Default to approach
                    start_index = np.random.randint(95, 115)
            elif trigger_condition == "cabin_altitude_exceeds_10000":
                trigger_indices = df.index[df['cabin_altitude_ft'] > 10000]
                if not trigger_indices.empty:
                    start_index = trigger_indices[0]
            
            if start_index == -1:
                print(f"  -> Warning: Trigger '{trigger_condition}' not met for event. Skipping.")
                continue

            ts = df.loc[start_index, 'timestamp']
            print(f"  -> Trigger '{trigger_condition}' met at t={ts}s. Applying event.")

            params = event.get('parameters', {})
            delay = params.get('pilot_reaction_time_seconds', {}).get('delay', 0)
            effect_start_index = min(start_index + int(delay), len(df) - 1)

            if 'ecam_alerts' in params:
                df.loc[start_index, 'ecam_alerts'].extend(params['ecam_alerts'])

            # --- Scenario-specific event injection logic ---

            # Hydraulic Failure: Green Hydraulic Pressure Decay
            if 'green_hydraulic_pressure' in params:
                decay_duration = params['green_hydraulic_pressure']['decay_to_zero_seconds']
                end_index = min(effect_start_index + decay_duration * self.data_frequency_hz, len(df) - 1)
                start_pressure = df.loc[effect_start_index, 'green_hydraulic_pressure_psi']
                decay_values = np.linspace(start_pressure, 0, end_index - effect_start_index + 1)
                df.loc[effect_start_index:end_index, 'green_hydraulic_pressure_psi'] = decay_values
                if end_index < len(df) - 1:
                    df.loc[end_index + 1:, 'green_hydraulic_pressure_psi'] = 0.0

            # Engine Maintenance Policy: Engine Spike
            if 'engine_1_vibration_n1' in params:
                df.loc[effect_start_index:, 'engine_1_vibration_n1'] = params['engine_1_vibration_n1']['spike_to_value']
            if 'engine_1_egt_degc' in params:
                df.loc[effect_start_index:, 'engine_1_egt_degc'] = params['engine_1_egt_degc']['spike_to_value']

            # Pressurization Misjudgment: Cabin Altitude Increase
            if 'cabin_altitude_ft' in params and 'rate_of_climb_fpm' in params['cabin_altitude_ft']:
                rate_fpm = params['cabin_altitude_ft']['rate_of_climb_fpm']
                rate_fps = rate_fpm / 60.0 / self.data_frequency_hz # Adjust for data frequency
                for i in range(effect_start_index, len(df)):
                    df.loc[i, 'cabin_altitude_ft'] = df.loc[i-1, 'cabin_altitude_ft'] + rate_fps

            # Sensor Failure: Faulty Flap Sensor Stuck
            if 'right_flap_sensor_faulty_output' in params:
                stuck_value = params['right_flap_sensor_faulty_output']['stuck_at_value']
                # The physical flap angle continues to change normally, but the faulty sensor output is stuck
                df.loc[effect_start_index:, 'right_flap_sensor_faulty_output_deg'] = stuck_value

            # Existing aircraft action logic (emergency descent, engine fire procedure)
            if 'aircraft_action' in params and isinstance(params['aircraft_action'], dict):
                if params['aircraft_action'].get('initiate_emergency_descent'):
                    target_alt = params['aircraft_action'].get('target_altitude_ft', 10000)
                    descent_duration = 30
                    end_index = min(effect_start_index + descent_duration, len(df) - 1)
                    start_alt = df.loc[effect_start_index, 'altitude_ft']
                    descent_values = np.linspace(start_alt, target_alt, end_index - effect_start_index + 1)
                    df.loc[effect_start_index:end_index, 'altitude_ft'] = descent_values
                    if end_index < len(df) -1:
                        df.loc[end_index + 1:, 'altitude_ft'] = target_alt
                if params['aircraft_action'].get('perform_engine_fire_procedure'):
                     df.loc[effect_start_index, 'ecam_alerts'].append("ENG 1 FIRE -> PULL/AGENT")

            # Existing flap motor current and flap jam logic
            if 'left_flap_motor_current' in params and params['left_flap_motor_current'].get('spike_and_fail'):
                df.loc[effect_start_index, 'left_flap_motor_current'] = 25.0
                df.loc[effect_start_index + 1:, 'left_flap_motor_current'] = 0.0

            if 'left_flap_angle' in params and 'jam_at_value' in params['left_flap_angle']:
                df.loc[effect_start_index:, 'left_flap_angle_deg'] = params['left_flap_angle']['jam_at_value']

        return df

def plot_scenario_telemetry(telemetry_data: pd.DataFrame, scenario_name: str, scenario_config: dict, output_dir: str,
                            hfacs_level: str = None, hfacs_confidence: int = None, hfacs_reasoning: str = None):
    """
    Generates and saves plots for a given scenario's telemetry data.
    output_dir is expected to be the project root.
    """
    scenario_plot_params = {
        'fatigue_perception_error': ['left_flap_angle_deg', 'right_flap_angle_deg'],
        'organizational_training_flaw': ['left_flap_angle_deg', 'right_flap_angle_deg', 'asymmetry_sensor_delta_deg'],
        'skill_based_error': ['airspeed_kts', 'flap_lever_position', 'vertical_g_force'],
        'supervisory_decision_error': ['left_flap_angle_deg', 'left_flap_motor_current'],
        'flap_jam': ['left_flap_angle_deg', 'right_flap_angle_deg'],
        'hydraulic_failure': ['green_hydraulic_pressure_psi', 'airspeed_kts'], # Added airspeed_kts
        'mechanical_asymmetry': ['left_flap_angle_deg', 'right_flap_angle_deg', 'asymmetry_sensor_delta_deg'],
        'sensor_failure': ['right_flap_angle_deg', 'right_flap_sensor_faulty_output_deg'],
        'pressurization_misjudgment': ['cabin_altitude_ft', 'altitude_ft', 'airspeed_kts'], # Reordered and added airspeed_kts
        'engine_maintenance_policy': ['engine_1_vibration_n1', 'engine_1_egt_degc', 'airspeed_kts'], # Added airspeed_kts
        'normal_flight': ['altitude_ft', 'airspeed_kts']
    }

    params_to_plot = scenario_plot_params.get(scenario_name, [])
    if 'airspeed_kts' not in params_to_plot and 'airspeed_kts' in telemetry_data.columns:
        params_to_plot.append('airspeed_kts')

    if not params_to_plot:
        return

    fig, ax1 = plt.subplots(figsize=(15, 10)) # Increased width and height
    ax2 = ax1.twinx()
    lines = []

    for param in params_to_plot:
        if param in telemetry_data.columns:
            if param == 'airspeed_kts':
                line, = ax2.plot(telemetry_data['timestamp'], telemetry_data[param], label=param.replace('_', ' ').title(), color='darkblue', linestyle='--')
                ax2.set_ylabel('Airspeed (kts)', color='darkblue')
                ax2.tick_params(axis='y', labelcolor='darkblue')
            else:
                line, = ax1.plot(telemetry_data['timestamp'], telemetry_data[param], label=param.replace('_', ' ').title())
                ax1.set_ylabel('Value')
            lines.append(line)

    ax1.set_title(f'Telemetry for {scenario_name.replace(" ", " ").title()} Scenario')
    ax1.set_xlabel('Time (seconds)')
    ax1.grid(True)
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')

    if hfacs_level and hfacs_confidence is not None:
        summary_text = f"HFACS Level: {hfacs_level}\nConfidence: {hfacs_confidence}%\nReasoning: {hfacs_reasoning}"
        fig.text(0.88, 0.95, summary_text, transform=fig.transFigure, fontsize=10, 
                 verticalalignment='top', horizontalalignment='right', 
                 bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5))

    charts_dir = os.path.join(output_dir, "project_outputs", "analysis_charts")
    os.makedirs(charts_dir, exist_ok=True)
    chart_path = os.path.join(charts_dir, f"telemetry_chart_{scenario_name}.png")
    
    try:
        plt.tight_layout(rect=[0, 0, 0.8, 0.9]) # Adjust plot area to make space for text
        plt.savefig(chart_path)
        print(f"  -> Saved plot to: {chart_path}")
    except Exception as e:
        print(f"  -> ERROR saving plot: {e}")
    finally:
        plt.close()

if __name__ == '__main__':
    import sys
    _CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_CURRENT_DIR)))
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    
    from data_input_simulator.scenario_loader import ScenarioLoader

    try:
        loader = ScenarioLoader()
        scenarios_to_test = [
            'normal_flight',
            'fatigue_perception_error',
            'organizational_training_flaw',
            'skill_based_error',
            'supervisory_decision_error',
            'flap_jam',
            'hydraulic_failure',
            'mechanical_asymmetry',
            'sensor_failure',
            'pressurization_misjudgment',
            'engine_maintenance_policy'
        ]

        for scenario_name in scenarios_to_test:
            try:
                scenario_config = loader.load(scenario_name)
                telemetry_gen = TelemetryGenerator(scenario_config)
                telemetry_data = telemetry_gen.generate()
                plot_scenario_telemetry(telemetry_data, scenario_name, scenario_config, _PROJECT_ROOT)
            except FileNotFoundError:
                print(f"  -> ERROR: Scenario file '{scenario_name}.json' not found. Skipping.")
            except Exception as e:
                print(f"  -> ERROR processing scenario '{scenario_name}': {e}")
                import traceback
                traceback.print_exc()

    except Exception:
        import traceback
        traceback.print_exc()
