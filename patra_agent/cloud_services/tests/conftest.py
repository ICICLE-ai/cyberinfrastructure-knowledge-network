import os
import sys
from unittest.mock import MagicMock

_CLOUD_SERVICES_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _CLOUD_SERVICES_ROOT)

# aggregate_events.py constructs a real confluent_kafka.Producer at module import time.
import confluent_kafka

confluent_kafka.Producer = MagicMock(name="Producer")
