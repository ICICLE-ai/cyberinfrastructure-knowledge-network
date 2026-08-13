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
