import asyncio
from unittest.mock import MagicMock

import pytest

import util


# ---------------------------------------------------------------------------
# get_model_id
# ---------------------------------------------------------------------------

def test_get_model_id_url_with_id_param():
    assert util.get_model_id("https://example.com/models?id=abc123") == "abc123-model"


def test_get_model_id_url_without_id_param_returns_input_unchanged():
    url = "https://example.com/models?other=xyz"
    assert util.get_model_id(url) == url


def test_get_model_id_plain_string_returned_unchanged():
    assert util.get_model_id("just-a-model-name") == "just-a-model-name"


# ---------------------------------------------------------------------------
# check_file_extension
# ---------------------------------------------------------------------------

def test_check_file_extension_accepted():
    assert util.check_file_extension("photo.JPG", {"jpg", "png"}) is True


def test_check_file_extension_rejected():
    assert util.check_file_extension("document.pdf", {"jpg", "png"}) is False


def test_check_file_extension_no_extension():
    assert util.check_file_extension("noext", {"jpg", "png"}) is False


# ---------------------------------------------------------------------------
# calculate_acc_qoe / calculate_delay_qoe / process_qoe
# ---------------------------------------------------------------------------

def test_calculate_acc_qoe_caps_at_one():
    assert util.calculate_acc_qoe(req_acc=0.5, provided_acc=0.9) == 1.0


def test_calculate_acc_qoe_below_cap():
    assert util.calculate_acc_qoe(req_acc=0.8, provided_acc=0.4) == pytest.approx(0.5)


def test_calculate_delay_qoe_caps_at_one():
    assert util.calculate_delay_qoe(req_delay=1.0, provided_delay=0.2) == 1.0


def test_calculate_acc_qoe_zero_required_raises_zero_division():
    with pytest.raises(ZeroDivisionError):
        util.calculate_acc_qoe(req_acc=0.0, provided_acc=0.5)


def test_process_qoe_weights_accuracy_and_delay_equally():
    total, acc_qoe, delay_qoe = util.process_qoe(
        probability=0.4, compute_time=0.4, req_delay=0.8, req_accuracy=0.8
    )
    assert acc_qoe == pytest.approx(0.5)
    assert delay_qoe == pytest.approx(1.0)
    assert total == pytest.approx(0.5 * 0.5 + 0.5 * 1.0)


# ---------------------------------------------------------------------------
# send_model_change / send_summary_event
# ---------------------------------------------------------------------------

def test_send_model_change_sends_expected_payload():
    producer = MagicMock()
    util.send_model_change("new-model", producer, "server-1")
    producer.send_request.assert_called_once_with(
        {"server_id": "server-1", "model": "new-model"}, key="server-1"
    )


def test_send_summary_event_builds_expected_event_and_sends():
    producer = MagicMock()
    data = {
        "server_id": "s1",
        "service_id": "svc1",
        "client_id": "c1",
        "accuracy": "0.8",
        "delay": "0.5",
        "added_time": 12345,
    }

    event = util.send_summary_event(
        data,
        qoe=0.75,
        compute_time=0.3,
        probability=0.9,
        prediction="cat",
        acc_qoe=0.8,
        delay_qoe=0.7,
        model_name="resnet",
        producer=producer,
    )

    assert event["server_id"] == "s1"
    assert event["prediction"] == "cat"
    assert event["req_acc"] == 0.8
    assert event["req_delay"] == 0.5
    assert event["model"] == "resnet"
    producer.send_request.assert_called_once_with(event, key="ckn-edge")


# ---------------------------------------------------------------------------
# write_perf_file
# ---------------------------------------------------------------------------

def test_write_perf_file_appends_rows_without_header(tmp_path):
    perf_file = tmp_path / "perf.csv"
    row1 = [{"compute_time": 0.1, "pub_time": 0.2, "dnn_time": 0.05}]
    row2 = [{"compute_time": 0.3, "pub_time": 0.4, "dnn_time": 0.06}]

    util.write_perf_file(row1, str(perf_file))
    util.write_perf_file(row2, str(perf_file))

    lines = perf_file.read_text().strip().splitlines()
    # No header is ever written by this function (DictWriter.writeheader() is never called) --
    # this is the module's existing, documented-as-is behavior, not something this test adds.
    assert len(lines) == 2
    assert lines[0] == "0.1,0.2,0.05"
    assert lines[1] == "0.3,0.4,0.06"


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------

def test_window_defaults():
    window = util.Window()
    assert window.total_acc == 0.0
    assert window.total_delay == 0.0
    assert window.num_requests == 0
    assert window.avg_acc == 0.0
    assert window.avg_delay == 0.0
    assert window.model_name == "SqueezeNet"


# ---------------------------------------------------------------------------
# save_file
# ---------------------------------------------------------------------------

class _FakeUploadFile:
    def __init__(self, filename, contents):
        self.filename = filename
        self._contents = contents

    async def read(self):
        return self._contents


def test_save_file_writes_contents_and_returns_path(tmp_path):
    upload_folder = tmp_path / "uploads"
    fake_file = _FakeUploadFile("my photo.jpg", b"fake-bytes")

    result_path = asyncio.run(util.save_file(fake_file, str(upload_folder)))

    assert result_path == str(upload_folder / "my_photo.jpg")
    assert (upload_folder / "my_photo.jpg").read_bytes() == b"fake-bytes"
