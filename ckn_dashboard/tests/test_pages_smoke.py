"""Minimal smoke coverage for the Streamlit page scripts under pages/. These aren't unit-
testable in the normal sense -- they're top-to-bottom scripts that build a UI as a side effect
of being run. Uses Streamlit's own headless AppTest harness (supported by the pinned
streamlit~=1.36.0) to confirm each page runs without raising, against the same mocked
Neo4jGraph/ChatOpenAI/etc. from conftest.py. This is presence/crash coverage, not behavioral
coverage of what each page renders.
"""

import os

import pytest
from streamlit.testing.v1 import AppTest

_PAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pages")

_PAGE_FILES = [
    "1_Camera_Traps.py",
    "2_Alerts.py",
    "3_CKN_Chat_Bot.py",
    "4_Compiler_Profiler.py",
    "5_Patra_Model_Cards.py",
]


@pytest.mark.parametrize("page_file", _PAGE_FILES)
def test_page_runs_without_raising(page_file, monkeypatch):
    # Streamlit pages resolve relative imports (e.g. "from ckn_pg import CKNPostgres") against
    # the dashboard root, matching how `streamlit run Home.py` actually executes them.
    monkeypatch.chdir(os.path.dirname(_PAGES_DIR))

    at = AppTest.from_file(os.path.join(_PAGES_DIR, page_file))
    at.run(timeout=30)

    assert not at.exception, f"{page_file} raised: {[str(e) for e in at.exception]}"
