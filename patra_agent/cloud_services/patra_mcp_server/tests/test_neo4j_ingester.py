from unittest.mock import MagicMock

import pytest

import ingester.neo4j_ingester as neo4j_ingester_module
from ingester.neo4j_ingester import MCIngester


@pytest.fixture
def mc_ingester(monkeypatch):
    fake_db = MagicMock()
    fake_graphdb_cls = MagicMock(return_value=fake_db)
    monkeypatch.setattr(neo4j_ingester_module, "GraphDB", fake_graphdb_cls)
    monkeypatch.setattr(neo4j_ingester_module, "embed_model_versioning", MagicMock(return_value=[0.1, 0.2]))

    ingester = MCIngester("bolt://fake:7687", "neo4j", "pwd")
    return ingester, fake_db


def _base_model_card(**overrides):
    card = {
        "author": "Alice",
        "name": "ResNet",
        "version": "1.0",
        "input_data": "datasheet-1",
        "ai_model": {"framework": "pytorch"},
        "bias_analysis": None,
        "xai_analysis": None,
        "foundational_model": None,
    }
    card.update(overrides)
    return card


def test_add_mc_early_returns_when_already_exists(mc_ingester):
    ingester, fake_db = mc_ingester
    fake_db.check_mc_exists.return_value = (True, "existing-id")

    exists, model_id = ingester.add_mc(_base_model_card())

    assert exists is True
    assert model_id == "existing-id"
    fake_db.insert_base_mc.assert_not_called()


def test_add_mc_generates_id_when_missing(mc_ingester):
    ingester, fake_db = mc_ingester
    fake_db.check_mc_exists.return_value = (False, None)

    exists, model_id = ingester.add_mc(_base_model_card())

    assert exists is False
    assert model_id == "Alice_ResNet_1.0"
    fake_db.insert_base_mc.assert_called_once()


def test_add_mc_uses_provided_id_when_present(mc_ingester):
    ingester, fake_db = mc_ingester
    fake_db.check_mc_exists.return_value = (False, None)

    _exists, model_id = ingester.add_mc(_base_model_card(id="custom-id"))

    assert model_id == "custom-id"


def test_add_mc_skips_bias_xai_requirements_when_none(mc_ingester):
    ingester, fake_db = mc_ingester
    fake_db.check_mc_exists.return_value = (False, None)

    ingester.add_mc(_base_model_card())

    fake_db.insert_bias_analysis_metadata.assert_not_called()
    fake_db.insert_xai_analysis_metadata.assert_not_called()


def test_add_mc_inserts_bias_and_xai_when_present(mc_ingester):
    ingester, fake_db = mc_ingester
    fake_db.check_mc_exists.return_value = (False, None)

    ingester.add_mc(
        _base_model_card(bias_analysis={"metric": 0.1}, xai_analysis={"shap": [1, 2]})
    )

    fake_db.insert_bias_analysis_metadata.assert_called_once()
    fake_db.insert_xai_analysis_metadata.assert_called_once()


def test_add_mc_inserts_model_requirements_when_present(mc_ingester):
    ingester, fake_db = mc_ingester
    fake_db.check_mc_exists.return_value = (False, None)

    ingester.add_mc(_base_model_card(model_requirements={"torch": "2.0"}))

    fake_db.insert_model_requirements_metadata.assert_called_once()


def test_add_mc_connects_foundational_model_only_when_truthy(mc_ingester):
    ingester, fake_db = mc_ingester
    fake_db.check_mc_exists.return_value = (False, None)

    ingester.add_mc(_base_model_card(foundational_model="base-model-id"))

    fake_db.connect_foundational_model.assert_called_once_with("Alice_ResNet_1.0", "base-model-id")


def test_add_mc_similarity_enabled_embeds_and_infers_versioning(monkeypatch):
    fake_db = MagicMock()
    fake_graphdb_cls = MagicMock(return_value=fake_db)
    fake_embed = MagicMock(return_value=[0.5, 0.6])
    monkeypatch.setattr(neo4j_ingester_module, "GraphDB", fake_graphdb_cls)
    monkeypatch.setattr(neo4j_ingester_module, "embed_model_versioning", fake_embed)
    fake_db.check_mc_exists.return_value = (False, None)

    ingester = MCIngester("bolt://fake:7687", "neo4j", "pwd", similarity_support=True)
    card = _base_model_card()
    ingester.add_mc(card)

    fake_embed.assert_called_once()
    assert card["embedding"] == [0.5, 0.6]
    fake_db.infer_versioning.assert_called_once_with(card)


def test_update_mc_updates_when_found(mc_ingester):
    ingester, fake_db = mc_ingester
    fake_db.check_update_mc.return_value = "base-id"

    result = ingester.update_mc(
        _base_model_card(
            bias_analysis={"metric": 0.1},
            xai_analysis={"shap": [1]},
            model_requirements={"torch": "2.0"},
        )
    )

    assert result == "base-id"
    fake_db.update_base_mc.assert_called_once()
    fake_db.update_bias_analysis_metadata.assert_called_once()
    fake_db.update_xai_analysis_metadata.assert_called_once()
    fake_db.update_model_requirements_metadata.assert_called_once()


def test_update_mc_missing_model_requirements_key_raises_key_error(mc_ingester):
    """add_mc() guards model_requirements access with `if "model_requirements" in model_card`,
    but update_mc() accesses model_card["model_requirements"] unconditionally -- an asymmetry
    between the two methods, not a test artifact. A card missing that key entirely (rather than
    set to None) crashes update_mc() with KeyError once check_update_mc() finds a match.
    """
    ingester, fake_db = mc_ingester
    fake_db.check_update_mc.return_value = "base-id"
    card = _base_model_card()
    assert "model_requirements" not in card

    with pytest.raises(KeyError):
        ingester.update_mc(card)


def test_update_mc_returns_none_and_skips_updates_when_not_found(mc_ingester):
    ingester, fake_db = mc_ingester
    fake_db.check_update_mc.return_value = None

    result = ingester.update_mc(_base_model_card())

    assert result is None
    fake_db.update_base_mc.assert_not_called()


def test_get_pid_normalizes_case_and_spaces(mc_ingester):
    ingester, _fake_db = mc_ingester
    assert ingester.get_pid("Alice B", "My Model", "V 1.0") == "alice_b-my_model-v_1.0"
