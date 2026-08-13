import json
import os
from unittest.mock import MagicMock

import pytest

from oracle_daemon import OracleEventHandler
from oracle_daemon import test_ckn_broker_connection as check_ckn_broker_connection

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "events", "image_mapping_final.json")


def make_handler(file_path=FIXTURE, producer=None):
    return OracleEventHandler(
        file_path=file_path,
        producer=producer or MagicMock(),
        topic="oracle-events",
        device_id="test-device",
        experiment_id="test-experiment",
        user_id="test-user",
    )


def test_compute_iou_identical_boxes_is_one():
    handler = make_handler()
    box = [0.0, 0.0, 1.0, 1.0]
    assert handler._compute_iou(box, box) == pytest.approx(1.0)


def test_compute_iou_disjoint_boxes_is_zero():
    handler = make_handler()
    assert handler._compute_iou([0.0, 0.0, 1.0, 1.0], [2.0, 2.0, 1.0, 1.0]) == 0.0


def test_compute_iou_partial_overlap():
    handler = make_handler()
    # Two unit squares offset by 0.5 -> intersection 0.5, union 1.5
    iou = handler._compute_iou([0.0, 0.0, 1.0, 1.0], [0.5, 0.0, 1.0, 1.0])
    assert iou == pytest.approx(0.5 / 1.5)


def test_update_experiment_metrics_classification_mode_tracks_precision_recall():
    handler = make_handler()

    handler._update_experiment_metrics("animal", [{"label": "animal", "probability": 0.9}])
    handler._update_experiment_metrics("animal", [{"label": "person", "probability": 0.5}])

    assert handler.metrics["total_images"] == 2
    assert handler.metrics["true_positives"] == 1
    assert handler.metrics["false_negatives"] == 1
    assert handler.metrics["false_positives"] == 1
    assert handler.metrics["precision"] == pytest.approx(0.5)
    assert handler.metrics["recall"] == pytest.approx(0.5)


def test_update_experiment_metrics_ignores_empty_ground_truth():
    handler = make_handler()

    handler._update_experiment_metrics("empty", [])

    assert handler.metrics["total_images"] == 1
    assert handler.metrics["total_ground_truth_objects"] == 0
    assert handler.metrics["true_positives"] == 0
    assert handler.metrics["false_negatives"] == 0


def test_read_json_events_processes_fixture_and_detects_shutdown():
    producer = MagicMock()
    handler = make_handler(producer=producer)

    handler.read_json_events()

    # The fixture has 13 entries; 1 is the shutdown signal with no image_decision.
    assert producer.produce.call_count == 12
    assert handler.stop_daemon is True

    last_args, last_kwargs = producer.produce.call_args
    last_event = json.loads(last_kwargs["value"])
    assert last_event["device_id"] == "test-device"
    assert last_event["experiment_id"] == "test-experiment"
    assert last_event["total_images"] == 12


def test_read_json_events_skips_already_processed_images():
    producer = MagicMock()
    handler = make_handler(producer=producer)
    handler.read_json_events()
    producer.reset_mock()

    handler.read_json_events()

    producer.produce.assert_not_called()


def test_ckn_broker_connection_retries_then_succeeds(monkeypatch):
    attempts = {"count": 0}

    class FakeAdminClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def list_topics(self, timeout):
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise RuntimeError("not ready")
            return MagicMock()

    monkeypatch.setattr("oracle_daemon.AdminClient", FakeAdminClient)
    monkeypatch.setattr("oracle_daemon.time.sleep", lambda *_: None)

    assert check_ckn_broker_connection({}, timeout=1, num_tries=5) is True
    assert attempts["count"] == 2


def test_ckn_broker_connection_gives_up_after_max_tries(monkeypatch):
    class AlwaysFailingAdminClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def list_topics(self, timeout):
            raise RuntimeError("still not ready")

    monkeypatch.setattr("oracle_daemon.AdminClient", AlwaysFailingAdminClient)
    monkeypatch.setattr("oracle_daemon.time.sleep", lambda *_: None)

    assert check_ckn_broker_connection({}, timeout=1, num_tries=2) is False
