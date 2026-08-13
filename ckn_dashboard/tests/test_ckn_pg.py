from unittest.mock import MagicMock

import pandas as pd
import pytest

from ckn_pg import CKNPostgres


@pytest.fixture
def pg(monkeypatch):
    store = CKNPostgres("postgresql://fake:fake@localhost:5432/fake")
    fake_conn = MagicMock()
    fake_conn.__enter__.return_value = fake_conn
    fake_conn.__exit__.return_value = False
    monkeypatch.setattr(store, "_conn", MagicMock(return_value=fake_conn))
    return store, fake_conn


def test_fetch_distinct_users_returns_list(pg):
    store, fake_conn = pg
    fake_cursor = MagicMock()
    fake_cursor.__enter__.return_value = fake_cursor
    fake_cursor.__exit__.return_value = False
    fake_cursor.fetchall.return_value = [("alice",), ("bob",)]
    fake_conn.cursor.return_value = fake_cursor

    result = store.fetch_distinct_users()

    assert result == ["alice", "bob"]


def test_fetch_distinct_users_empty_returns_none(pg):
    store, fake_conn = pg
    fake_cursor = MagicMock()
    fake_cursor.__enter__.return_value = fake_cursor
    fake_cursor.__exit__.return_value = False
    fake_cursor.fetchall.return_value = []
    fake_conn.cursor.return_value = fake_cursor

    assert store.fetch_distinct_users() is None


def test_get_experiment_info_for_user_sets_experiment_index(pg, monkeypatch):
    store, _fake_conn = pg
    fake_df = pd.DataFrame([{"Experiment": "exp-1", "User": "alice"}])
    monkeypatch.setattr("ckn_pg.pd.read_sql", MagicMock(return_value=fake_df))

    result = store.get_experiment_info_for_user("alice")

    assert result.index.name == "Experiment"


def test_fetch_experiments_empty_df_skips_set_index(pg, monkeypatch):
    store, _fake_conn = pg
    empty_df = pd.DataFrame()
    monkeypatch.setattr("ckn_pg.pd.read_sql", MagicMock(return_value=empty_df))

    result = store.fetch_experiments("alice")

    assert result.empty


def test_get_experiment_metrics_converts_row_to_float_dict(pg):
    store, fake_conn = pg
    fake_cursor = MagicMock()
    fake_cursor.__enter__.return_value = fake_cursor
    fake_cursor.__exit__.return_value = False
    fake_cursor.fetchone.return_value = {"precision": "0.9", "recall": None}
    fake_conn.cursor.return_value = fake_cursor

    result = store.get_experiment_metrics("exp-1")

    assert result == {"precision": 0.9, "recall": None}


def test_get_experiment_metrics_no_row_returns_empty_dict(pg):
    store, fake_conn = pg
    fake_cursor = MagicMock()
    fake_cursor.__enter__.return_value = fake_cursor
    fake_cursor.__exit__.return_value = False
    fake_cursor.fetchone.return_value = None
    fake_conn.cursor.return_value = fake_cursor

    assert store.get_experiment_metrics("exp-1") == {}


def test_get_exp_deployment_info_empty_returns_none(pg, monkeypatch):
    store, _fake_conn = pg
    monkeypatch.setattr("ckn_pg.pd.read_sql", MagicMock(return_value=pd.DataFrame()))

    assert store.get_exp_deployment_info("exp-1") is None


def test_get_exp_deployment_info_returns_dataframe_when_present(pg, monkeypatch):
    store, _fake_conn = pg
    fake_df = pd.DataFrame([{"Experiment": "exp-1", "total_cpu_power_consumption": 1.5}])
    monkeypatch.setattr("ckn_pg.pd.read_sql", MagicMock(return_value=fake_df))

    result = store.get_exp_deployment_info("exp-1")

    assert result is not None
    assert result.iloc[0]["total_cpu_power_consumption"] == 1.5


def test_get_mode_name_version_returns_model_id_as_is(pg):
    store, _fake_conn = pg
    assert store.get_mode_name_version("model-123") == "model-123"


def test_get_device_type_returns_device_id_when_found(pg):
    store, fake_conn = pg
    fake_cursor = MagicMock()
    fake_cursor.__enter__.return_value = fake_cursor
    fake_cursor.__exit__.return_value = False
    fake_cursor.fetchone.return_value = ("raspi-3",)
    fake_conn.cursor.return_value = fake_cursor

    assert store.get_device_type("exp-1") == "raspi-3"


def test_get_device_type_returns_unknown_when_not_found(pg):
    store, fake_conn = pg
    fake_cursor = MagicMock()
    fake_cursor.__enter__.return_value = fake_cursor
    fake_cursor.__exit__.return_value = False
    fake_cursor.fetchone.return_value = None
    fake_conn.cursor.return_value = fake_cursor

    assert store.get_device_type("exp-1") == "Unknown"
