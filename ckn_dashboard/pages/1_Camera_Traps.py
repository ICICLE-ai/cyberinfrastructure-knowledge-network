import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ckn_pg import CKNPostgres

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://patra:patra-dev-password@localhost:5432/patra')

pg = CKNPostgres(DATABASE_URL)

st.set_page_config(
    page_title="Camera Traps Experiments",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        'About': 'Camera Traps Experiment Dashboard'
    }
)
st.markdown(
    """
<style>
[data-testid="stMetricValue"] {
    font-size: 20px;
}
[data-testid="stMetricLabel"] {
    font-size: 16px !important;
    font-weight: 600 !important;
}
[data-testid="stMetricDelta"] {
    font-size: 14px !important;
}
</style>
""",
    unsafe_allow_html=True,
)

st.header("Camera Traps Experiments")

users = pg.fetch_distinct_users()
if not users:
    st.write("No camera trap data found in PostgreSQL.")
    st.stop()

def get_experiment_indicators(experiment_id, experiment_df, model_id):
    selected_experiment = experiment_df.loc[experiment_id]
    start_time = selected_experiment['Start Time']
    if pd.isna(start_time):
        date_str, time_str = "N/A", "N/A"
    else:
        date_str = start_time.strftime("%Y-%m-%d")
        time_str = start_time.strftime("%H:%M:%S")

    model_name = pg.get_mode_name_version(model_id)

    device_info = pg.get_device_type(experiment_id)

    return date_str, time_str, model_name, device_info

def _is_number(value):
    return isinstance(value, (int, float))


def _fmt_dec(value, decimals=4):
    return f"{value:.{decimals}f}" if _is_number(value) else "-"


def _progress_if_number(value):
    if _is_number(value):
        v = max(0.0, min(1.0, float(value)))
        st.progress(v)


def get_power_info(deployment_info):
    if deployment_info is None:
        return None, None, None, None, None

    total_cpu = round(float(deployment_info['total_cpu_power_consumption'].iloc[0]), 3)
    total_gpu = round(float(deployment_info['total_gpu_power_consumption'].iloc[0]), 3)

    # Build plugin breakdown table
    plugins = []
    plugin_cols = [
        ('image_generating_plugin', 'Image generating'),
        ('power_monitor_plugin', 'Power monitor'),
        ('image_scoring_plugin', 'Image scoring'),
    ]
    for col_prefix, name in plugin_cols:
        cpu_col = f"{col_prefix}_cpu_power_consumption"
        gpu_col = f"{col_prefix}_gpu_power_consumption"
        if cpu_col in deployment_info.columns:
            plugins.append({
                "Plugin Name": name,
                "Total CPU Consumption (W)": round(float(deployment_info[cpu_col].iloc[0]), 3),
                "Total GPU Consumption (W)": round(float(deployment_info[gpu_col].iloc[0]), 3),
            })
    plugins_df = pd.DataFrame(plugins)
    if not plugins_df.empty:
        plugins_df.set_index("Plugin Name", inplace=True)

    return None, None, total_cpu, total_gpu, plugins_df


col1 = st.container()

# Display DataFrames in columns
with col1:
    selected_user = st.selectbox("Select User", users)

if selected_user:
    with col1:
        exp_summary_user = pg.get_experiment_info_for_user(selected_user)

        default_rows = 3
        height = min(50 * default_rows, 50 * len(exp_summary_user))
        st.dataframe(exp_summary_user, use_container_width=True, height=height)

if selected_user:
    experiments = pg.fetch_experiments(selected_user)
    with col1:
        selected_experiment = st.selectbox(f"Select Experiment performed by {selected_user}", experiments['experiment_id'])

# Load user-specific data
if selected_experiment:
    with col1:
        experiment_info = pg.get_exp_info_raw(selected_experiment)

        db_metrics = pg.get_experiment_metrics(selected_experiment) or {}

        dataset_metrics = {
            "total_images": db_metrics.get("total_images"),
            "total_ground_truth_objects": db_metrics.get("total_ground_truth_objects"),
            "total_predictions": db_metrics.get("total_predictions"),
            "true_positives": db_metrics.get("true_positives"),
            "false_positives": db_metrics.get("false_positives"),
            "false_negatives": db_metrics.get("false_negatives"),
            "mean_iou": db_metrics.get("mean_iou"),
            "precision": db_metrics.get("precision"),
            "recall": db_metrics.get("recall"),
            "f1_score": db_metrics.get("f1_score"),
            "map_50": db_metrics.get("map_50"),
            "map_50_95": db_metrics.get("map_50_95"),
        }

        model_id = experiment_info['Model'].iloc[0]
        experiment_info = experiment_info.drop(columns=['Model'])
        if 'Delete Time' in experiment_info.columns:
            experiment_info = experiment_info.drop(columns=['Delete Time'])

        date_str, time_str, model_name, device_info = get_experiment_indicators(selected_experiment, exp_summary_user, model_id)

        deployment_info = pg.get_exp_deployment_info(selected_experiment)
        _, _, total_cpu, total_gpu, plugins_df = get_power_info(deployment_info)

        columns = st.columns(3)
        columns[0].metric(label="Start Time", value=f"{date_str} {time_str}")
        columns[1].metric(label="Model", value=model_name)
        columns[2].metric(label="Device", value=device_info)


        # Detection Metrics (Collapsible)
        if dataset_metrics["true_positives"] and dataset_metrics["total_images"] and dataset_metrics["total_ground_truth_objects"] and dataset_metrics["total_predictions"] is not None:
            with st.expander("Detection Metrics", expanded=True):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        label="Total Images",
                        value=str(dataset_metrics["total_images"]) if dataset_metrics["total_images"] is not None else "-",
                        help="Number of images processed in this experiment"
                    )

                with col2:
                    st.metric(
                        label="Ground Truth Objects",
                        value=str(dataset_metrics["total_ground_truth_objects"]) if dataset_metrics["total_ground_truth_objects"] is not None else "-",
                        help="Number of objects in ground truth annotations"
                    )

                with col3:
                    st.metric(
                        label="Total Predictions",
                        value=str(dataset_metrics["total_predictions"]) if dataset_metrics["total_predictions"] is not None else "-",
                        help="Total number of predictions made by the model"
                    )

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        label="True Positives",
                        value=str(dataset_metrics["true_positives"]) if dataset_metrics["true_positives"] is not None else "-",
                        help="Correctly detected objects (IoU > 0.5)"
                    )

                with col2:
                    st.metric(
                        label="False Positives",
                        value=str(dataset_metrics["false_positives"]) if dataset_metrics["false_positives"] is not None else "-",
                        help="Incorrect detections"
                    )

                with col3:
                    st.metric(
                        label="False Negatives",
                        value=str(dataset_metrics["false_negatives"]) if dataset_metrics["false_negatives"] is not None else "-",
                        help="Missed ground truth objects"
                    )


        # Precision & Recall (Collapsible)
        if dataset_metrics["precision"] and dataset_metrics["recall"] and dataset_metrics["f1_score"] is not None:
            with st.expander("Precision & Recall", expanded=False):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        label="Precision",
                        value=_fmt_dec(dataset_metrics.get('precision'), 4),
                        help="TP / (TP + FP) - Accuracy of positive predictions"
                    )
                    _progress_if_number(dataset_metrics.get('precision'))

                with col2:
                    st.metric(
                        label="Recall",
                        value=_fmt_dec(dataset_metrics.get('recall'), 4),
                        help="TP / (TP + FN) - Ability to find all positive instances"
                    )
                    _progress_if_number(dataset_metrics.get('recall'))

                with col3:
                    st.metric(
                        label="F1 Score",
                        value=_fmt_dec(dataset_metrics.get('f1_score'), 4),
                        help="Harmonic mean of precision and recall"
                    )
                    _progress_if_number(dataset_metrics.get('f1_score'))

        # mAP Metrics (Collapsible)
        if dataset_metrics["map_50"] and dataset_metrics["map_50_95"] is not None:
                with st.expander("mAP Metrics", expanded=False):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.metric(
                            label="mAP@0.5",
                            value=_fmt_dec(dataset_metrics.get('map_50'), 3),
                            help="Mean Average Precision at IoU threshold 0.5"
                        )
                        _progress_if_number(dataset_metrics.get('map_50'))

                    with col2:
                        st.metric(
                            label="mAP@[0.5:0.95]",
                            value=_fmt_dec(dataset_metrics.get('map_50_95'), 3),
                            help="Mean Average Precision across IoU thresholds 0.5 to 0.95"
                        )
                        _progress_if_number(dataset_metrics.get('map_50_95'))

        st.markdown("Experiment Raw Data")

        st.dataframe(experiment_info, use_container_width=True)

        if plugins_df is not None and not plugins_df.empty:
            st.markdown("#### Power Information")
            col1, col2 = st.columns(2)
            col1.metric(label="Total CPU Consumption (W)", value=total_cpu)
            col2.metric(label="Total GPU Consumption (W)", value=total_gpu)
            st.dataframe(plugins_df, use_container_width=True)

        else:
            st.write("No power information available for this experiment.")
