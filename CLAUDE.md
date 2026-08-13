# CLAUDE.md

This repo is part of the Plale Lab workspace (`plale_lab/`). See `../CLAUDE.md` for cross-project context and the Karpathy Guidelines that apply lab-wide — this file covers only what's specific to `cyberinfrastructure-knowledge-network` (CKN).

## What this is

Docker Compose + Kafka + Neo4j edge-streaming stack; not a typical application repo.

```bash
make up      # see breakdown below
make down    # docker-compose down + docker network rm ckn-network
```

`make up` runs, in order: `network` (creates `ckn-network`), `docker-compose up -d`, `check-neo4j-server` (polls `cypher-shell` until ready), then copies `ckn_kg/constraints.cypher` into the `neo4j_server` container and applies it.

**Credentials are hardcoded placeholders, not env-file driven.** `PWD_HERE` appears literally in the root `docker-compose.yml` (`NEO4J_AUTH=neo4j/PWD_HERE`), the Makefile, CI workflow, and connector JSON templates — no `.env`/`.env.example` exists anywhere in the repo. Edit these files directly rather than looking for an env file.

## Structure

- `ckn_broker/` — Kafka Connect sink connector JSON configs for camera-traps and oracle-events, now Postgres-only (`pgsink-*.json`); the compiler-data and oracle-alerts pipelines and their Neo4j sinks were dropped as unused. `setup_connector.sh` registers the JDBC connectors.
- `ckn_kg/` — `constraints.cypher`, its own `docker-compose.yml`, `init_scripts/`
- `ckn_dashboard/` — Streamlit dashboard: `Home.py`, `pages/`, `ckn_kg.py`, `ckn_pg.py`, `llm_graph.py`, `util.py`, own `Dockerfile`/`docker-compose.yml`/`requirements.txt`, `modelcards/`, `test/`
- `plugins/` — four per-source daemons: `ckn_inference_daemon`, `ckn-mqtt-cameratraps`, `experiment-alerts`, `oracle_ckn_daemon`
- `patra_agent/` — edge/cloud agent feeding events to Patra: `cloud_services/`, `edge_device/`, `edge_server/`, own `requirements.txt`
- `examples/` — camera-trap event producer: `daemon.py`, `Dockerfile`, `event.json`, `docker-compose.yml`, `run_e2e_test.sh`, `tests/`

```bash
docker compose -f examples/docker-compose.yml up -d --build   # example camera-trap event producer
```

## Custom plugin tutorial (new Kafka topic → producer → Postgres sink)

1. Add the topic via `KAFKA_CREATE_TOPICS` in the root `docker-compose.yml`, then `make down && make up`.
2. Write a `confluent_kafka` Python producer; verify with `kafka-console-consumer` in the broker container.
3. Create a JDBC (Postgres) sink connector JSON in `ckn_broker/`, following the existing `pgsink-*.json` configs.
4. Register it via `curl -X POST .../connectors` in `setup_connector.sh`, re-run the producer, and check the table in Postgres.

`patra_agent/cloud_services/ckn_broker/` still uses Neo4j sinks for the deployment-topology graph
(Server/Model/Device/Deployment nodes) that feeds Patra's real-time deployment tracking — that
one wasn't touched by the Postgres migration above.

Full detail in the repo README.

## CI

`.github/workflows/ci.yml` ("CKN-CI") runs a matrix job, one entry per sub-component, each in its
own process with its own dependency install and `--cov` target: `oracle_ckn_daemon`,
`ckn-mqtt-cameratraps`, `experiment-alerts`, `ckn_inference_daemon`, `patra_agent/edge_server`,
`patra_agent/cloud_services`, `patra_agent/cloud_services/patra_mcp_server`, `ckn_dashboard`. All
run mocked unit tests — no live Kafka, Neo4j, Postgres, or Docker Compose stack. Keeping each
component in its own job matters: several plugins have same-named modules (`model.py`, `server.py`,
`util.py`), so importing more than one plugin's directory onto `sys.path` in the same pytest
process risks silently importing the wrong module.

The old version brought up the full docker-compose stack, waited on Kafka Connect and a Neo4j sink
connector, and ran `oracle_ckn_daemon`'s tests against a live Neo4j database; that stopped passing
reliably around April 2026 and was replaced with a mocked-unit-test version scoped to that one
plugin. This matrix extends the same approach to `ckn_dashboard` and every plugin under
`plugins/`/`patra_agent/` that previously had zero test coverage.

Notable test-only dependency gaps found and pinned in each component's own `tests/requirements.txt`
(these packages are imported by the production code but weren't declared anywhere before): `httpx`
for `ckn_inference_daemon`'s FastAPI `TestClient`; `psycopg2-binary`/`confluent-kafka` for
`patra_agent/cloud_services` (`aggregate_events.py` imports both, neither was in any
`requirements.txt`); `mcp~=1.0.0`/`neo4j`/`python-dotenv`/`openai` for `patra_mcp_server` (must pin
`mcp` to the same version the code was written against — later SDK versions changed the
`@server.list_tools()`/`@server.call_tool()` decorator API this code relies on).
