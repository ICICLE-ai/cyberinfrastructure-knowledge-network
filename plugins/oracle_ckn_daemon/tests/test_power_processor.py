import json
import os
from unittest.mock import MagicMock

import pytest

from power_processor import PowerProcessor

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "events", "power_summary_report.json")


def test_get_power_summary_flattens_plugins_and_totals():
    producer = MagicMock()
    processor = PowerProcessor(FIXTURE, producer, "cameratraps-power-summary", "exp-1")

    summary = processor.get_power_summary()

    assert summary["image_generating_plugin_cpu_power_consumption"] == 2.6314074074074068
    assert summary["power_monitor_plugin_gpu_power_consumption"] == 0.07137037037037038
    assert summary["experiment_id"] == "exp-1"
    assert summary["total_cpu_power_consumption"] == pytest.approx(
        2.6314074074074068 + 2.5915555555555554 + 2.5690384615384616
    )
    assert summary["total_gpu_power_consumption"] == pytest.approx(
        0.07603703703703703 + 0.07137037037037038 + 0.08219230769230768
    )


def test_process_summary_events_produces_flattened_event_to_kafka():
    producer = MagicMock()
    processor = PowerProcessor(FIXTURE, producer, "cameratraps-power-summary", "exp-1")

    processor.process_summary_events()

    assert producer.produce.call_count == 1
    args, kwargs = producer.produce.call_args
    assert args[0] == "cameratraps-power-summary"
    assert kwargs["key"] == "exp-1"
    payload = json.loads(kwargs["value"])
    assert payload["experiment_id"] == "exp-1"
    assert "total_cpu_power_consumption" in payload
    assert "total_gpu_power_consumption" in payload
    producer.flush.assert_called_once()


def test_process_summary_events_gives_up_when_file_never_appears():
    producer = MagicMock()
    processor = PowerProcessor(
        "/nonexistent/power_summary_report.json",
        producer,
        "cameratraps-power-summary",
        "exp-1",
        max_attempts=1,
        timeout=0,
    )

    processor.process_summary_events()

    producer.produce.assert_not_called()
