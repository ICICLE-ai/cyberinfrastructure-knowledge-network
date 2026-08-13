import os
import time
from unittest.mock import MagicMock

import pytest

import server_utils


# ---------------------------------------------------------------------------
# process_qoe
# ---------------------------------------------------------------------------

def test_process_qoe_weights_accuracy_and_delay_equally():
    # Note: this module's ratio is req_accuracy / probability (required over provided) -- the
    # opposite direction from ckn_inference_daemon/util.py's calculate_acc_qoe, which divides
    # provided over required. Both modules exist independently in this codebase; asserting the
    # actual formula here rather than assuming they match.
    total, acc_qoe, delay_qoe = server_utils.process_qoe(
        probability=0.6, compute_time=0.4, req_delay=0.8, req_accuracy=0.3
    )
    assert acc_qoe == pytest.approx(0.5)  # min(1.0, 0.3/0.6)
    assert delay_qoe == pytest.approx(1.0)  # min(1.0, 0.8/0.4) capped
    assert total == pytest.approx(0.5 * 0.5 + 0.5 * 1.0)


def test_process_qoe_caps_at_one():
    total, acc_qoe, delay_qoe = server_utils.process_qoe(
        probability=0.1, compute_time=1.0, req_delay=0.5, req_accuracy=0.9
    )
    assert acc_qoe == 1.0  # min(1.0, 0.9/0.1) capped
    assert delay_qoe == pytest.approx(0.5)  # min(1.0, 0.5/1.0), not capped
    assert total == pytest.approx(0.5 * 1.0 + 0.5 * 0.5)


def test_process_qoe_zero_probability_raises_zero_division():
    with pytest.raises(ZeroDivisionError):
        server_utils.process_qoe(probability=0.0, compute_time=0.1, req_delay=1.0, req_accuracy=0.5)


# ---------------------------------------------------------------------------
# check_file_extension
# ---------------------------------------------------------------------------

def test_check_file_extension_accepted():
    assert server_utils.check_file_extension("photo.JPG") is True


def test_check_file_extension_rejected():
    assert server_utils.check_file_extension("document.pdf") is False


def test_check_file_extension_no_extension():
    assert server_utils.check_file_extension("noext") is False


# ---------------------------------------------------------------------------
# save_file -- uploads to a fixed relative "./uploads" folder; use monkeypatch.chdir so
# writes land in tmp_path instead of the real repo tree.
# ---------------------------------------------------------------------------

def test_save_file_saves_and_returns_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("./uploads", exist_ok=True)

    def fake_save(path):
        with open(path, "wb") as f:
            f.write(b"fake-bytes")

    fake_file = MagicMock()
    fake_file.filename = "my photo.jpg"
    fake_file.save.side_effect = fake_save

    result_path = server_utils.save_file(fake_file)

    assert result_path == os.path.join("./uploads", "my_photo.jpg")
    assert os.path.exists(result_path)
    with open(result_path, "rb") as f:
        assert f.read() == b"fake-bytes"


# ---------------------------------------------------------------------------
# delivery_report
# ---------------------------------------------------------------------------

def test_delivery_report_success_prints_delivery_info(capsys):
    msg = MagicMock()
    msg.topic.return_value = "ckn_raw"
    msg.partition.return_value = 0
    msg.offset.return_value = 42

    server_utils.delivery_report(None, msg)

    captured = capsys.readouterr()
    assert "Message delivered to ckn_raw" in captured.out


def test_delivery_report_error_prints_failure(capsys):
    server_utils.delivery_report("broker unavailable", None)

    captured = capsys.readouterr()
    assert "Message delivery failed" in captured.out
