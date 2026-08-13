import json
import os
from queue import Queue
from unittest.mock import MagicMock

import daemon


class _ScriptedFile:
    """Fake file object driving tail_and_process_events deterministically.

    daemon.py seeks to EOF and tails for new lines, so the real file API can't be used
    directly in a test without real threading/timing. This fake scripts exactly which
    lines readline() returns, then a final "" to trigger the stop path below.
    """

    def __init__(self, lines):
        self._lines = list(lines) + [""]
        self._index = 0

    def seek(self, *_args, **_kwargs):
        pass

    def readline(self):
        line = self._lines[self._index]
        self._index += 1
        return line

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _StopTailing(Exception):
    pass


def _run_tail(monkeypatch, lines):
    fake_file = _ScriptedFile(lines)
    monkeypatch.setattr("builtins.open", lambda *a, **k: fake_file)
    # time.sleep is only called once readline() runs out of scripted lines (returns "");
    # raising there breaks the otherwise-infinite tail loop. The outer except Exception
    # catches it and logs, so the function returns normally.
    monkeypatch.setattr(daemon.time, "sleep", MagicMock(side_effect=_StopTailing))
    monkeypatch.setattr(daemon, "image_event_queue", Queue())
    mqtt_client = MagicMock()
    daemon.tail_and_process_events(mqtt_client)
    return mqtt_client


def test_detection_row_is_published(monkeypatch):
    mqtt_client = _run_tail(
        monkeypatch,
        ["DETECTION,uuid-1,[{'label': 'cat', 'probability': 0.9}]\n"],
    )

    assert mqtt_client.publish.call_count == 1
    _args, kwargs = mqtt_client.publish.call_args
    payload = json.loads(kwargs["payload"])
    assert payload["uuid"] == "uuid-1"
    assert payload["event_type"] == "DETECTION"
    assert payload["classification"] == [{"label": "cat", "probability": 0.9}]


def test_malformed_classification_is_skipped(monkeypatch):
    mqtt_client = _run_tail(monkeypatch, ["DETECTION,uuid-2,not valid python\n"])
    mqtt_client.publish.assert_not_called()


def test_storing_row_is_enqueued_not_published(monkeypatch):
    mqtt_client = _run_tail(monkeypatch, ["STORING,uuid-3,file123.jpg,ingest\n"])

    mqtt_client.publish.assert_not_called()
    assert daemon.image_event_queue.qsize() == 1
    queued = daemon.image_event_queue.get_nowait()
    assert queued["uuid"] == "uuid-3"
    assert queued["file_location"] == os.path.join(daemon.IMAGE_FOLDER_PATH, "file123.jpg")
    assert queued["action"] == "ingest"


def test_unknown_event_type_is_skipped(monkeypatch):
    mqtt_client = _run_tail(monkeypatch, ["WEIRD,x,y\n"])
    mqtt_client.publish.assert_not_called()
    assert daemon.image_event_queue.empty()


def test_incomplete_detection_row_is_skipped(monkeypatch):
    mqtt_client = _run_tail(monkeypatch, ["DETECTION,uuid-4\n"])
    mqtt_client.publish.assert_not_called()


def test_incomplete_storing_row_is_skipped(monkeypatch):
    _run_tail(monkeypatch, ["STORING,uuid-5,file.jpg\n"])
    assert daemon.image_event_queue.empty()


def test_multiple_rows_all_processed_before_stopping(monkeypatch):
    mqtt_client = _run_tail(
        monkeypatch,
        [
            "DETECTION,uuid-6,[{'label': 'dog', 'probability': 0.5}]\n",
            "STORING,uuid-7,file7.jpg,ingest\n",
        ],
    )

    assert mqtt_client.publish.call_count == 1
    assert daemon.image_event_queue.qsize() == 1


def test_start_image_worker_pool_submits_expected_worker_count(monkeypatch):
    submitted = []

    class FakeExecutor:
        def __init__(self, max_workers):
            self.max_workers = max_workers

        def submit(self, fn, *args):
            submitted.append((fn, args))

    monkeypatch.setattr(daemon, "ThreadPoolExecutor", FakeExecutor)
    mqtt_client = MagicMock()

    daemon.start_image_worker_pool(mqtt_client, num_workers=3)

    assert len(submitted) == 3
    for _fn, args in submitted:
        assert args == (daemon.image_event_queue, mqtt_client)
