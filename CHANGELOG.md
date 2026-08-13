## [Unreleased]

### Added
- Mocked unit test suites for 5 previously-untested sub-components: `ckn-mqtt-cameratraps`,
  `experiment-alerts`, `ckn_inference_daemon`, `patra_agent` (`edge_server`, `cloud_services`,
  `cloud_services/patra_mcp_server`), and `ckn_dashboard`. No live Kafka/MQTT/Neo4j/Postgres/LLM
  services required — all external calls are mocked at the boundary. 160 tests total.
- CI (`.github/workflows/ci.yml`) restructured from a single `oracle_ckn_daemon`-only job into a
  matrix, one entry per sub-component, each with its own dependency install and `--cov` target.
- Filled test-only dependency gaps that existed but were undeclared in any `requirements.txt`:
  `httpx` (`ckn_inference_daemon`), `psycopg2-binary`/`confluent-kafka`
  (`patra_agent/cloud_services`), `mcp~=1.0.0`/`neo4j`/`python-dotenv`/`openai`
  (`patra_mcp_server`).

### Known issues found by the new tests (not fixed — flagged for the maintainer)
- `patra_agent/edge_server/server.py`: `/predict`'s "no file" and "no filename" validation paths
  call `flash()`, but the app never sets `secret_key`; both crash with a 500 instead of the
  intended redirect.
- `patra_agent/edge_server/server.py`: `qoe_predict()` only assigns the local `data` variable
  inside the extension-check branch but references it unconditionally afterward — an invalid
  file extension raises `UnboundLocalError` (surfaces as 500) instead of a clean 4xx.
- `patra_agent/cloud_services/patra_mcp_server/ingester/neo4j_ingester.py`: `update_mc()`
  accesses `model_card["model_requirements"]` with no existence guard, unlike `add_mc()`'s
  `if "model_requirements" in model_card`; a card missing that key raises `KeyError`.
- `plugins/ckn_inference_daemon/models/model_store.py`: `get_model()` passes `response.json()`
  (a dict) into `get_model_location()`, which immediately calls `json.loads()` expecting a raw
  string — crashes with `TypeError` against any real Patra server response.
- `plugins/ckn_inference_daemon` and `patra_agent/edge_server` each have their own
  `process_qoe()`/`calculate_acc_qoe()` with the accuracy ratio computed in opposite directions
  (provided/required vs. required/provided) — not necessarily a bug, but a real inconsistency
  across near-duplicate code worth reconciling.

## [v1.0.0] - 2026-08-12

First stable release.

### Changed
- Repointed README badges and clone URLs from the stale `Data-to-Insight-Center` org to
  `Plale-Lab`, the canonical home for this release.
- `ckn_broker/` is now Postgres-only: dropped the `cameratraps-power-summary` and
  `oracle-events` Neo4j sink connectors (already unused — never registered by
  `setup_connector.sh`) and the `compiler-data`/`oracle-alerts` Neo4j sinks (no downstream
  consumer). `patra_agent/cloud_services/ckn_broker/`'s Neo4j sinks are unaffected; they still
  back the deployment-topology graph that feeds Patra's real-time deployment tracking.
- CI modernized: `checkout@v2`/`setup-python@v2` -> v4/v5, Python 3.8 (EOL) -> 3.11, dropped a
  dead standalone `docker-compose` binary install.
- CI replaced the live docker-compose + Kafka + Kafka Connect + Neo4j integration test (which
  had not passed reliably since ~April 2026) with mocked unit tests against the
  `oracle_ckn_daemon` plugin's own event-processing and power-summary logic.

### Known limitations
- `ckn_inference_daemon` is experimental and outside the stability contract.
- Default Neo4j and Postgres credentials (`PWD_HERE` / `d2i`) are hardcoded placeholders across
  `docker-compose.yml`, the Makefile, CI, and connector JSON templates — no `.env` file exists.
  Do not deploy with these credentials in an untrusted network.

## [v0.2.0] - 2025-06-10

### Added
- **Plugins:**
  - **ckn-mqtt-cameratraps**: MQTT-based camera trap ingestion plugin for edge event and image streaming. Enables scalable, decoupled data collection from edge devices. _(ICICLE)_
  - **experiment-alerts**: Automated experiment monitoring and alerting plugin. Detects low-accuracy experiments and publishes alerts to Kafka for downstream workflows. _(ICICLE)_
  - **ckn_inference_daemon**: Edge inference research plugin implementing FastAPI-based serving and model management. Intended for prototyping and experimentation.  _(Research / Experimental)_
- **Documentation:**
  - Added comprehensive documentation for new plugins and event topics (`docs/topics.md`), plugin usage, and deployment.
- **Database:**
  - Introduced additional Neo4j indexes to improve query and analytics performance.

### Fixed
  - Improved experiment completion detection and ensured robust accuracy reporting in monitoring and alerting workflows.
  - Minor bug fixes, typo corrections, and formatting improvements throughout documentation and example configs.
