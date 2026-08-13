from datetime import datetime, timezone
from unittest.mock import MagicMock

import neo4j
import pytest

from ckn_kg import CKNKnowledgeGraph


@pytest.fixture
def kg(monkeypatch):
    fake_driver = MagicMock()
    fake_session = MagicMock()
    fake_driver.session.return_value = fake_session
    fake_graphdatabase = MagicMock()
    fake_graphdatabase.driver.return_value = fake_driver
    monkeypatch.setattr("ckn_kg.GraphDatabase", fake_graphdatabase)

    graph = CKNKnowledgeGraph("bolt://fake:7687", "neo4j", "pwd")
    return graph, fake_session, fake_graphdatabase


def test_init_constructs_driver_and_session(kg):
    graph, fake_session, fake_graphdatabase = kg
    fake_graphdatabase.driver.assert_called_once_with("bolt://fake:7687", auth=("neo4j", "pwd"))
    assert graph.session is fake_session


def test_close_closes_session(kg):
    graph, fake_session, _fake_graphdatabase = kg
    graph.close()
    fake_session.close.assert_called_once()


def _stub_transaction(fake_session, value=5):
    fake_tx = MagicMock()
    single_record = MagicMock()
    single_record.__getitem__ = lambda _self, key: value if key == "value" else None
    fake_tx.run.return_value.single.return_value = single_record
    fake_session.begin_transaction.return_value.__enter__.return_value = fake_tx
    fake_session.begin_transaction.return_value.__exit__.return_value = False
    return fake_tx


def test_get_statistics_no_filters_uses_true_clauses(kg):
    graph, fake_session, _gdb = kg
    fake_tx = _stub_transaction(fake_session)

    result = graph.get_statistics()

    assert result == {
        "average_probability": 5,
        "user_count": 5,
        "image_count": 5,
        "device_count": 5,
    }
    for call in fake_tx.run.call_args_list:
        query_text = call.args[0]
        assert "true AND true AND true AND true" in query_text


def test_get_statistics_with_device_ids_builds_in_clause(kg):
    graph, fake_session, _gdb = kg
    fake_tx = _stub_transaction(fake_session)

    graph.get_statistics(device_ids=["dev-1", "dev-2"])

    query_text = fake_tx.run.call_args_list[0].args[0]
    assert "d.device_id IN ['dev-1', 'dev-2']" in query_text


def test_get_statistics_with_date_range_builds_datetime_clause(kg):
    graph, fake_session, _gdb = kg
    fake_tx = _stub_transaction(fake_session)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)

    graph.get_statistics(date_range=(start, end))

    query_text = fake_tx.run.call_args_list[0].args[0]
    assert "p.image_scoring_timestamp >= datetime('2026-01-01T00:00:00+00:00')" in query_text
    assert "p.image_scoring_timestamp <= datetime('2026-02-01T00:00:00+00:00')" in query_text


def test_get_statistics_missing_result_defaults_to_zero(kg):
    graph, fake_session, _gdb = kg
    fake_tx = MagicMock()
    fake_result = MagicMock()
    fake_result.single.return_value = None
    fake_tx.run.return_value = fake_result
    fake_session.begin_transaction.return_value.__enter__.return_value = fake_tx
    fake_session.begin_transaction.return_value.__exit__.return_value = False

    result = graph.get_statistics()

    assert result == {
        "average_probability": 0,
        "user_count": 0,
        "image_count": 0,
        "device_count": 0,
    }


def test_fetch_distinct_users_returns_list(kg):
    graph, fake_session, _gdb = kg
    fake_session.run.return_value = [{"user_id": "alice"}, {"user_id": "bob"}]
    # neo4j Record supports __getitem__ by key; a plain dict does too.
    result = graph.fetch_distinct_users()
    assert result == ["alice", "bob"]


def test_fetch_distinct_users_exception_returns_none(kg):
    graph, fake_session, _gdb = kg
    fake_session.run.side_effect = Exception("connection lost")
    assert graph.fetch_distinct_users() is None


def test_convert_to_datetime_builds_python_datetime():
    graph = CKNKnowledgeGraph.__new__(CKNKnowledgeGraph)
    fake_neo4j_dt = MagicMock()
    fake_neo4j_dt.year, fake_neo4j_dt.month, fake_neo4j_dt.day = 2026, 3, 15
    fake_neo4j_dt.hour, fake_neo4j_dt.minute, fake_neo4j_dt.second = 10, 30, 45.123456
    fake_neo4j_dt.nanosecond = 123456000
    fake_neo4j_dt.tzinfo = timezone.utc

    result = graph.convert_to_datetime(fake_neo4j_dt)

    assert result == datetime(2026, 3, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)


def test_convert_to_native_passes_through_non_neo4j_datetime():
    graph = CKNKnowledgeGraph.__new__(CKNKnowledgeGraph)
    plain_dt = datetime(2026, 1, 1)
    assert graph.convert_to_native(plain_dt) is plain_dt


def test_convert_to_native_converts_neo4j_datetime():
    graph = CKNKnowledgeGraph.__new__(CKNKnowledgeGraph)
    fake_neo4j_dt = MagicMock(spec=neo4j.time.DateTime)
    fake_native = datetime(2026, 1, 1)
    fake_neo4j_dt.to_native.return_value = fake_native

    result = graph.convert_to_native(fake_neo4j_dt)

    assert result is fake_native


def test_get_exp_deployment_info_returns_dataframe_with_computed_times(kg):
    graph, fake_session, _gdb = kg
    fake_record = MagicMock()
    fake_record.data.return_value = {
        "Experiment": "exp-1",
        "d": {"device_id": "dev-1", "start_time": 1_700_000_000_000, "end_time": 1_700_000_100_000},
    }
    fake_session.run.return_value = [fake_record]

    result = graph.get_exp_deployment_info("exp-1")

    assert result is not None
    assert result.iloc[0]["device_id"] == "dev-1"
    assert result.iloc[0]["Experiment"] == "exp-1"
    assert "Start Time" in result.columns
    assert "End Time" in result.columns
    query_text = fake_session.run.call_args.args[0]
    assert "experiment_id: 'exp-1'" in query_text


def test_get_exp_deployment_info_no_deployments_returns_none(kg):
    graph, fake_session, _gdb = kg
    fake_session.run.return_value = []

    assert graph.get_exp_deployment_info("exp-1") is None
