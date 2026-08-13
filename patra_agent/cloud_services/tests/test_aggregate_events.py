from unittest.mock import MagicMock

import pandas as pd
import pytest

import aggregate_events


# ---------------------------------------------------------------------------
# aggregate_data -- pure pandas, no mocking needed
# ---------------------------------------------------------------------------

def test_aggregate_data_groups_by_deployment_and_computes_means():
    df = pd.DataFrame(
        [
            {
                "deployment_id": "dep-1", "req_delay": 1.0, "req_acc": 0.5,
                "compute_time": 0.2, "probability": 0.9, "accuracy": 1,
                "total_qoe": 0.8, "accuracy_qoe": 0.9, "delay_qoe": 0.7,
            },
            {
                "deployment_id": "dep-1", "req_delay": 2.0, "req_acc": 0.7,
                "compute_time": 0.4, "probability": 0.7, "accuracy": 0,
                "total_qoe": 0.6, "accuracy_qoe": 0.5, "delay_qoe": 0.7,
            },
            {
                "deployment_id": "dep-2", "req_delay": 0.5, "req_acc": 0.9,
                "compute_time": 0.1, "probability": 0.95, "accuracy": 1,
                "total_qoe": 0.95, "accuracy_qoe": 0.95, "delay_qoe": 0.95,
            },
        ]
    )

    result = aggregate_events.aggregate_data(df)

    assert list(result.columns) == [
        "deployment_id", "avg_req_delay", "avg_req_acc", "avg_compute_time",
        "avg_probability", "avg_accuracy", "avg_total_qoe", "avg_accuracy_qoe",
        "avg_delay_qoe", "total_requests",
    ]

    dep1 = result[result["deployment_id"] == "dep-1"].iloc[0]
    assert dep1["avg_req_delay"] == pytest.approx(1.5)
    assert dep1["avg_req_acc"] == pytest.approx(0.6)
    assert dep1["total_requests"] == 2

    dep2 = result[result["deployment_id"] == "dep-2"].iloc[0]
    assert dep2["avg_req_delay"] == pytest.approx(0.5)
    assert dep2["total_requests"] == 1


# ---------------------------------------------------------------------------
# fetch_data_from_postgres -- mocked psycopg2 + pandas.read_sql_query
# ---------------------------------------------------------------------------

def test_fetch_data_from_postgres_queries_ckn_raw_and_closes_connection(monkeypatch):
    fake_conn = MagicMock()
    fake_connect = MagicMock(return_value=fake_conn)
    fake_df = pd.DataFrame([{"deployment_id": "dep-1"}])
    fake_read_sql = MagicMock(return_value=fake_df)

    monkeypatch.setattr(aggregate_events.psycopg2, "connect", fake_connect)
    monkeypatch.setattr(aggregate_events.pd, "read_sql_query", fake_read_sql)

    result = aggregate_events.fetch_data_from_postgres()

    fake_connect.assert_called_once_with(**aggregate_events.db_config)
    fake_read_sql.assert_called_once_with("SELECT * FROM ckn_raw", fake_conn)
    fake_conn.close.assert_called_once()
    assert result is fake_df


# ---------------------------------------------------------------------------
# produce_to_kafka -- mocked Producer (already patched at module import in conftest.py)
# ---------------------------------------------------------------------------

def test_produce_to_kafka_sends_one_message_per_row_and_flushes(monkeypatch):
    fake_producer = MagicMock()
    monkeypatch.setattr(aggregate_events, "producer", fake_producer)

    agg_df = pd.DataFrame(
        [
            {"deployment_id": "dep-1", "avg_req_delay": 1.5, "total_requests": 2},
            {"deployment_id": "dep-2", "avg_req_delay": 0.5, "total_requests": 1},
        ]
    )

    aggregate_events.produce_to_kafka(agg_df)

    assert fake_producer.produce.call_count == 2
    first_call = fake_producer.produce.call_args_list[0]
    assert first_call.args[0] == aggregate_events.AGG_TOPIC
    assert first_call.kwargs["key"] == "dep-1"
    fake_producer.flush.assert_called_once()


def test_main_calls_fetch_aggregate_and_produce_in_order(monkeypatch):
    call_order = []
    fake_df = pd.DataFrame([{"deployment_id": "dep-1"}])
    fake_agg_df = pd.DataFrame([{"deployment_id": "dep-1"}])

    monkeypatch.setattr(
        aggregate_events,
        "fetch_data_from_postgres",
        MagicMock(side_effect=lambda: (call_order.append("fetch"), fake_df)[1]),
    )
    monkeypatch.setattr(
        aggregate_events,
        "aggregate_data",
        MagicMock(side_effect=lambda df: (call_order.append("aggregate"), fake_agg_df)[1]),
    )
    monkeypatch.setattr(
        aggregate_events,
        "produce_to_kafka",
        MagicMock(side_effect=lambda df: call_order.append("produce")),
    )

    aggregate_events.main()

    assert call_order == ["fetch", "aggregate", "produce"]
