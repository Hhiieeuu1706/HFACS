import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime # New import

def plot_telemetry_and_report(telemetry_data: pd.DataFrame, report: dict, output_dir: str, scenario_name: str):
    """
    Plots telemetry data and includes the final risk report as text on the plot.
    """
    fig, ax = plt.subplots(figsize=(14, 8))

    # Plot telemetry data (example: flap angles)
    ax.plot(telemetry_data['timestamp'], telemetry_data['left_flap_angle_deg'], label='Left Flap Angle', color='blue')
    
    # Conditionally plot right flap angle or faulty sensor output
    if scenario_name == 'sensor_failure':
        ax.plot(telemetry_data['timestamp'], telemetry_data['right_flap_sensor_faulty_output_deg'], label='Right Flap Sensor (Faulty)', color='red', linestyle='--')
    else:
        ax.plot(telemetry_data['timestamp'], telemetry_data['right_flap_angle_deg'], label='Right Flap Angle', color='red', linestyle='--')

    # Add anomaly trigger line if available in report
    # Assuming 'what_happened' contains timestamp like "Detected at Xs"
    try:
        anomaly_timestamp_str = report.get('what_happened', '').split('Detected at ')[1].split('s')[0]
        anomaly_timestamp = float(anomaly_timestamp_str)
        ax.axvline(x=anomaly_timestamp, color='green', linestyle=':', label='Anomaly Triggered')
    except (IndexError, ValueError):
        pass # No anomaly timestamp found or parsing failed

    ax.set_title(f'Telemetry Data for Scenario: {scenario_name}')
    ax.set_xlabel('Time (seconds)')
    ax.set_ylabel('Angle (degrees)')
    ax.legend()
    ax.grid(True)

    # Add report text as annotation
    report_text = """--- FINAL RISK REPORT ---
"""
    for key, value in report.items():
        report_text += f"{key.replace('_', ' ').title()}: {value}\n"

    # Position the text box
    props = dict(boxstyle='round,pad=0.5', fc='wheat', alpha=0.8)
    ax.text(0.02, 0.98, report_text, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=props)

    # Save the chart
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    chart_filename = f"RISK_REPORT_{scenario_name}_{timestamp}.png"
    chart_path = os.path.join(output_dir, chart_filename)
    plt.savefig(chart_path, bbox_inches='tight')
    plt.close(fig) # Close the figure to free memory
    print(f"\nSaved combined chart to: {chart_path}")