"""PostgreSQL query class for CKN Camera Traps — replaces Neo4j for flat tables."""

import psycopg2
import psycopg2.extras
import pandas as pd


class CKNPostgres:
    def __init__(self, dsn: str):
        """
        Parameters
        ----------
        dsn : str
            PostgreSQL connection string, e.g.
            ``postgresql://patra:patra-dev-password@patra-postgres:5432/patra``
        """
        self.dsn = dsn

    def _conn(self):
        return psycopg2.connect(self.dsn)

    # ── users ────────────────────────────────────────────────────────────

    def fetch_distinct_users(self):
        """Return list of user_id strings that have camera trap events."""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT DISTINCT user_id FROM camera_trap_events ORDER BY user_id")
            return [row[0] for row in cur.fetchall()] or None

    # ── experiment summary for user ──────────────────────────────────────

    def get_experiment_info_for_user(self, user_id):
        query = """
            SELECT
                experiment_id AS "Experiment",
                user_id AS "User",
                model_id AS "Model",
                device_id AS "Device",
                MIN(image_receiving_timestamp) AS "Start Time",
                MAX(total_images) AS "Total Images",
                SUM(CASE WHEN image_decision = 'Save' THEN 1 ELSE 0 END) AS "Saved Images",
                MAX(precision) AS "Precision",
                MAX(recall) AS "Recall",
                MAX(f1_score) AS "F1 Score"
            FROM camera_trap_events
            WHERE user_id = %s
            GROUP BY experiment_id, user_id, model_id, device_id
            ORDER BY MIN(image_receiving_timestamp) DESC
        """
        with self._conn() as conn:
            df = pd.read_sql(query, conn, params=(user_id,))
        df.set_index("Experiment", inplace=True)
        return df

    # ── experiment list for user ─────────────────────────────────────────

    def fetch_experiments(self, user_id):
        query = """
            SELECT DISTINCT
                experiment_id,
                MIN(image_receiving_timestamp) AS timestamp,
                device_id,
                model_id
            FROM camera_trap_events
            WHERE user_id = %s
            GROUP BY experiment_id, device_id, model_id
            ORDER BY MIN(image_receiving_timestamp) DESC
        """
        with self._conn() as conn:
            df = pd.read_sql(query, conn, params=(user_id,))
        if not df.empty:
            df.set_index("timestamp", inplace=True)
        return df

    # ── experiment metrics ───────────────────────────────────────────────

    def get_experiment_metrics(self, experiment_id):
        query = """
            SELECT
                total_images, total_predictions, total_ground_truth_objects,
                true_positives, false_positives, false_negatives,
                precision, recall, f1_score, mean_iou,
                map_50, map_50_95
            FROM camera_trap_events
            WHERE experiment_id = %s
            ORDER BY image_count DESC
            LIMIT 1
        """
        with self._conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (experiment_id,))
            row = cur.fetchone()
        if not row:
            return {}
        return {k: (float(v) if v is not None else None) for k, v in row.items()}

    # ── experiment raw image data ────────────────────────────────────────

    def get_exp_info_raw(self, experiment_id):
        query = """
            SELECT
                image_name AS "Image",
                ground_truth AS "Ground Truth",
                image_scoring_timestamp AS "Score Time",
                image_receiving_timestamp AS "Ingestion Time",
                image_store_delete_time AS "Delete Time",
                model_id AS "Model",
                image_decision AS "Decision",
                flattened_scores AS "Scores"
            FROM camera_trap_events
            WHERE experiment_id = %s
            ORDER BY image_receiving_timestamp ASC
        """
        with self._conn() as conn:
            df = pd.read_sql(query, conn, params=(experiment_id,))
        if not df.empty:
            df.set_index("Ingestion Time", inplace=True)
        return df

    def get_exp_info_with_bbox(self, experiment_id):
        """Same as get_exp_info_raw for flat tables (no separate bbox data)."""
        return self.get_exp_info_raw(experiment_id)

    # ── power / deployment info ──────────────────────────────────────────

    def get_exp_deployment_info(self, experiment_id):
        query = """
            SELECT
                experiment_id AS "Experiment",
                image_generating_plugin_cpu_power_consumption,
                image_generating_plugin_gpu_power_consumption,
                power_monitor_plugin_cpu_power_consumption,
                power_monitor_plugin_gpu_power_consumption,
                image_scoring_plugin_cpu_power_consumption,
                image_scoring_plugin_gpu_power_consumption,
                total_cpu_power_consumption,
                total_gpu_power_consumption
            FROM camera_trap_power
            WHERE experiment_id = %s
        """
        with self._conn() as conn:
            df = pd.read_sql(query, conn, params=(experiment_id,))
        if df.empty:
            return None
        return df

    # ── model name (fallback) ────────────────────────────────────────────

    def get_mode_name_version(self, model_id):
        """Return model_id as-is (flat table has no separate model registry)."""
        return model_id

    # ── device type ──────────────────────────────────────────────────────

    def get_device_type(self, experiment_id):
        query = """
            SELECT DISTINCT device_id
            FROM camera_trap_events
            WHERE experiment_id = %s
            LIMIT 1
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(query, (experiment_id,))
            row = cur.fetchone()
        return row[0] if row else "Unknown"
