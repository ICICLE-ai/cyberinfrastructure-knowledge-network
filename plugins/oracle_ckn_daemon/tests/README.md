CKN Oracle Daemon plugin tests:

These are mocked unit tests against `oracle_daemon.py` and `power_processor.py` directly —
no live Kafka, Neo4j, or Postgres services required.

1. Install requirements:
```bash
  pip install -r ../requirements.txt -r requirements.txt
  ```

2. **Run Tests**:
```bash
  pytest .
```

   - `test_oracle_event_handler.py` — event-metric math (IoU, precision/recall), fixture-driven
     event processing, and broker-connection retry logic.
   - `test_power_processor.py` — power-summary flattening and Kafka production, using a mocked
     producer.