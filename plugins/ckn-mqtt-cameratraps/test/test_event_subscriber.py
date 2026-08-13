import json
from unittest.mock import MagicMock

import event_subscriber


def test_on_connect_success_subscribes():
    client = MagicMock()
    event_subscriber.on_connect(client, None, {}, 0)
    client.subscribe.assert_called_once_with(event_subscriber.EVENTS_TOPIC)


def test_on_connect_failure_does_not_subscribe(caplog):
    client = MagicMock()
    with caplog.at_level("ERROR"):
        event_subscriber.on_connect(client, None, {}, 1)
    client.subscribe.assert_not_called()
    assert "Failed to connect" in caplog.text


def test_on_message_logs_valid_payload(caplog):
    msg = MagicMock()
    msg.topic = "cameratrap/events"
    msg.payload = json.dumps({"uuid": "u1"}).encode("utf-8")

    with caplog.at_level("INFO"):
        event_subscriber.on_message(MagicMock(), None, msg)  # must not raise

    assert "Event message received" in caplog.text


def test_on_message_malformed_json_does_not_raise(caplog):
    msg = MagicMock()
    msg.topic = "cameratrap/events"
    msg.payload = b"not json"

    with caplog.at_level("ERROR"):
        event_subscriber.on_message(MagicMock(), None, msg)  # must not raise

    assert "Error processing message" in caplog.text
