#!/usr/bin/env bash
# End-to-end Kafka pipeline test:
#   edge-daemon → Kafka → Kafka Connect → PostgreSQL → REST API
#
# Usage: cd cyberinfrastructure-knowledge-network/examples && bash run_e2e_test.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CKN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PATRA_KG_ROOT="$(cd "$CKN_ROOT/../patra-kg" && pwd)"

KAFKA_CONNECT_URL="http://localhost:8083"
PATRA_API_URL="http://localhost:8000"
NETWORK_NAME="ckn-network"

POLL_INTERVAL=3
MAX_WAIT=120  # seconds

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[E2E]${NC} $*"; }
warn() { echo -e "${YELLOW}[E2E]${NC} $*"; }
fail() { echo -e "${RED}[E2E FAIL]${NC} $*"; exit 1; }

# ── 1. Create shared Docker network ─────────────────────────────────────────
if ! docker network inspect "$NETWORK_NAME" &>/dev/null; then
  log "Creating Docker network: $NETWORK_NAME"
  docker network create "$NETWORK_NAME"
else
  log "Docker network '$NETWORK_NAME' already exists"
fi

# ── 2. Start CKN services (broker + kafka-connect) ──────────────────────────
log "Starting CKN services (broker, kafka-connect)..."
docker compose -f "$CKN_ROOT/docker-compose.yml" up -d broker kafka-connect

# ── 3. Start patra-kg services (postgres + backend) ─────────────────────────
log "Starting patra-kg services (postgres, patra-backend)..."
docker compose -f "$PATRA_KG_ROOT/docker-compose.backend.yml" up -d postgres patra-backend

# ── 4. Poll Kafka Connect until ready ────────────────────────────────────────
log "Waiting for Kafka Connect to be ready..."
elapsed=0
while true; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "$KAFKA_CONNECT_URL/connectors" 2>/dev/null || echo "000")
  if [ "$status" = "200" ]; then
    log "Kafka Connect is ready"
    break
  fi
  elapsed=$((elapsed + POLL_INTERVAL))
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    fail "Kafka Connect did not become ready within ${MAX_WAIT}s"
  fi
  warn "Kafka Connect not ready (HTTP $status), retrying in ${POLL_INTERVAL}s... (${elapsed}s/${MAX_WAIT}s)"
  sleep "$POLL_INTERVAL"
done

# ── 5. Poll patra-backend health until ready ─────────────────────────────────
log "Waiting for patra-backend to be ready..."
elapsed=0
while true; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "$PATRA_API_URL/healthz" 2>/dev/null || echo "000")
  if [ "$status" = "200" ]; then
    log "patra-backend is ready"
    break
  fi
  elapsed=$((elapsed + POLL_INTERVAL))
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    fail "patra-backend did not become ready within ${MAX_WAIT}s"
  fi
  warn "patra-backend not ready (HTTP $status), retrying in ${POLL_INTERVAL}s... (${elapsed}s/${MAX_WAIT}s)"
  sleep "$POLL_INTERVAL"
done

# ── 6. Run the example daemon to produce a test event ────────────────────────
log "Building and running the example daemon to produce a test event..."
docker compose -f "$SCRIPT_DIR/docker-compose.yml" up --build --abort-on-container-exit

# ── 7. Wait for Kafka Connect to sink the row ───────────────────────────────
log "Waiting 5s for Kafka Connect to sink the event to PostgreSQL..."
sleep 5

# ── 8. Verify via REST API ──────────────────────────────────────────────────
log "Verifying event arrived via REST API..."

echo ""
log "── GET /experiments/animal-ecology/users ──"
users_response=$(curl -s "$PATRA_API_URL/experiments/animal-ecology/users")
echo "$users_response" | python3 -m json.tool 2>/dev/null || echo "$users_response"

if echo "$users_response" | grep -q "example_user"; then
  echo -e "${GREEN}  ✓ 'example_user' found in users list${NC}"
else
  echo -e "${RED}  ✗ 'example_user' NOT found in users list${NC}"
fi

echo ""
log "── GET /experiments/animal-ecology/users/example_user/summary ──"
summary_response=$(curl -s "$PATRA_API_URL/experiments/animal-ecology/users/example_user/summary")
echo "$summary_response" | python3 -m json.tool 2>/dev/null || echo "$summary_response"

if echo "$summary_response" | grep -q "example_experiment"; then
  echo -e "${GREEN}  ✓ 'example_experiment' found in user summary${NC}"
else
  echo -e "${RED}  ✗ 'example_experiment' NOT found in user summary${NC}"
fi

# ── 9. Final result ─────────────────────────────────────────────────────────
echo ""
if echo "$users_response" | grep -q "example_user" && echo "$summary_response" | grep -q "example_experiment"; then
  echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}  E2E TEST PASSED${NC}"
  echo -e "${GREEN}  Event flowed: daemon → Kafka → Connect → PostgreSQL → API${NC}"
  echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
else
  echo -e "${RED}══════════════════════════════════════════════════${NC}"
  echo -e "${RED}  E2E TEST FAILED${NC}"
  echo -e "${RED}  Check the API responses above for details${NC}"
  echo -e "${RED}══════════════════════════════════════════════════${NC}"
  exit 1
fi
