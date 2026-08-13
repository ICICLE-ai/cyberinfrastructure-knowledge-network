from cypher_queries import (
    CYPHER_CALCULATE_ACCURACY,
    CYPHER_FIND_COMPLETABLE_EXPERIMENTS,
    CYPHER_FIND_LOW_ACCURACY_FOR_ALERT,
    CYPHER_UPDATE_COMPLETED_EXPERIMENT,
)


def test_find_completable_experiments_has_no_params():
    assert "MATCH" in CYPHER_FIND_COMPLETABLE_EXPERIMENTS
    assert "$" not in CYPHER_FIND_COMPLETABLE_EXPERIMENTS


def test_calculate_accuracy_has_expected_params():
    assert "$experiment_id" in CYPHER_CALCULATE_ACCURACY
    assert "$confidence_threshold" in CYPHER_CALCULATE_ACCURACY


def test_update_completed_experiment_has_expected_params():
    for param in ("$experiment_id", "$end_time_ms", "$accuracy", "$start_time_ms"):
        assert param in CYPHER_UPDATE_COMPLETED_EXPERIMENT


def test_find_low_accuracy_for_alert_has_expected_params():
    assert "$accuracy_threshold" in CYPHER_FIND_LOW_ACCURACY_FOR_ALERT
    assert "$time_range" in CYPHER_FIND_LOW_ACCURACY_FOR_ALERT
