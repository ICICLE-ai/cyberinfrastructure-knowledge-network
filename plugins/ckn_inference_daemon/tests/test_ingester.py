from unittest.mock import MagicMock

import pytest

import message_broker.ingester as ingester_module


@pytest.fixture
def fake_producer_cls(monkeypatch):
    """Patch KafkaIngester's already-bound `KafkaProducer` name directly (rather than
    patching kafka.KafkaProducer before import), so this works regardless of whether
    another test module already imported message_broker.ingester first.
    """
    fake_cls = MagicMock(name="KafkaProducer")
    monkeypatch.setattr(ingester_module, "KafkaProducer", fake_cls)
    return fake_cls


def test_kafka_ingester_constructs_producer_with_bootstrap_servers(fake_producer_cls):
    kafka_ingester = ingester_module.KafkaIngester("broker:9092", "edge-inference")

    fake_producer_cls.assert_called_once()
    _args, kwargs = fake_producer_cls.call_args
    assert kwargs["bootstrap_servers"] == ["broker:9092"]
    assert kafka_ingester.topic == "edge-inference"


def test_send_request_sends_encoded_key(fake_producer_cls):
    kafka_ingester = ingester_module.KafkaIngester("broker:9092", "edge-inference")

    kafka_ingester.send_request({"a": 1}, key="server-1")

    kafka_ingester.producer.send.assert_called_once_with(
        topic="edge-inference", value={"a": 1}, key=b"server-1"
    )


def test_send_qoe_sends_without_key(fake_producer_cls):
    kafka_ingester = ingester_module.KafkaIngester("broker:9092", "edge-inference")

    kafka_ingester.send_qoe({"qoe": 0.5})

    kafka_ingester.producer.send.assert_called_once_with(
        topic="edge-inference", value={"qoe": 0.5}
    )
