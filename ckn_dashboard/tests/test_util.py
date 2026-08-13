"""util.py has no pure logic -- its entire body constructs a Neo4jGraph client and a
ChatOpenAI client at import time (both mocked in conftest.py before this module is ever
imported). These tests exist to confirm the module still imports safely under mocking and
exposes the three names llm_graph.py and others depend on -- not to test business logic,
since there isn't any here.
"""

import util


def test_module_imports_without_touching_real_services():
    assert util.graph is not None
    assert util.llm is not None


def test_top_k_results_default():
    assert util.top_k_results == 10
