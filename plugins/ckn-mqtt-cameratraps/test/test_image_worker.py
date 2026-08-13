import base64
import json
from queue import Queue
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt

import image_worker


def test_create_image_payload_includes_encoded_image_and_schema_fields(monkeypatch):
    monkeypatch.setattr(image_worker, "CAMERA_TRAP_ID", "cam-1")
    monkeypatch.setattr(image_worker.time, "time", lambda: 1000.0)

    payload = image_worker.create_image_payload({"uuid": "u1"}, "base64data==")

    assert payload["image_data"] == "base64data=="
    assert payload["camera_trap_id"] == "cam-1"
    assert payload["image_id"] == "cam-1_u1"


def test_process_image_event_publishes_success(tmp_path):
    image_file = tmp_path / "img.jpg"
    image_file.write_bytes(b"fake-image-bytes")

    mqtt_client = MagicMock()
    result = MagicMock()
    result.rc = mqtt.MQTT_ERR_SUCCESS
    mqtt_client.publish.return_value = result

    event = {"uuid": "u1", "file_location": str(image_file)}
    image_worker.process_image_event(event, mqtt_client)

    assert mqtt_client.publish.call_count == 1
    args, kwargs = mqtt_client.publish.call_args
    assert args[0] == image_worker.IMAGES_TOPIC
    sent_payload = json.loads(kwargs["payload"])
    assert sent_payload["image_data"] == base64.b64encode(b"fake-image-bytes").decode("utf-8")
    assert kwargs["qos"] == 1
    result.wait_for_publish.assert_called_once()


def test_process_image_event_logs_failure_rc(tmp_path, caplog):
    image_file = tmp_path / "img.jpg"
    image_file.write_bytes(b"data")

    mqtt_client = MagicMock()
    result = MagicMock()
    result.rc = mqtt.MQTT_ERR_NO_CONN
    mqtt_client.publish.return_value = result

    event = {"uuid": "u1", "file_location": str(image_file)}
    with caplog.at_level("ERROR"):
        image_worker.process_image_event(event, mqtt_client)

    assert "Failed to publish image" in caplog.text


def test_process_image_event_bad_file_path_does_not_raise(caplog):
    mqtt_client = MagicMock()
    event = {"uuid": "u1", "file_location": "/nonexistent/path.jpg"}

    with caplog.at_level("ERROR"):
        image_worker.process_image_event(event, mqtt_client)  # must not raise

    mqtt_client.publish.assert_not_called()


def test_image_worker_loop_processes_until_sentinel():
    q = Queue()
    q.put({"uuid": "u1", "file_location": "/nonexistent.jpg"})
    q.put(None)

    mqtt_client = MagicMock()
    with patch.object(image_worker, "process_image_event") as mock_process:
        image_worker.image_worker(q, mqtt_client)

    mock_process.assert_called_once_with(
        {"uuid": "u1", "file_location": "/nonexistent.jpg"}, mqtt_client
    )
    # task_done() is only called for the real event, not for the None sentinel that
    # breaks the loop -- this is the module's existing behavior, not a test artifact.
    assert q.unfinished_tasks == 1
