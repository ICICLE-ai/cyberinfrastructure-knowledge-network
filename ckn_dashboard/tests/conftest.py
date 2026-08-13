import os
import sys
from unittest.mock import MagicMock

_DASHBOARD_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _DASHBOARD_ROOT)

# util.py constructs a real Neo4jGraph(...) and ChatOpenAI(...) at module import time, and
# llm_graph.py (and anything importing it) transitively imports `util`. Patch the upstream
# classes before util.py's first execution so this wins regardless of which test file happens
# to trigger that first import.
import langchain_community.graphs as _lc_graphs
import langchain_openai as _lc_openai

_lc_graphs.Neo4jGraph = MagicMock(name="Neo4jGraph")
_lc_openai.ChatOpenAI = MagicMock(name="ChatOpenAI")

os.environ.setdefault("NEO4J_URI", "bolt://fake:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PWD", "fake-password")

# Several Streamlit pages call real query methods on CKNKnowledgeGraph/CKNPostgres at module
# top-level (not just inside callbacks), e.g. pages/1_Camera_Traps.py's
# `users = pg.fetch_distinct_users()` and pages/5_Patra_Model_Cards.py's
# `kg.get_model_card_ids()`. ckn_kg.py uses the raw neo4j.GraphDatabase driver directly (a
# different path from util.py's LangChain-wrapped Neo4jGraph, already mocked above), and
# ckn_pg.py uses psycopg2.connect directly. Mock both globally so no page import can reach a
# real service, consistent with every other CKN sub-component's "no live services" test
# contract.
import neo4j
import psycopg2

neo4j.GraphDatabase.driver = MagicMock(name="GraphDatabase.driver", return_value=MagicMock())
psycopg2.connect = MagicMock(name="psycopg2.connect", return_value=MagicMock())
