from unittest.mock import MagicMock

import pytest
from kafka.errors import KafkaError
from neo4j.exceptions import Neo4jError
from redis.exceptions import RedisError

import experiment_monitor


# ---------------------------------------------------------------------------
# create_low_accuracy_kafka_event -- pure
# ---------------------------------------------------------------------------

def test_create_low_accuracy_kafka_event_numeric_accuracy():
    event = experiment_monitor.create_low_accuracy_kafka_event("exp-1", 42.567, "model-1", {})

    assert event["alert_name"] == "Low Experiment Accuracy"
    assert event["priority"] == "HIGH"
    assert "42.57%" in event["description"]
    assert event["event_data"] == {
        "experiment_id": "exp-1",
        "accuracy": 42.567,
        "model_id": "model-1",
    }
    assert event["UUID"].startswith("exp-hist-alert-")


def test_create_low_accuracy_kafka_event_none_accuracy():
    event = experiment_monitor.create_low_accuracy_kafka_event("exp-2", None, None, None)
    assert "N/A" in event["description"]


def test_create_low_accuracy_kafka_event_non_numeric_accuracy():
    event = experiment_monitor.create_low_accuracy_kafka_event("exp-3", "unknown", None, None)
    assert "unknown" in event["description"]


# ---------------------------------------------------------------------------
# process_completed_experiments -- needs neo4j_driver mocked as a module global
# ---------------------------------------------------------------------------

class _FakeRecord:
    def __init__(self, data):
        self._data = data

    def data(self):
        return self._data


class _FakeTxResult:
    def __init__(self, single_value=None):
        self._single_value = single_value

    def single(self):
        return self._single_value

    def consume(self):
        return MagicMock()


class _FakeTx:
    def __init__(self, run_side_effect):
        self.run = MagicMock(side_effect=run_side_effect)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _tx_run(accuracy_value=None, raise_error=None):
    def run_side_effect(query, **_kwargs):
        if raise_error is not None:
            raise raise_error
        if query == experiment_monitor.CYPHER_CALCULATE_ACCURACY:
            single = {"averageAccuracy": accuracy_value} if accuracy_value is not None else None
            return _FakeTxResult(single_value=single)
        if query == experiment_monitor.CYPHER_UPDATE_COMPLETED_EXPERIMENT:
            return _FakeTxResult()
        raise AssertionError(f"unexpected query: {query!r}")

    return run_side_effect


class _FakeSession:
    def __init__(self, records, txs):
        self._records = records
        self._txs = iter(txs)

    def run(self, query, **_kwargs):
        assert query == experiment_monitor.CYPHER_FIND_COMPLETABLE_EXPERIMENTS
        return [_FakeRecord(r) for r in self._records]

    def begin_transaction(self):
        return next(self._txs)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _driver_with_session(session):
    driver = MagicMock()
    driver.session.return_value = session
    return driver


def test_process_completed_experiments_no_driver_returns_early(monkeypatch):
    monkeypatch.setattr(experiment_monitor, "neo4j_driver", None)
    experiment_monitor.process_completed_experiments()  # must not raise


def test_process_completed_experiments_no_completable_returns_early(monkeypatch):
    session = _FakeSession(records=[], txs=[])
    session.begin_transaction = MagicMock()
    monkeypatch.setattr(experiment_monitor, "neo4j_driver", _driver_with_session(session))

    experiment_monitor.process_completed_experiments()

    session.begin_transaction.assert_not_called()


def test_process_completed_experiments_happy_path_updates_with_calculated_accuracy(monkeypatch):
    record = {"experiment_id": "exp-1", "start_time_ms": 1000, "end_time_ms": 2000}
    tx = _FakeTx(_tx_run(accuracy_value=87.654))
    session = _FakeSession(records=[record], txs=[tx])
    monkeypatch.setattr(experiment_monitor, "neo4j_driver", _driver_with_session(session))

    experiment_monitor.process_completed_experiments()

    calls = tx.run.call_args_list
    assert calls[0].args[0] == experiment_monitor.CYPHER_CALCULATE_ACCURACY
    assert calls[0].kwargs == {
        "experiment_id": "exp-1",
        "confidence_threshold": experiment_monitor.PREDICTION_CONFIDENCE_THRESHOLD,
    }
    assert calls[1].args[0] == experiment_monitor.CYPHER_UPDATE_COMPLETED_EXPERIMENT
    assert calls[1].kwargs == {
        "experiment_id": "exp-1",
        "start_time_ms": 1000,
        "end_time_ms": 2000,
        "accuracy": 87.65,
    }


def test_process_completed_experiments_missing_accuracy_defaults_to_zero(monkeypatch):
    record = {"experiment_id": "exp-1", "start_time_ms": 1000, "end_time_ms": 2000}
    tx = _FakeTx(_tx_run(accuracy_value=None))
    session = _FakeSession(records=[record], txs=[tx])
    monkeypatch.setattr(experiment_monitor, "neo4j_driver", _driver_with_session(session))

    experiment_monitor.process_completed_experiments()

    update_call = tx.run.call_args_list[1]
    assert update_call.kwargs["accuracy"] == 0.0


def test_process_completed_experiments_missing_required_fields_skipped(monkeypatch):
    record = {"experiment_id": "exp-1", "start_time_ms": None, "end_time_ms": 2000}
    session = _FakeSession(records=[record], txs=[])
    session.begin_transaction = MagicMock()
    monkeypatch.setattr(experiment_monitor, "neo4j_driver", _driver_with_session(session))

    experiment_monitor.process_completed_experiments()

    session.begin_transaction.assert_not_called()


def test_process_completed_experiments_neo4j_error_does_not_abort_loop(monkeypatch):
    record_1 = {"experiment_id": "exp-fail", "start_time_ms": 1000, "end_time_ms": 2000}
    record_2 = {"experiment_id": "exp-ok", "start_time_ms": 1000, "end_time_ms": 2000}
    failing_tx = _FakeTx(_tx_run(raise_error=Neo4jError("boom")))
    ok_tx = _FakeTx(_tx_run(accuracy_value=90.0))
    session = _FakeSession(records=[record_1, record_2], txs=[failing_tx, ok_tx])
    monkeypatch.setattr(experiment_monitor, "neo4j_driver", _driver_with_session(session))

    experiment_monitor.process_completed_experiments()  # must not raise

    assert ok_tx.run.call_args_list[1].kwargs["experiment_id"] == "exp-ok"


# ---------------------------------------------------------------------------
# check_low_accuracy_alerts -- needs redis_conn/neo4j_driver/kafka_producer mocked
# ---------------------------------------------------------------------------

class _IsoformatValue:
    def isoformat(self):
        return "2026-01-01T00:00:00+00:00"


class Duration:
    """Stand-in for neo4j.time.Duration -- the code checks type(value).__name__."""

    def __str__(self):
        return "PT1H"


def _low_accuracy_session(records):
    session = MagicMock()
    session.run.return_value = records
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    return session


def test_check_low_accuracy_alerts_missing_connections_returns_early(monkeypatch):
    monkeypatch.setattr(experiment_monitor, "redis_conn", None)
    monkeypatch.setattr(experiment_monitor, "neo4j_driver", MagicMock())
    monkeypatch.setattr(experiment_monitor, "kafka_producer", MagicMock())

    experiment_monitor.check_low_accuracy_alerts()  # must not raise


def test_check_low_accuracy_alerts_serializes_metadata_temporal_types_in_place(monkeypatch):
    metadata = {"end_datetime": _IsoformatValue(), "experiment_duration": Duration()}
    record = _FakeRecord(
        {"experiment_id": "exp-1", "accuracy": 50.0, "model_id": "model-1", "metadata": metadata}
    )
    session = _low_accuracy_session([record])
    driver = MagicMock()
    driver.session.return_value = session
    redis_conn = MagicMock()
    redis_conn.sismember.return_value = False
    kafka_producer = MagicMock()
    kafka_producer.send.return_value = MagicMock()

    monkeypatch.setattr(experiment_monitor, "neo4j_driver", driver)
    monkeypatch.setattr(experiment_monitor, "redis_conn", redis_conn)
    monkeypatch.setattr(experiment_monitor, "kafka_producer", kafka_producer)

    experiment_monitor.check_low_accuracy_alerts()

    # The temporal fields are converted to serializable strings in place on the record's
    # metadata dict. Note: create_low_accuracy_kafka_event's outgoing event_data does not
    # currently include metadata at all (it's commented out there), so this mutation isn't
    # observable in the sent Kafka payload -- only on the source dict, which is what we assert.
    assert metadata["end_datetime"] == "2026-01-01T00:00:00+00:00"
    assert metadata["experiment_duration"] == "PT1H"
    kafka_producer.send.assert_called_once()
    args, kwargs = kafka_producer.send.call_args
    assert args[0] == experiment_monitor.KAFKA_TOPIC
    assert kwargs["value"]["event_data"]["experiment_id"] == "exp-1"


def test_check_low_accuracy_alerts_skips_already_alerted(monkeypatch):
    record = _FakeRecord({"experiment_id": "exp-1", "accuracy": 50.0, "model_id": "m1", "metadata": {}})
    session = _low_accuracy_session([record])
    driver = MagicMock()
    driver.session.return_value = session
    redis_conn = MagicMock()
    redis_conn.sismember.return_value = True  # already alerted
    kafka_producer = MagicMock()

    monkeypatch.setattr(experiment_monitor, "neo4j_driver", driver)
    monkeypatch.setattr(experiment_monitor, "redis_conn", redis_conn)
    monkeypatch.setattr(experiment_monitor, "kafka_producer", kafka_producer)

    experiment_monitor.check_low_accuracy_alerts()

    kafka_producer.send.assert_not_called()


def test_check_low_accuracy_alerts_sends_and_records_new_alert(monkeypatch):
    record = _FakeRecord({"experiment_id": "exp-1", "accuracy": 50.0, "model_id": "m1", "metadata": {}})
    session = _low_accuracy_session([record])
    driver = MagicMock()
    driver.session.return_value = session
    redis_conn = MagicMock()
    redis_conn.sismember.return_value = False
    kafka_producer = MagicMock()
    kafka_producer.send.return_value = MagicMock()

    monkeypatch.setattr(experiment_monitor, "neo4j_driver", driver)
    monkeypatch.setattr(experiment_monitor, "redis_conn", redis_conn)
    monkeypatch.setattr(experiment_monitor, "kafka_producer", kafka_producer)

    experiment_monitor.check_low_accuracy_alerts()

    redis_conn.sadd.assert_called_once_with(experiment_monitor.REDIS_ALERTED_SET_KEY, "exp-1")
    redis_conn.expire.assert_called_once_with(
        experiment_monitor.REDIS_ALERTED_SET_KEY, experiment_monitor.REDIS_ALERTED_TTL_SECONDS
    )


def test_check_low_accuracy_alerts_kafka_error_on_one_does_not_abort_loop(monkeypatch):
    record_1 = _FakeRecord({"experiment_id": "exp-fail", "accuracy": 10.0, "model_id": "m1", "metadata": {}})
    record_2 = _FakeRecord({"experiment_id": "exp-ok", "accuracy": 10.0, "model_id": "m1", "metadata": {}})
    session = _low_accuracy_session([record_1, record_2])
    driver = MagicMock()
    driver.session.return_value = session
    redis_conn = MagicMock()
    redis_conn.sismember.return_value = False
    kafka_producer = MagicMock()
    kafka_producer.send.side_effect = [KafkaError("boom"), MagicMock()]

    monkeypatch.setattr(experiment_monitor, "neo4j_driver", driver)
    monkeypatch.setattr(experiment_monitor, "redis_conn", redis_conn)
    monkeypatch.setattr(experiment_monitor, "kafka_producer", kafka_producer)

    experiment_monitor.check_low_accuracy_alerts()  # must not raise

    assert kafka_producer.send.call_count == 2
    redis_conn.sadd.assert_called_once_with(experiment_monitor.REDIS_ALERTED_SET_KEY, "exp-ok")


def test_check_low_accuracy_alerts_redis_error_on_one_does_not_abort_loop(monkeypatch):
    record_1 = _FakeRecord({"experiment_id": "exp-fail", "accuracy": 10.0, "model_id": "m1", "metadata": {}})
    record_2 = _FakeRecord({"experiment_id": "exp-ok", "accuracy": 10.0, "model_id": "m1", "metadata": {}})
    session = _low_accuracy_session([record_1, record_2])
    driver = MagicMock()
    driver.session.return_value = session
    redis_conn = MagicMock()
    redis_conn.sismember.side_effect = [RedisError("boom"), False]
    kafka_producer = MagicMock()
    kafka_producer.send.return_value = MagicMock()

    monkeypatch.setattr(experiment_monitor, "neo4j_driver", driver)
    monkeypatch.setattr(experiment_monitor, "redis_conn", redis_conn)
    monkeypatch.setattr(experiment_monitor, "kafka_producer", kafka_producer)

    experiment_monitor.check_low_accuracy_alerts()  # must not raise

    assert kafka_producer.send.call_count == 1


# ---------------------------------------------------------------------------
# run_monitoring_tasks -- orchestration smoke test
# ---------------------------------------------------------------------------

def test_run_monitoring_tasks_calls_both_steps(monkeypatch):
    process_mock = MagicMock()
    check_mock = MagicMock()
    monkeypatch.setattr(experiment_monitor, "process_completed_experiments", process_mock)
    monkeypatch.setattr(experiment_monitor, "check_low_accuracy_alerts", check_mock)

    experiment_monitor.run_monitoring_tasks()

    process_mock.assert_called_once()
    check_mock.assert_called_once()
