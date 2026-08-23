#!/bin/bash
set -euo pipefail

# The unified Dockerfile/compose live here at the repo root (build context needs
# both backend/ and frontend/). Operate from this dir regardless of invocation cwd.
cd "$(dirname "$0")"

ROUTES="/ app · /admin · /status (dev tool links live in the app nav)"
HEALTH_URL="http://localhost:8000/api/health"

preflight() {
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Start Docker Desktop and try again." >&2
    exit 1
  fi

  if [ ! -f .env ]; then
    echo ".env not found; creating one from .env.example"
    cp .env.example .env
  fi

  if port_in_use 8000; then
    echo "WARN: host port 8000 is already in use; the container may fail to bind." >&2
  fi

  local mem_total
  mem_total=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)
  if [ "${mem_total:-0}" -gt 0 ] && [ "$mem_total" -lt 4294967296 ]; then
    echo "WARN: Docker has <4GB RAM; raise Docker Desktop RAM to >=4GB (Settings > Resources)." >&2
  fi
}

port_in_use() {
  local port=$1
  if (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null; then
    exec 3>&- 3<&-
    return 0
  fi
  return 1
}

wait_for_health() {
  echo "Waiting for the app to become healthy (first build can take ~3-5 min)..."
  local deadline=$(( SECONDS + 90 ))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      echo "Up → http://localhost:8000  ( $ROUTES )"
      echo "(logs: ./manage.sh logs | stop: ./manage.sh down)"
      return 0
    fi
    sleep 3
  done
  echo "still starting - check ./manage.sh logs" >&2
}

run_dev() {
  preflight
  echo "Starting DEV (hot-reload backend)..."
  docker compose --profile dev up -d --build
  wait_for_health
}

run_prod() {
  preflight
  echo "Starting PROD image locally..."
  docker compose --profile prod up -d --build
  wait_for_health
}

gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 12
  else
    echo "genesis-$(date +%s)"
  fi
}

set_env() {
  local key=$1 val=$2
  local tmp=.env.tmp
  grep -v "^${key}=" .env > "$tmp" 2>/dev/null || true
  echo "${key}=${val}" >> "$tmp"
  mv "$tmp" .env
}

save_certs() {
  mkdir -p deploy/certs
  if [ "$(uname)" = "Darwin" ]; then
    security find-certificate -a -p /Library/Keychains/System.keychain > deploy/certs/corp-ca.crt 2>/dev/null || true
    security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain >> deploy/certs/corp-ca.crt 2>/dev/null || true
    echo "  OK - company certificates saved to deploy/certs/corp-ca.crt"
  elif [ -f /etc/ssl/certs/ca-certificates.crt ]; then
    cp /etc/ssl/certs/ca-certificates.crt deploy/certs/corp-ca.crt
    echo "  OK - company certificates saved to deploy/certs/corp-ca.crt"
  else
    echo "  ! couldn't auto-detect certs; if the build fails on a certificate error, drop your company .crt into deploy/certs/"
  fi
}

configure_env() {
  cp .env.example .env
  local app_name llm_choice
  printf "App name [Genesis]: "; read -r app_name || true
  set_env APP_NAME "${app_name:-Genesis}"

  echo ""
  echo "AI chat setup:"
  echo "  [1] OpenRouter  - one key, easiest (recommended)"
  echo "  [2] Portkey     - your gateway + a provider key"
  echo "  [3] Skip        - add later"
  printf "> "; read -r llm_choice || true
  case "$llm_choice" in
    1)
      local k
      printf "Paste your OpenRouter key: "; read -r k || true
      set_env LLM_API_KEY "$k"
      set_env LLM_BASE_URL "https://openrouter.ai/api/v1"
      set_env LLM_MODEL "openai/gpt-4o-mini"
      ;;
    2)
      local pk prov provkey
      printf "Portkey gateway URL (e.g. https://your-gateway.portkey.ai/v1): "; read -r gw || true
      printf "Portkey API key: "; read -r pk || true
      printf "Provider (openai/anthropic/google): "; read -r prov || true
      printf "Provider API key: "; read -r provkey || true
      set_env LLM_API_KEY "$provkey"
      set_env LLM_BASE_URL "$gw"
      set_env LLM_EXTRA_HEADERS "{\"x-portkey-api-key\":\"$pk\",\"x-portkey-provider\":\"$prov\"}"
      ;;
    *)
      echo "Skipping AI for now (add it to .env later)."
      ;;
  esac

  echo ""
  local db_pass admin_pass
  printf "Database password [Enter = auto-generate a strong one]: "; read -r db_pass || true
  [ -z "$db_pass" ] && db_pass="$(gen_secret)"
  set_env POSTGRES_PASSWORD "$db_pass"
  printf "Dashboard admin password [Enter = auto-generate]: "; read -r admin_pass || true
  [ -z "$admin_pass" ] && admin_pass="$(gen_secret)"
  set_env O2_ROOT_PASSWORD "$admin_pass"

  echo ""
  local corp
  printf "Are you on a corporate network with a security proxy? [y/N] "; read -r corp || true
  case "$corp" in [yY]*) save_certs ;; esac

  echo "OK - .env configured"
  echo ""
  echo "Save these - they log you into the built-in dashboards (also stored in .env):"
  echo "  Database password:  $db_pass"
  echo "  Dashboard login:    admin@genesis.local  /  $admin_pass"
}

doctor() {
  echo "=============================================="
  echo "  Genesis setup"
  echo "=============================================="

  if ! command -v docker >/dev/null 2>&1; then
    echo "X  Docker is not installed."
    echo "   Install one of these (any works), start it, then run ./manage.sh again:"
    echo "     - Rancher Desktop (free for work):  https://rancherdesktop.io"
    echo "     - Docker Desktop:                   https://www.docker.com/products/docker-desktop"
    echo "     - OrbStack (Mac, fast):             https://orbstack.dev"
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "X  Docker is installed but not running."
    echo "   Start Docker/Rancher Desktop, wait until it says 'running', then run ./manage.sh again."
    exit 1
  fi
  echo "OK - Docker is running"

  local mem_total
  mem_total=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)
  if [ "${mem_total:-0}" -gt 0 ] && [ "$mem_total" -lt 4294967296 ]; then
    echo "!  Docker has <4GB RAM; raise it in Settings > Resources for best results."
  fi
  if port_in_use 8000; then
    echo "!  Port 8000 is in use; the app may not start. Close whatever is using it."
  fi

  local reconfig=y
  if [ -f .env ]; then
    printf "A .env already exists. Reconfigure it? [y/N] "; read -r reconfig || true
    reconfig=${reconfig:-N}
  fi
  case "$reconfig" in
    [yY]*) configure_env ;;
    *) echo "Keeping existing .env." ;;
  esac

  echo ""
  local start
  printf "Start the app now? [Y/n] "; read -r start || true
  case "$start" in
    [nN]*) echo "When you're ready: ./manage.sh dev" ;;
    *) run_dev ;;
  esac
}

usage() {
  cat <<'EOF'
Usage: ./manage.sh <command>   (no command = guided setup)

Everything except first-run setup is the genesis CLI; any command not listed
below is forwarded to it, so `./manage.sh map` and `genesis map` are the same.

  (none)         Guided setup: checks Docker, configures .env, starts the app
  certs          Save your company's certificates for corporate networks
  up | prod      Run the built image locally (prod profile)

Forwarded to genesis (run `genesis --help` for the full list):
  dev            Build and start the app
  down           Stop and remove containers
  logs           Follow container logs
  restart [proc] Restart one process (default: fastapi)
  migrate "msg"  Create + apply a database migration after model changes
  map            Print the resolved project graph
  docs · check   Generate / verify the AI context documents
  render         Assemble a new project from modules

Maintainer-only (requires the Azure CLI `az`):
  publish-dev    Build + push to Dev ACR
  publish-prod   Build + push to Prod ACR
EOF
}

build_and_push() {
  local ACR_NAME=$1
  local IMAGE_NAME=$2
  local ENVIRONMENT=$3

  echo "Logging into $ACR_NAME..."
  az acr login -n "$ACR_NAME"

  local IMAGE_TAG="latest"
  local HOST_PORT="80"
  local COMMIT_TAG
  COMMIT_TAG=$(git rev-parse --short HEAD)

  export IMAGE_NAME
  export IMAGE_TAG
  export HOST_PORT
  export ENV_FOR_DYNACONF="$ENVIRONMENT"

  echo "Building image..."
  docker compose --profile prod build

  echo "Tagging immutable version..."
  docker tag "${IMAGE_NAME}:latest" "${IMAGE_NAME}:${COMMIT_TAG}"

  echo "Pushing images..."
  docker compose --profile prod push
  docker push "${IMAGE_NAME}:${COMMIT_TAG}"

  echo "Pushed:"
  echo "  - ${IMAGE_NAME}:latest"
  echo "  - ${IMAGE_NAME}:${COMMIT_TAG}"
}

publish_dev() {
  build_and_push \
    "${DEV_ACR_NAME:-your-dev-acr}" \
    "${DEV_IMAGE_NAME:-your-dev-acr.azurecr.io/genesis}" \
    "development"
}

publish_prod() {
  build_and_push \
    "${PROD_ACR_NAME:-your-prod-acr}" \
    "${PROD_IMAGE_NAME:-your-prod-acr.azurecr.io/genesis}" \
    "production"
}

if [ "$#" -lt 1 ]; then
  doctor
  exit 0
fi

genesis() {
  if command -v python3 >/dev/null 2>&1; then
    PYTHONPATH="$(pwd)/tools/genesis" exec python3 -m genesis_cli.cli "$@"
  fi
  if command -v uvx >/dev/null 2>&1; then
    exec uvx --no-cache --from ./tools/genesis genesis "$@"
  fi
  echo "The genesis CLI needs uv (https://astral.sh/uv) or python3 on PATH." >&2
  exit 1
}

case "$1" in
  doctor|setup) doctor ;;
  up|prod)      run_prod ;;
  certs)        save_certs ;;
  publish-dev)  publish_dev ;;
  publish-prod) publish_prod ;;
  -h|--help|help) usage ;;
  *) genesis "$@" ;;
esac
