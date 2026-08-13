from unittest.mock import MagicMock

import pytest

import model as model_module
import models.hf_transformer_vision_llm as hf_module
import models.image_net_model as imagenet_module


@pytest.fixture
def mocked_model_classes(monkeypatch):
    """_get_plugin_instance() does its imports at function-call time
    ("from models.image_net_model import ImageNetModel"), so patching the class attribute
    on the already-imported module is picked up on every call without needing a reload.
    """
    fake_imagenet_cls = MagicMock(name="ImageNetModel")
    fake_hf_cls = MagicMock(name="HFTransformerVisionLLM")
    monkeypatch.setattr(imagenet_module, "ImageNetModel", fake_imagenet_cls)
    monkeypatch.setattr(hf_module, "HFTransformerVisionLLM", fake_hf_cls)
    return fake_imagenet_cls, fake_hf_cls


def test_dispatch_imagenet_instantiates_image_net_model(monkeypatch, mocked_model_classes):
    fake_imagenet_cls, fake_hf_cls = mocked_model_classes
    monkeypatch.setattr(model_module, "MODEL_TYPE", "imagenet")

    instance = model_module._get_plugin_instance()

    fake_imagenet_cls.assert_called_once_with(
        model_module.model_store.model,
        getattr(model_module.model_store, "feature_extractor", None),
    )
    fake_hf_cls.assert_not_called()
    assert instance is fake_imagenet_cls.return_value


def test_dispatch_vision_transformer_instantiates_hf_model(monkeypatch, mocked_model_classes):
    fake_imagenet_cls, fake_hf_cls = mocked_model_classes
    monkeypatch.setattr(model_module, "MODEL_TYPE", "vision_transformer")

    instance = model_module._get_plugin_instance()

    fake_hf_cls.assert_called_once_with(model_module.model_store.model)
    fake_imagenet_cls.assert_not_called()
    assert instance is fake_hf_cls.return_value


def test_dispatch_unsupported_model_type_raises(monkeypatch, mocked_model_classes):
    monkeypatch.setattr(model_module, "MODEL_TYPE", "sound")

    with pytest.raises(ValueError, match="Unsupported MODEL_TYPE"):
        model_module._get_plugin_instance()


def test_load_model_reloads_store_and_rebuilds_current_model(monkeypatch, mocked_model_classes):
    fake_imagenet_cls, _fake_hf_cls = mocked_model_classes
    monkeypatch.setattr(model_module, "MODEL_TYPE", "imagenet")
    monkeypatch.setattr(model_module.model_store, "change_model", MagicMock())
    fake_imagenet_cls.reset_mock(return_value=True)
    new_instance = MagicMock(name="rebuilt_current_model")
    fake_imagenet_cls.return_value = new_instance

    model_module.load_model("new-model-url")

    model_module.model_store.change_model.assert_called_once_with("new-model-url")
    assert model_module.current_model is new_instance


def test_change_model_delegates_to_load_model(monkeypatch):
    load_model_mock = MagicMock()
    monkeypatch.setattr(model_module, "load_model", load_model_mock)

    model_module.change_model("some-model")

    load_model_mock.assert_called_once_with("some-model")
