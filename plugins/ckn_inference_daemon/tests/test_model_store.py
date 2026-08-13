import json
from unittest.mock import MagicMock, patch

import pytest

from models.model_store import ModelStore


def _store_without_init_side_effects():
    """ModelStore.__init__ runs real logic depending on env vars; construct an instance
    without calling __init__ so we can unit test its methods in isolation.
    """
    return ModelStore.__new__(ModelStore)


# ---------------------------------------------------------------------------
# get_huggingface_repo_and_filename -- pure
# ---------------------------------------------------------------------------

def test_get_huggingface_repo_and_filename_parses_url():
    store = _store_without_init_side_effects()
    repo, filename = store.get_huggingface_repo_and_filename(
        "https://huggingface.co/xxx/yyy/blob/main/googlenet.pt"
    )
    assert repo == "xxx/yyy"
    assert filename == "googlenet.pt"


def test_get_huggingface_repo_and_filename_too_short_raises():
    store = _store_without_init_side_effects()
    with pytest.raises(ValueError):
        store.get_huggingface_repo_and_filename("https://huggingface.co/onlyonepart")


# ---------------------------------------------------------------------------
# get_model_location -- pure
# ---------------------------------------------------------------------------

def test_get_model_location_extracts_location():
    store = _store_without_init_side_effects()
    payload = json.dumps({"ai_model": {"location": "https://huggingface.co/x/y/blob/main/m.pt"}})
    assert store.get_model_location(payload) == "https://huggingface.co/x/y/blob/main/m.pt"


def test_get_model_location_missing_location_raises_value_error():
    store = _store_without_init_side_effects()
    payload = json.dumps({"ai_model": {}})
    with pytest.raises(ValueError):
        store.get_model_location(payload)


def test_get_model_location_invalid_json_raises_value_error():
    store = _store_without_init_side_effects()
    with pytest.raises(ValueError):
        store.get_model_location("not json")


# ---------------------------------------------------------------------------
# get_model -- mocked requests.get
# ---------------------------------------------------------------------------

def test_get_model_with_real_requests_json_dict_raises_type_error(monkeypatch):
    """get_model() passes response.json() (a dict, per normal `requests` behavior) straight
    into get_model_location(), which immediately calls json.loads() on it expecting a raw
    JSON string. Against any real Patra server response this crashes with TypeError before
    reaching the location field at all -- this is an existing bug in model_store.py, not a
    test artifact. Locking in the actual current behavior here rather than the presumably
    intended one, so a fix is a deliberate choice, not something this test suite masks.
    """
    store = _store_without_init_side_effects()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "ai_model": {"location": "https://huggingface.co/a/b/blob/main/model.pt"}
    }
    monkeypatch.setattr(
        "models.model_store.requests.get", MagicMock(return_value=response)
    )

    with pytest.raises(TypeError):
        store.get_model("http://patra/models?id=1")


def test_get_model_succeeds_if_response_json_were_a_string(monkeypatch):
    """Documents the path get_model_location() actually supports: a raw JSON string. This
    only happens today if response.json() itself returns a string (e.g. a double-encoded
    payload) -- not the normal dict shape `requests` produces.
    """
    store = _store_without_init_side_effects()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = (
        '{"ai_model": {"location": "https://huggingface.co/a/b/blob/main/model.pt"}}'
    )
    monkeypatch.setattr(
        "models.model_store.requests.get", MagicMock(return_value=response)
    )

    repo, filename = store.get_model("http://patra/models?id=1")

    assert repo == "a/b"
    assert filename == "model.pt"


def test_get_model_non_200_raises(monkeypatch):
    store = _store_without_init_side_effects()
    response = MagicMock()
    response.status_code = 404
    monkeypatch.setattr(
        "models.model_store.requests.get", MagicMock(return_value=response)
    )

    with pytest.raises(Exception, match="Failed to get model info"):
        store.get_model("http://patra/models?id=1")


# ---------------------------------------------------------------------------
# load_model / change_model -- mocked hf_hub_download + torch.load
# ---------------------------------------------------------------------------

def test_load_model_pt_downloads_and_loads(monkeypatch):
    store = _store_without_init_side_effects()
    store.loader_type = "pt"

    fake_model = MagicMock()
    monkeypatch.setattr(
        "models.model_store.hf_hub_download",
        MagicMock(return_value="/tmp/fake_model_file.pt"),
    )
    monkeypatch.setattr(
        "models.model_store.torch.load", MagicMock(return_value=fake_model)
    )

    result = store.load_model("repo/name", "model.pt")

    assert result is fake_model


def test_load_model_transformer_loader_is_noop_stub():
    store = _store_without_init_side_effects()
    store.loader_type = "transformer"
    assert store.load_model("repo/name", "model.pt") is None


def test_change_model_updates_repo_filename_and_model(monkeypatch):
    store = _store_without_init_side_effects()
    store.loader_type = "pt"
    fake_model = MagicMock()

    monkeypatch.setattr(
        store,
        "get_model",
        MagicMock(return_value=("repo/name", "model.pt")),
    )
    monkeypatch.setattr(store, "load_model", MagicMock(return_value=fake_model))

    store.change_model("http://patra/models?id=2")

    assert store.repo == "repo/name"
    assert store.filename == "model.pt"
    fake_model.eval.assert_called_once()
