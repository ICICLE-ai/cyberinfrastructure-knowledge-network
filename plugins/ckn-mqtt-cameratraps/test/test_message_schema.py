import time

import pytest

from message_schema import create_event_data


def test_create_event_data_builds_image_id_and_merges_fields():
    row = {"uuid": "abc-123", "action": "ingest"}

    result = create_event_data("MLEDGE_1", row, timestamp=1000)

    assert result["image_id"] == "MLEDGE_1_abc-123"
    assert result["camera_trap_id"] == "MLEDGE_1"
    assert result["timestamp"] == 1000
    assert result["action"] == "ingest"
    assert result["uuid"] == "abc-123"


def test_create_event_data_defaults_timestamp_to_now(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_700_000_000.5)

    result = create_event_data("cam", {"uuid": "u1"})

    assert result["timestamp"] == int(1_700_000_000.5 * 1000)


def test_create_event_data_explicit_timestamp_used_verbatim():
    result = create_event_data("cam", {"uuid": "u1"}, timestamp=42.0)
    assert result["timestamp"] == 42.0


def test_create_event_data_missing_uuid_raises_key_error():
    with pytest.raises(KeyError):
        create_event_data("cam", {"no_uuid_here": True})
