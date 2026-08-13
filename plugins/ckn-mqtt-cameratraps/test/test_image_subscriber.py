import base64
import json
import os
from unittest.mock import MagicMock

import image_subscriber

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


def test_on_connect_success_subscribes():
    client = MagicMock()
    image_subscriber.on_connect(client, None, {}, 0)
    client.subscribe.assert_called_once_with(image_subscriber.IMAGES_TOPIC)


def test_on_connect_failure_does_not_subscribe(caplog):
    client = MagicMock()
    with caplog.at_level("ERROR"):
        image_subscriber.on_connect(client, None, {}, 1)
    client.subscribe.assert_not_called()


def test_on_message_saves_image_with_detected_extension():
    payload = {
        "camera_trap_id": "cam-1",
        "image_id": "img-explicit",
        "image_data": base64.b64encode(_PNG_MAGIC).decode("utf-8"),
    }
    msg = MagicMock()
    msg.payload = json.dumps(payload).encode("utf-8")

    image_subscriber.on_message(MagicMock(), None, msg)

    expected_path = os.path.join(image_subscriber.SAVED_IMAGES_DIR, "img-explicit.png")
    assert os.path.exists(expected_path)
    with open(expected_path, "rb") as f:
        assert f.read() == _PNG_MAGIC
    os.remove(expected_path)


def test_on_message_falls_back_to_filename_extension_when_undetectable():
    payload = {
        "camera_trap_id": "cam-1",
        "image_id": "img-2",
        "filename": "photo.jpg",
        "image_data": base64.b64encode(b"not-a-real-image-signature").decode("utf-8"),
    }
    msg = MagicMock()
    msg.payload = json.dumps(payload).encode("utf-8")

    image_subscriber.on_message(MagicMock(), None, msg)

    expected_path = os.path.join(image_subscriber.SAVED_IMAGES_DIR, "img-2.jpg")
    assert os.path.exists(expected_path)
    os.remove(expected_path)


def test_on_message_falls_back_to_png_when_no_extension_available():
    payload = {
        "camera_trap_id": "cam-1",
        "image_id": "img-3",
        "image_data": base64.b64encode(b"not-a-real-image-signature").decode("utf-8"),
    }
    msg = MagicMock()
    msg.payload = json.dumps(payload).encode("utf-8")

    image_subscriber.on_message(MagicMock(), None, msg)

    expected_path = os.path.join(image_subscriber.SAVED_IMAGES_DIR, "img-3.png")
    assert os.path.exists(expected_path)
    os.remove(expected_path)


def test_on_message_missing_image_data_logs_error_and_writes_nothing(caplog):
    payload = {"camera_trap_id": "cam-1", "image_id": "img-4"}
    msg = MagicMock()
    msg.payload = json.dumps(payload).encode("utf-8")

    before = set(os.listdir(image_subscriber.SAVED_IMAGES_DIR))
    with caplog.at_level("ERROR"):
        image_subscriber.on_message(MagicMock(), None, msg)
    after = set(os.listdir(image_subscriber.SAVED_IMAGES_DIR))

    assert before == after
    assert "No image data found" in caplog.text


def test_on_message_missing_image_id_generates_name(monkeypatch):
    monkeypatch.setattr(image_subscriber.time, "time", lambda: 1000.0)
    payload = {
        "camera_trap_id": "cam-9",
        "image_data": base64.b64encode(_PNG_MAGIC).decode("utf-8"),
    }
    msg = MagicMock()
    msg.payload = json.dumps(payload).encode("utf-8")

    image_subscriber.on_message(MagicMock(), None, msg)

    expected_path = os.path.join(
        image_subscriber.SAVED_IMAGES_DIR, "cam-9_image_1000000.png"
    )
    assert os.path.exists(expected_path)
    os.remove(expected_path)


def test_on_message_malformed_json_does_not_raise(caplog):
    msg = MagicMock()
    msg.payload = b"not json"
    with caplog.at_level("ERROR"):
        image_subscriber.on_message(MagicMock(), None, msg)  # must not raise
    assert "Failed to process incoming image message" in caplog.text
