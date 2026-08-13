import io
from unittest.mock import MagicMock

import pytest

# server.py constructs a real KafkaIngester (which constructs a real KafkaProducer) at module
# import time. Patch message_broker.ingester's own KafkaProducer attribute directly -- not
# kafka.KafkaProducer -- so this works regardless of whether some other test module already
# imported message_broker.ingester with the real class bound into its namespace.
import message_broker.ingester as _ingester_module

_real_kafka_producer = _ingester_module.KafkaProducer
_ingester_module.KafkaProducer = MagicMock(name="KafkaProducer")
try:
    import server
finally:
    _ingester_module.KafkaProducer = _real_kafka_producer

from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "edge_pred_producer", MagicMock())

    async def fake_save_file(_file, _upload_folder):
        return "/tmp/fake-upload.jpg"

    monkeypatch.setattr(server, "save_file", fake_save_file)
    monkeypatch.setattr(server, "pre_process", MagicMock(return_value="preprocessed"))
    monkeypatch.setattr(server, "predict", MagicMock(return_value=("cat", 0.87)))
    return TestClient(server.app)


def _upload(client, filename="photo.jpg", label=None):
    files = {"file": (filename, io.BytesIO(b"fake-bytes"), "image/jpeg")}
    data = {"label": label} if label is not None else {}
    return client.post("/predict", files=files, data=data)


def test_predict_returns_prediction_and_compute_time(client):
    response = _upload(client)

    assert response.status_code == 200
    body = response.json()
    assert body["prediction"] == "cat"
    assert body["probability"] == 0.87
    assert "compute_time" in body
    assert "accuracy" not in body  # no label provided


def test_predict_with_matching_label_reports_accuracy_one(client):
    response = _upload(client, label="Cat")
    assert response.json()["accuracy"] == 1.0


def test_predict_with_mismatched_label_reports_accuracy_zero(client):
    response = _upload(client, label="dog")
    assert response.json()["accuracy"] == 0.0


def test_predict_invalid_extension_returns_400(client):
    response = _upload(client, filename="document.pdf")
    assert response.status_code == 400


def test_predict_sends_event_to_kafka_with_expected_shape(client):
    _upload(client, label="cat")

    server.edge_pred_producer.send_request.assert_called_once()
    args, kwargs = server.edge_pred_producer.send_request.call_args
    event = args[0]
    assert event["server_id"] == server.SERVER_ID
    assert event["prediction"] == "cat"
    assert event["ground_truth"] == "cat"
    assert event["accuracy"] == 1.0
    assert kwargs["key"] == server.SERVER_ID
