import io
import json
from unittest.mock import MagicMock

import pytest

# server.py constructs a real confluent_kafka.Producer at module import time. Patch
# confluent_kafka's own Producer attribute directly before the first import, so the
# constructor call in server.py never attempts a real broker connection.
import confluent_kafka

_real_producer_cls = confluent_kafka.Producer
confluent_kafka.Producer = MagicMock(name="Producer")
try:
    import server
finally:
    confluent_kafka.Producer = _real_producer_cls


@pytest.fixture(autouse=True)
def reset_server_globals(monkeypatch):
    monkeypatch.setattr(server, "producer", MagicMock())
    monkeypatch.setattr(server, "previous_deployment_id", None)
    monkeypatch.setattr(server, "deployment_id", None)
    monkeypatch.setattr(server, "device_id", None)
    server.app.config["TESTING"] = False  # keep production-like error handling


@pytest.fixture
def client():
    return server.app.test_client()


def test_home_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Welcome to CKN Edge Server!" in response.data


def test_load_model_sends_only_start_event_when_no_previous_deployment(client, monkeypatch):
    monkeypatch.setattr(server, "model_store", MagicMock())

    response = client.get("/load/?model_name=resnet152")

    assert response.status_code == 200
    assert server.producer.produce.call_count == 1
    args, kwargs = server.producer.produce.call_args
    assert args[0] == server.START_DEPLOYMENT_TOPIC
    start_event = json.loads(args[1])
    assert start_event["model_id"] == "resnet152"
    assert start_event["status"] == "RUNNING"


def test_load_model_sends_end_event_for_previous_deployment(client, monkeypatch):
    monkeypatch.setattr(server, "model_store", MagicMock())
    # send_model_change() gates the END event on the *previous* run's previous_deployment_id
    # global, not the current deployment_id -- seed that one.
    monkeypatch.setattr(server, "previous_deployment_id", "old-deployment-id")

    client.get("/load/?model_name=alexnet")

    assert server.producer.produce.call_count == 2
    end_call = server.producer.produce.call_args_list[1]
    assert end_call.args[0] == server.END_DEPLOYMENT_TOPIC
    end_event = json.loads(end_call.args[1])
    assert end_event["deployment_id"] == "old-deployment-id"
    assert end_event["status"] == "STOPPED"


def test_predict_missing_file_raises_due_to_missing_secret_key(client):
    """qoe_predict() calls flash('No file part') on this path, but server.py never sets
    app.secret_key, and Flask's flash() requires a signed session to store the message. With
    TESTING=False (matching production), this is an existing bug that surfaces as a 500
    (RuntimeError: session unavailable), not the clean redirect the code appears to intend.
    """
    response = client.post("/predict", data={})
    assert response.status_code == 500


def test_predict_empty_filename_raises_due_to_missing_secret_key(client):
    data = {"file": (io.BytesIO(b""), "")}
    response = client.post("/predict", data=data, content_type="multipart/form-data")
    assert response.status_code == 500


def test_predict_invalid_extension_raises_due_to_unbound_data(client):
    """qoe_predict() only assigns the local `data` variable inside the
    `if file and check_file_extension(...)` branch, but references it unconditionally on the
    next line. An invalid extension skips that assignment entirely, so process_w_qoe(file, data)
    hits UnboundLocalError -- an existing bug in server.py, not a test artifact. Flask (with
    TESTING=False, matching production) turns this into a 500 response rather than a clean
    validation error.
    """
    data = {"file": (io.BytesIO(b"fake"), "document.pdf")}
    response = client.post("/predict", data=data, content_type="multipart/form-data")
    assert response.status_code == 500


def test_predict_valid_file_computes_qoe_and_produces_event(client, monkeypatch):
    fake_model_store = MagicMock()
    fake_model_store.get_current_model_id.return_value = "model-1"
    monkeypatch.setattr(server, "model_store", fake_model_store)
    monkeypatch.setattr(server, "pre_process", MagicMock(return_value="preprocessed"))
    monkeypatch.setattr(server, "predict", MagicMock(return_value=("cat", 0.9)))
    monkeypatch.setattr(server, "save_file", MagicMock(return_value="/tmp/fake-upload.jpg"))

    form_data = {
        "file": (io.BytesIO(b"fake-bytes"), "photo.jpg"),
        "client_id": "device-1",
        "ground_truth": "cat",
        "delay": "1.0",
        "accuracy": "0.5",
        "service_id": "imagenet_image_classification",
    }
    response = client.post("/predict", data=form_data, content_type="multipart/form-data")

    assert response.status_code == 200
    assert response.get_json() == {"STATUS": "OK"}

    server.producer.produce.assert_called_once()
    args, kwargs = server.producer.produce.call_args
    assert args[0] == server.RAW_EVENT_TOPIC
    envelope = json.loads(args[1])
    payload = envelope["payload"]
    assert payload["prediction"] == "cat"
    assert payload["accuracy"] == 1  # ground_truth "cat" == prediction "cat"
    assert payload["device_id"] == "device-1"
    assert payload["req_delay"] == 1.0
    assert payload["req_acc"] == 0.5
