import os
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import random
from tqdm import tqdm
from typing import List, Dict
from datetime import datetime
import numpy as np # Added for numpy.arange

from src.data_simulation.data_input_simulator.main_simulator import ScenarioSimulator
from src.data_simulation.data_input_simulator.scenario_loader import ScenarioLoader
from src.data_analysis.analysis_modules.hfacs_analyzer import HFACSAnalyzer, ALL_EVIDENCE_TAGS, HFACS_RUBRIC
from src.data_analysis.analysis_modules.risk_engine import RiskTriageEngine



# --- Path Management ---
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if os.path.join(_PROJECT_ROOT, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'src'))
print(f"DEBUG: sys.path after modification: {sys.path}")

# --- Global Configuration ---
PROJECT_ID = "aviation-classifier-sa"
LOCATION = "us-central1"
CREDENTIALS_PATH = os.path.join(_PROJECT_ROOT, "config", "secrets", "gcloud_credentials.json")

def _compute_metrics(actual_tags: List[str], expected_tags: List[str]) -> Dict[str, int]:
    """
    Computes True Positives, False Positives, and False Negatives for multi-label classification.
    """
    actual_set = set(actual_tags)
    expected_set = set(expected_tags)

    tp = len(actual_set.intersection(expected_set))
    fp = len(actual_set.difference(expected_set))
    fn = len(expected_set.difference(expected_set))

    return {"tp": tp, "fp": fp, "fn": fn}

def _calculate_prf1(tp: int, fp: int, fn: int) -> Dict[str, float]:
    """
    Calculates Precision, Recall, and F1-score.
    """
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1_score": f1_score}

def _plot_overall_metrics(overall_metrics_df: pd.DataFrame, output_path: str, num_runs: int):
    """
    Creates a bar chart showing overall F1-Score, Precision, and Recall.
    """
    metrics_labels = ["Precision", "Recall", "F1-Score"]
    metrics_values = [overall_metrics_df["overall_precision"].iloc[0],
                      overall_metrics_df["overall_recall"].iloc[0],
                      overall_metrics_df["overall_f1_score"].iloc[0]]

    plt.figure(figsize=(8, 6))
    ax = plt.gca() # Get current axes
    bars = ax.bar(metrics_labels, metrics_values, color=['skyblue', 'lightcoral', 'lightgreen'])
    plt.ylim(0, 1) # Metrics are between 0 and 1
    plt.title(f"Overall HFACS Analysis Performance Metrics (N_runs={num_runs})", y=1.05) # Adjusted title position
    plt.ylabel("Score")
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    # Add numerical values on top of each bar
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + 0.02, round(yval, 2), ha='center', va='bottom')
    
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close() # Close the plot to prevent it from being displayed
    print(f"Overall performance chart saved to: {output_path}")

def _plot_hfacs_radar_chart(tag_level_metrics: Dict[str, Dict[str, int]], output_path: str, num_runs: int):
    """
    Creates a radar chart showing F1-Score, Precision, and Recall for each major HFACS Level.
    """
    hfacs_levels_agg = {
        "Level 1: Unsafe Acts": {'tp': 0, 'fp': 0, 'fn': 0},
        "Level 2: Preconditions for Unsafe Acts": {'tp': 0, 'fp': 0, 'fn': 0},
        "Level 3: Unsafe Supervision": {'tp': 0, 'fp': 0, 'fn': 0},
        "Level 4: Organizational Influences": {'tp': 0, 'fp': 0, 'fn': 0},
    }

    # Aggregate tag-level metrics to HFACS levels
    for tag, counts in tag_level_metrics.items():
        if tag in HFACS_RUBRIC:
            level_name = HFACS_RUBRIC[tag][0]
            hfacs_levels_agg[level_name]['tp'] += counts['tp']
            hfacs_levels_agg[level_name]['fp'] += counts['fp']
            hfacs_levels_agg[level_name]['fn'] += counts['fn']

    # Prepare data for plotting
    levels = list(hfacs_levels_agg.keys())
    num_levels = len(levels)

    precision_scores = []
    recall_scores = []
    f1_scores = []

    for level_full_name in levels:
        counts = hfacs_levels_agg[level_full_name]
        prf1 = _calculate_prf1(counts['tp'], counts['fp'], counts['fn'])
        precision_scores.append(prf1['precision'])
        recall_scores.append(prf1['recall'])
        f1_scores.append(prf1['f1_score'])

    # Close the plot for a circular radar chart
    precision_scores.append(precision_scores[0])
    recall_scores.append(recall_scores[0])
    f1_scores.append(f1_scores[0])

    # Calculate angle for each axis
    angles = np.linspace(0, 2 * np.pi, num_levels, endpoint=False).tolist()
    angles += angles[:1] # Complete the loop

    fig, ax = plt.subplots(figsize=(12, 8), subplot_kw=dict(polar=True)) # Widened figure

    # Plot data
    ax.plot(angles, precision_scores, linewidth=2, linestyle='solid', label='Precision', color='skyblue')
    ax.fill(angles, precision_scores, color='skyblue', alpha=0.25)

    ax.plot(angles, recall_scores, linewidth=2, linestyle='solid', label='Recall', color='lightcoral')
    ax.fill(angles, recall_scores, color='lightcoral', alpha=0.25)

    ax.plot(angles, f1_scores, linewidth=2, linestyle='solid', label='F1-Score', color='lightgreen')
    ax.fill(angles, f1_scores, color='lightgreen', alpha=0.25)

    # Set labels for each axis
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([level.replace("Level ", "L").replace(": ", "\n").replace(" for Unsafe Acts", "") for level in levels]) # Shortened labels

    # Set y-axis limits and labels
    ax.set_ylim(0, 1.0)
    ax.set_yticks(np.arange(0, 1.1, 0.2))
    ax.set_yticklabels([f'{x:.1f}' for x in np.arange(0, 1.1, 0.2)], color="gray", size=8)

    ax.set_title(f"HFACS Level-wise Performance Radar Chart (N_runs={num_runs})", y=1.08)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1)) # Adjusted legend position
    ax.grid(True)

    plt.tight_layout() # Added tight_layout
    plt.savefig(output_path)
    plt.close()
    print(f"HFACS Level performance radar chart saved to: {output_path}")

def _plot_per_scenario_metrics(all_run_results_df: pd.DataFrame, output_path: str, num_runs: int):
    """
    Creates a grouped bar chart showing F1-Score, Precision, and Recall for each scenario.
    """
    scenario_agg_metrics = {}
    for scenario_name in all_run_results_df['scenario'].unique():
        scenario_df = all_run_results_df[all_run_results_df['scenario'] == scenario_name]
        tp_sum = scenario_df['tp'].sum()
        fp_sum = scenario_df['fp'].sum()
        fn_sum = scenario_df['fn'].sum()
        scenario_agg_metrics[scenario_name] = _calculate_prf1(tp_sum, fp_sum, fn_sum)

    scenario_names = list(scenario_agg_metrics.keys())
    precision_scores = [scenario_agg_metrics[s]['precision'] for s in scenario_names]
    recall_scores = [scenario_agg_metrics[s]['recall'] for s in scenario_names]
    f1_scores = [scenario_agg_metrics[s]['f1_score'] for s in scenario_names]

    x = np.arange(len(scenario_names))
    width = 0.25

    fig, ax = plt.subplots(figsize=(14, 7))
    rects1 = ax.bar(x - width, precision_scores, width, label='Precision', color='skyblue')
    rects2 = ax.bar(x, recall_scores, width, label='Recall', color='lightcoral')
    rects3 = ax.bar(x + width, f1_scores, width, label='F1-Score', color='lightgreen')

    ax.set_ylabel('Score')
    ax.set_title(f"Performance per Scenario (N_runs={num_runs})", y=1.05) # Adjusted title position
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_names, rotation=45, ha="right")
    ax.set_ylim(0, 1)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.2f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom')
    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)

    fig.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Performance per scenario chart saved to: {output_path}")

def _plot_top_n_tag_errors(tag_level_metrics: Dict[str, Dict[str, int]], output_path: str, num_runs: int, top_n: int = 10):
    """
    Creates a horizontal stacked bar chart showing FP and FN for the top N error tags.
    """
    tag_error_data = []
    for tag, counts in tag_level_metrics.items():
        total_errors = counts['fp'] + counts['fn']
        if total_errors > 0: # Only include tags with actual errors
            tag_error_data.append({'tag': tag, 'fp': counts['fp'], 'fn': counts['fn'], 'total_errors': total_errors})

    error_df = pd.DataFrame(tag_error_data).sort_values(by='total_errors', ascending=True).tail(top_n) # Use tail to get top_n after sorting ascending

    if error_df.empty:
        print(f"No errors to plot for top {top_n} tags.")
        return

    tags = error_df['tag']
    fp_values = error_df['fp']
    fn_values = error_df['fn']
    total_values = error_df['total_errors']

    y_pos = np.arange(len(tags))

    fig, ax = plt.subplots(figsize=(10, max(6, len(tags) * 0.6))) # Adjust figure size dynamically

    # Stacked bars
    ax.barh(y_pos, fp_values, height=0.6, label='False Positives', color='orange')
    ax.barh(y_pos, fn_values, height=0.6, left=fp_values, label='False Negatives', color='red')

    ax.set_xlabel('Number of Errors')
    ax.set_title(f"Top {top_n} HFACS Tags with Most Errors (N_runs={num_runs})", y=1.02) # Adjusted title position
    ax.set_yticks(y_pos)
    ax.set_yticklabels(tags)
    ax.set_xlim(0, max(total_values) * 1.1) # Adjust x-axis limit
    ax.legend()
    ax.grid(axis='x', linestyle='--', alpha=0.7)

    # Add total error labels on each bar
    for i, total in enumerate(total_values):
        ax.text(total + (max(total_values) * 0.02), y_pos[i], str(total), va='center', ha='left', fontsize=9)

    fig.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Top {top_n} error tags stacked bar chart saved to: {output_path}")

def main():
    """
    Main function to run the batch testing script.
    """
    parser = argparse.ArgumentParser(description="Batch runner for the aviation safety analysis system.")
    parser.add_argument("--num_runs", type=int, default=200, help="Number of simulation runs.")
    parser.add_argument("--scenario", type=str, default="random", help="Scenario to test.")
    args = parser.parse_args()

    print("--- Starting Batch Runner ---")
    print(f"Number of runs: {args.num_runs}")
    print(f"Scenario: {args.scenario}")

    # --- Initialization ---
    loader = ScenarioLoader()
    hfacs_analyzer = HFACSAnalyzer(
        project_id=PROJECT_ID,
        location=LOCATION,
        credentials_path=CREDENTIALS_PATH,
        prompt_path=os.path.join(_PROJECT_ROOT, "config", "prompts", "prompts", "hfacs_analyzer_prompt.txt"),
        project_root=_PROJECT_ROOT
    )
    risk_engine = RiskTriageEngine(
        project_id=PROJECT_ID,
        location=LOCATION,
        credentials_path=CREDENTIALS_PATH
    )
    
    scenarios = loader.list_scenarios()
    all_run_results = []

    # --- Batch Processing Loop ---
    for _ in tqdm(range(args.num_runs), desc="Running batch tests"):
        scenario_name = random.choice(scenarios) if args.scenario == 'random' else args.scenario
        
        simulator = ScenarioSimulator(scenario_name=scenario_name, hfacs_analyzer=hfacs_analyzer)
        simulator.run()
        simulation_output = simulator.get_data()
        
        analysis_result, _ = risk_engine.analyze_flight(simulation_output)
        
        # Extract predicted and ground truth tags
        ai_tags = analysis_result.get("reasoning", "").split(", ") if analysis_result.get("reasoning", "") else []
        ground_truth_hfacs = simulation_output.get("ground_truth", {}).get("hfacs_analysis", {})
        expected_tags = ground_truth_hfacs.get("evidence_tags", [])

        # Compute metrics for the current run
        metrics = _compute_metrics(ai_tags, expected_tags)
        prf1 = _calculate_prf1(metrics["tp"], metrics["fp"], metrics["fn"])

        run_result = {
            "scenario": scenario_name,
            "hfacs_level_predicted": analysis_result.get("hfacs_level") ,
            "hfacs_confidence_predicted": analysis_result.get("confidence") ,
            "hfacs_reasoning_predicted": analysis_result.get("reasoning") ,
            "hfacs_ground_truth_level": ground_truth_hfacs.get("hfacs_level") ,
            "hfacs_ground_truth_tags": expected_tags,
            "tp": metrics["tp"],
            "fp": metrics["fp"],
            "fn": metrics["fn"],
            "precision": prf1["precision"],
            "recall": prf1["recall"],
            "f1_score": prf1["f1_score"],
        }
        all_run_results.append(run_result)

    # --- Save Results and Generate Plots ---
    output_dir = os.path.join(_PROJECT_ROOT, "outputs", "project_outputs", "batch_runs")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save detailed results
    detailed_df = pd.DataFrame(all_run_results)
    detailed_csv_path = os.path.join(output_dir, f"detailed_results_{timestamp}.csv")
    detailed_df.to_csv(detailed_csv_path, index=False)
    print(f"\nDetailed results saved to: {detailed_csv_path}")

    # Calculate overall metrics
    overall_tp = detailed_df['tp'].sum()
    overall_fp = detailed_df['fp'].sum()
    overall_fn = detailed_df['fn'].sum()
    overall_prf1 = _calculate_prf1(overall_tp, overall_fp, overall_fn)

    summary_metrics = {
        "total_runs": args.num_runs,
        "overall_tp": overall_tp,
        "overall_fp": overall_fp,
        "overall_fn": overall_fn,
        "overall_precision": overall_prf1["precision"],
        "overall_recall": overall_prf1["recall"],
        "overall_f1_score": overall_prf1["f1_score"],
    }
    summary_df = pd.DataFrame([summary_metrics])
    summary_csv_path = os.path.join(output_dir, f"summary_metrics_{timestamp}.csv")
    summary_df.to_csv(summary_csv_path, index=False)
    print(f"Summary metrics saved to: {summary_csv_path}")

    # Generate and save overall plot
    _plot_overall_metrics(summary_df, os.path.join(output_dir, f"overall_metrics_chart_{timestamp}.png"), args.num_runs)

    # --- Calculate and Print Tag-Level Metrics ---
    tag_level_metrics = {tag: {'tp': 0, 'fp': 0, 'fn': 0} for tag in ALL_EVIDENCE_TAGS}

    for run_result in all_run_results:
        ai_tags_set = set(run_result["hfacs_reasoning_predicted"].split(", ")) if run_result["hfacs_reasoning_predicted"] else set()
        expected_tags_set = set(run_result["hfacs_ground_truth_tags"])

        for tag in ALL_EVIDENCE_TAGS:
            is_ai_present = tag in ai_tags_set
            is_expected_present = tag in expected_tags_set

            if is_ai_present and is_expected_present:
                tag_level_metrics[tag]['tp'] += 1
            elif is_ai_present and not is_expected_present:
                tag_level_metrics[tag]['fp'] += 1
            elif not is_ai_present and is_expected_present:
                tag_level_metrics[tag]['fn'] += 1
            # True Negatives are not explicitly counted here as per the request, 
            # but would be 'not is_ai_present and not is_expected_present'

    print("\n--- Tag-Level Metrics ---")
    for tag, counts in tag_level_metrics.items():
        print(f"Tag: {tag}")
        print(f"  TP: {counts['tp']}, FP: {counts['fp']}, FN: {counts['fn']}")
        prf1 = _calculate_prf1(counts['tp'], counts['fp'], counts['fn'])
        print(f"  Precision: {prf1['precision']:.2f}, Recall: {prf1['recall']:.2f}, F1-Score: {prf1['f1_score']:.2f}")

    # Generate and save HFACS level plot
    _plot_hfacs_radar_chart(tag_level_metrics, os.path.join(output_dir, f"hfacs_level_metrics_chart_{timestamp}.png"), args.num_runs)

    # Generate and save per-scenario plot
    _plot_per_scenario_metrics(detailed_df, os.path.join(output_dir, f"per_scenario_metrics_chart_{timestamp}.png"), args.num_runs)

    # Generate and save top N error tags plot
    _plot_top_n_tag_errors(tag_level_metrics, os.path.join(output_dir, f"top_n_error_tags_chart_{timestamp}.png"), args.num_runs)

if __name__ == "__main__":
    main()


def _compute_metrics(actual_tags: List[str], expected_tags: List[str]) -> Dict[str, int]:
    """
    Computes True Positives, False Positives, and False Negatives for multi-label classification.
    """
    actual_set = set(actual_tags)
    expected_set = set(expected_tags)

    tp = len(actual_set.intersection(expected_set))
    fp = len(actual_set.difference(expected_set))
    fn = len(expected_set.difference(expected_set))

    return {"tp": tp, "fp": fp, "fn": fn}

def _calculate_prf1(tp: int, fp: int, fn: int) -> Dict[str, float]:
    """
    Calculates Precision, Recall, and F1-score.
    """
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1_score": f1_score}

def _plot_overall_metrics(overall_metrics_df: pd.DataFrame, output_path: str, num_runs: int):
    """
    Creates a bar chart showing overall F1-Score, Precision, and Recall.
    """
    metrics_labels = ["Precision", "Recall", "F1-Score"]
    metrics_values = [overall_metrics_df["overall_precision"].iloc[0],
                      overall_metrics_df["overall_recall"].iloc[0],
                      overall_metrics_df["overall_f1_score"].iloc[0]]

    plt.figure(figsize=(8, 6))
    ax = plt.gca() # Get current axes
    bars = ax.bar(metrics_labels, metrics_values, color=['skyblue', 'lightcoral', 'lightgreen'])
    plt.ylim(0, 1) # Metrics are between 0 and 1
    plt.title(f"Overall HFACS Analysis Performance Metrics (N_runs={num_runs})", y=1.05) # Adjusted title position
    plt.ylabel("Score")
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    # Add numerical values on top of each bar
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + 0.02, round(yval, 2), ha='center', va='bottom')
    
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close() # Close the plot to prevent it from being displayed
    print(f"Overall performance chart saved to: {output_path}")

def _plot_hfacs_radar_chart(tag_level_metrics: Dict[str, Dict[str, int]], output_path: str, num_runs: int):
    """
    Creates a radar chart showing F1-Score, Precision, and Recall for each major HFACS Level.
    """
    hfacs_levels_agg = {
        "Level 1: Unsafe Acts": {'tp': 0, 'fp': 0, 'fn': 0},
        "Level 2: Preconditions for Unsafe Acts": {'tp': 0, 'fp': 0, 'fn': 0},
        "Level 3: Unsafe Supervision": {'tp': 0, 'fp': 0, 'fn': 0},
        "Level 4: Organizational Influences": {'tp': 0, 'fp': 0, 'fn': 0},
    }

    # Aggregate tag-level metrics to HFACS levels
    for tag, counts in tag_level_metrics.items():
        if tag in HFACS_RUBRIC:
            level_name = HFACS_RUBRIC[tag][0]
            hfacs_levels_agg[level_name]['tp'] += counts['tp']
            hfacs_levels_agg[level_name]['fp'] += counts['fp']
            hfacs_levels_agg[level_name]['fn'] += counts['fn']

    # Prepare data for plotting
    levels = list(hfacs_levels_agg.keys())
    num_levels = len(levels)

    precision_scores = []
    recall_scores = []
    f1_scores = []

    for level_full_name in levels:
        counts = hfacs_levels_agg[level_full_name]
        prf1 = _calculate_prf1(counts['tp'], counts['fp'], counts['fn'])
        precision_scores.append(prf1['precision'])
        recall_scores.append(prf1['recall'])
        f1_scores.append(prf1['f1_score'])

    # Close the plot for a circular radar chart
    precision_scores.append(precision_scores[0])
    recall_scores.append(recall_scores[0])
    f1_scores.append(f1_scores[0])

    # Calculate angle for each axis
    angles = np.linspace(0, 2 * np.pi, num_levels, endpoint=False).tolist()
    angles += angles[:1] # Complete the loop

    fig, ax = plt.subplots(figsize=(12, 8), subplot_kw=dict(polar=True)) # Widened figure

    # Plot data
    ax.plot(angles, precision_scores, linewidth=2, linestyle='solid', label='Precision', color='skyblue')
    ax.fill(angles, precision_scores, color='skyblue', alpha=0.25)

    ax.plot(angles, recall_scores, linewidth=2, linestyle='solid', label='Recall', color='lightcoral')
    ax.fill(angles, recall_scores, color='lightcoral', alpha=0.25)

    ax.plot(angles, f1_scores, linewidth=2, linestyle='solid', label='F1-Score', color='lightgreen')
    ax.fill(angles, f1_scores, color='lightgreen', alpha=0.25)

    # Set labels for each axis
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([level.replace("Level ", "L").replace(": ", "\n").replace(" for Unsafe Acts", "") for level in levels]) # Shortened labels

    # Set y-axis limits and labels
    ax.set_ylim(0, 1.0)
    ax.set_yticks(np.arange(0, 1.1, 0.2))
    ax.set_yticklabels([f'{x:.1f}' for x in np.arange(0, 1.1, 0.2)], color="gray", size=8)

    ax.set_title(f"HFACS Level-wise Performance Radar Chart (N_runs={num_runs})", y=1.08)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1)) # Adjusted legend position
    ax.grid(True)

    plt.tight_layout() # Added tight_layout
    plt.savefig(output_path)
    plt.close()
    print(f"HFACS Level performance radar chart saved to: {output_path}")

def _plot_per_scenario_metrics(all_run_results_df: pd.DataFrame, output_path: str, num_runs: int):
    """
    Creates a grouped bar chart showing F1-Score, Precision, and Recall for each scenario.
    """
    scenario_agg_metrics = {}
    for scenario_name in all_run_results_df['scenario'].unique():
        scenario_df = all_run_results_df[all_run_results_df['scenario'] == scenario_name]
        tp_sum = scenario_df['tp'].sum()
        fp_sum = scenario_df['fp'].sum()
        fn_sum = scenario_df['fn'].sum()
        scenario_agg_metrics[scenario_name] = _calculate_prf1(tp_sum, fp_sum, fn_sum)

    scenario_names = list(scenario_agg_metrics.keys())
    precision_scores = [scenario_agg_metrics[s]['precision'] for s in scenario_names]
    recall_scores = [scenario_agg_metrics[s]['recall'] for s in scenario_names]
    f1_scores = [scenario_agg_metrics[s]['f1_score'] for s in scenario_names]

    x = np.arange(len(scenario_names))
    width = 0.25

    fig, ax = plt.subplots(figsize=(14, 7))
    rects1 = ax.bar(x - width, precision_scores, width, label='Precision', color='skyblue')
    rects2 = ax.bar(x, recall_scores, width, label='Recall', color='lightcoral')
    rects3 = ax.bar(x + width, f1_scores, width, label='F1-Score', color='lightgreen')

    ax.set_ylabel('Score')
    ax.set_title(f"Performance per Scenario (N_runs={num_runs})", y=1.05) # Adjusted title position
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_names, rotation=45, ha="right")
    ax.set_ylim(0, 1)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.2f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom')
    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)

    fig.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Performance per scenario chart saved to: {output_path}")

def _plot_top_n_tag_errors(tag_level_metrics: Dict[str, Dict[str, int]], output_path: str, num_runs: int, top_n: int = 10):
    """
    Creates a horizontal stacked bar chart showing FP and FN for the top N error tags.
    """
    tag_error_data = []
    for tag, counts in tag_level_metrics.items():
        total_errors = counts['fp'] + counts['fn']
        if total_errors > 0: # Only include tags with actual errors
            tag_error_data.append({'tag': tag, 'fp': counts['fp'], 'fn': counts['fn'], 'total_errors': total_errors})

    error_df = pd.DataFrame(tag_error_data).sort_values(by='total_errors', ascending=True).tail(top_n) # Use tail to get top_n after sorting ascending

    if error_df.empty:
        print(f"No errors to plot for top {top_n} tags.")
        return

    tags = error_df['tag']
    fp_values = error_df['fp']
    fn_values = error_df['fn']
    total_values = error_df['total_errors']

    y_pos = np.arange(len(tags))

    fig, ax = plt.subplots(figsize=(10, max(6, len(tags) * 0.6))) # Adjust figure size dynamically

    # Stacked bars
    ax.barh(y_pos, fp_values, height=0.6, label='False Positives', color='orange')
    ax.barh(y_pos, fn_values, height=0.6, left=fp_values, label='False Negatives', color='red')

    ax.set_xlabel('Number of Errors')
    ax.set_title(f"Top {top_n} HFACS Tags with Most Errors (N_runs={num_runs})", y=1.02)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(tags)
    ax.set_xlim(0, max(total_values) * 1.1) # Adjust x-axis limit
    ax.legend()
    ax.grid(axis='x', linestyle='--', alpha=0.7)

    # Add total error labels on each bar
    for i, total in enumerate(total_values):
        ax.text(total + (max(total_values) * 0.02), y_pos[i], str(total), va='center', ha='left', fontsize=9)

    fig.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Top {top_n} error tags stacked bar chart saved to: {output_path}")

def main():
    """
    Main function to run the batch testing script.
    """
    parser = argparse.ArgumentParser(description="Batch runner for the aviation safety analysis system.")
    parser.add_argument("--num_runs", type=int, default=200, help="Number of simulation runs.")
    parser.add_argument("--scenario", type=str, default="random", help="Scenario to test.")
    args = parser.parse_args()

    print("--- Starting Batch Runner ---")
    print(f"Number of runs: {args.num_runs}")
    print(f"Scenario: {args.scenario}")

    # --- Initialization ---
    loader = ScenarioLoader()
    hfacs_analyzer = HFACSAnalyzer(
        project_id=PROJECT_ID,
        location=LOCATION,
        credentials_path=CREDENTIALS_PATH,
        prompt_path="prompts/hfacs_analyzer_prompt.txt",
        project_root=_PROJECT_ROOT
    )
    risk_engine = RiskTriageEngine(
        project_id=PROJECT_ID,
        location=LOCATION,
        credentials_path=CREDENTIALS_PATH
    )
    
    scenarios = loader.list_scenarios()
    all_run_results = []

    # --- Batch Processing Loop ---
    for _ in tqdm(range(args.num_runs), desc="Running batch tests"):
        scenario_name = random.choice(scenarios) if args.scenario == 'random' else args.scenario
        
        simulator = ScenarioSimulator(scenario_name=scenario_name, hfacs_analyzer=hfacs_analyzer)
        simulator.run()
        simulation_output = simulator.get_data()
        
        analysis_result, _ = risk_engine.analyze_flight(simulation_output)
        
        # Extract predicted and ground truth tags
        ai_tags = analysis_result.get("reasoning", "").split(", ") if analysis_result.get("reasoning", "") else []
        ground_truth_hfacs = simulation_output.get("ground_truth", {}).get("hfacs_analysis", {})
        expected_tags = ground_truth_hfacs.get("evidence_tags", [])

        # Compute metrics for the current run
        metrics = _compute_metrics(ai_tags, expected_tags)
        prf1 = _calculate_prf1(metrics["tp"], metrics["fp"], metrics["fn"])

        run_result = {
            "scenario": scenario_name,
            "hfacs_level_predicted": analysis_result.get("hfacs_level"),
            "hfacs_confidence_predicted": analysis_result.get("confidence"),
            "hfacs_reasoning_predicted": analysis_result.get("reasoning"),
            "hfacs_ground_truth_level": ground_truth_hfacs.get("hfacs_level"),
            "hfacs_ground_truth_tags": expected_tags,
            "tp": metrics["tp"],
            "fp": metrics["fp"],
            "fn": metrics["fn"],
            "precision": prf1["precision"],
            "recall": prf1["recall"],
            "f1_score": prf1["f1_score"],
        }
        all_run_results.append(run_result)

    # --- Save Results and Generate Plots ---
    output_dir = os.path.join(_PROJECT_ROOT, "project_outputs", "batch_runs")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save detailed results
    detailed_df = pd.DataFrame(all_run_results)
    detailed_csv_path = os.path.join(output_dir, f"detailed_results_{timestamp}.csv")
    detailed_df.to_csv(detailed_csv_path, index=False)
    print(f"\nDetailed results saved to: {detailed_csv_path}")

    # Calculate overall metrics
    overall_tp = detailed_df['tp'].sum()
    overall_fp = detailed_df['fp'].sum()
    overall_fn = detailed_df['fn'].sum()
    overall_prf1 = _calculate_prf1(overall_tp, overall_fp, overall_fn)

    summary_metrics = {
        "total_runs": args.num_runs,
        "overall_tp": overall_tp,
        "overall_fp": overall_fp,
        "overall_fn": overall_fn,
        "overall_precision": overall_prf1["precision"],
        "overall_recall": overall_prf1["recall"],
        "overall_f1_score": overall_prf1["f1_score"],
    }
    summary_df = pd.DataFrame([summary_metrics])
    summary_csv_path = os.path.join(output_dir, f"summary_metrics_{timestamp}.csv")
    summary_df.to_csv(summary_csv_path, index=False)
    print(f"Summary metrics saved to: {summary_csv_path}")

    # Generate and save overall plot
    _plot_overall_metrics(summary_df, os.path.join(output_dir, f"overall_metrics_chart_{timestamp}.png"), args.num_runs)

    # --- Calculate and Print Tag-Level Metrics ---
    tag_level_metrics = {tag: {'tp': 0, 'fp': 0, 'fn': 0} for tag in ALL_EVIDENCE_TAGS}

    for run_result in all_run_results:
        ai_tags_set = set(run_result["hfacs_reasoning_predicted"].split(", ")) if run_result["hfacs_reasoning_predicted"] else set()
        expected_tags_set = set(run_result["hfacs_ground_truth_tags"])

        for tag in ALL_EVIDENCE_TAGS:
            is_ai_present = tag in ai_tags_set
            is_expected_present = tag in expected_tags_set

            if is_ai_present and is_expected_present:
                tag_level_metrics[tag]['tp'] += 1
            elif is_ai_present and not is_expected_present:
                tag_level_metrics[tag]['fp'] += 1
            elif not is_ai_present and is_expected_present:
                tag_level_metrics[tag]['fn'] += 1
            # True Negatives are not explicitly counted here as per the request, 
            # but would be 'not is_ai_present and not is_expected_present'

    print("\n--- Tag-Level Metrics ---")
    for tag, counts in tag_level_metrics.items():
        print(f"Tag: {tag}")
        print(f"  TP: {counts['tp']}, FP: {counts['fp']}, FN: {counts['fn']}")
        prf1 = _calculate_prf1(counts['tp'], counts['fp'], counts['fn'])
        print(f"  Precision: {prf1['precision']:.2f}, Recall: {prf1['recall']:.2f}, F1-Score: {prf1['f1_score']:.2f}")

    # Generate and save HFACS level plot
    _plot_hfacs_radar_chart(tag_level_metrics, os.path.join(output_dir, f"hfacs_level_metrics_chart_{timestamp}.png"), args.num_runs)

    # Generate and save per-scenario plot
    _plot_per_scenario_metrics(detailed_df, os.path.join(output_dir, f"per_scenario_metrics_chart_{timestamp}.png"), args.num_runs)

    # Generate and save top N error tags plot
    _plot_top_n_tag_errors(tag_level_metrics, os.path.join(output_dir, f"top_n_error_tags_chart_{timestamp}.png"), args.num_runs)

if __name__ == "__main__":
    main()