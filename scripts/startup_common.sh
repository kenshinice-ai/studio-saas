#!/usr/bin/env bash
# Shared startup helpers for the StudioSaaS macOS launchers.
#
# The launchers intentionally fail loudly when a prerequisite cannot be
# installed or a health check does not pass. They never continue with a partial
# stack and never terminate an unknown process that happens to own the port.

say() {
  printf "\n==> %s\n" "$1" >&2
}

die() {
  printf "\nERROR: %s\n" "$1" >&2
  exit 1
}

require_homebrew() {
  command -v brew >/dev/null 2>&1 || die \
    "Homebrew is required for PostgreSQL and Cloudflare Tunnel. Install it from https://brew.sh and run this launcher again."
}

add_postgres_to_path() {
  local pg_bin
  for pg_bin in \
    /opt/homebrew/opt/postgresql@18/bin \
    /opt/homebrew/opt/postgresql@17/bin \
    /opt/homebrew/opt/postgresql@16/bin \
    /usr/local/opt/postgresql@18/bin \
    /usr/local/opt/postgresql@17/bin \
    /usr/local/opt/postgresql@16/bin; do
    if [ -d "$pg_bin" ]; then
      export PATH="$pg_bin:$PATH"
      return 0
    fi
  done
}

ensure_brew_command() {
  local command_name="$1"
  local formula="$2"
  if command -v "$command_name" >/dev/null 2>&1; then
    return 0
  fi
  require_homebrew
  say "Installing missing dependency: $formula"
  brew install "$formula"
  add_postgres_to_path
  command -v "$command_name" >/dev/null 2>&1 || die \
    "Installed $formula, but $command_name is still unavailable on PATH."
}

ensure_python_environment() {
  local project_root="$1"
  local python_bin="$project_root/.venv/bin/python"
  local requirements="$project_root/backend/requirements.txt"

  command -v python3 >/dev/null 2>&1 || die "Python 3 is required."
  if [ ! -x "$python_bin" ]; then
    say "Creating Python virtual environment"
    python3 -m venv "$project_root/.venv"
  fi

  if ! "$python_bin" -c "import flask, waitress, psycopg" >/dev/null 2>&1; then
    say "Installing Python dependencies"
    "$python_bin" -m pip install --upgrade pip
    "$python_bin" -m pip install -r "$requirements"
  fi

  "$python_bin" -c "import flask, waitress, psycopg" >/dev/null 2>&1 || die \
    "Python dependencies are incomplete after installation."
  printf "%s\n" "$python_bin"
}

ensure_postgres_tools() {
  add_postgres_to_path
  if ! command -v pg_isready >/dev/null 2>&1 || \
     ! command -v psql >/dev/null 2>&1 || \
     ! command -v createdb >/dev/null 2>&1; then
    require_homebrew
    say "Installing PostgreSQL 18"
    brew install postgresql@18
    add_postgres_to_path
  fi
  command -v pg_isready >/dev/null 2>&1 || die "pg_isready is unavailable."
  command -v psql >/dev/null 2>&1 || die "psql is unavailable."
  command -v createdb >/dev/null 2>&1 || die "createdb is unavailable."
}

ensure_postgres_running() {
  local host="$1"
  local port="$2"
  local attempt

  if pg_isready -h "$host" -p "$port" >/dev/null 2>&1; then
    return 0
  fi

  require_homebrew
  say "Starting PostgreSQL"
  if brew list --versions postgresql@18 >/dev/null 2>&1; then
    brew services start postgresql@18
  elif brew list --versions postgresql >/dev/null 2>&1; then
    brew services start postgresql
  else
    die "PostgreSQL is not installed after the environment check."
  fi

  for attempt in $(seq 1 30); do
    if pg_isready -h "$host" -p "$port" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "PostgreSQL did not become ready at $host:$port within 30 seconds."
}

ensure_database_exists() {
  local host="$1"
  local port="$2"
  local database_name="$3"

  if psql -h "$host" -p "$port" -d "$database_name" -X -v ON_ERROR_STOP=1 \
      -c "SELECT 1" >/dev/null 2>&1; then
    return 0
  fi
  say "Creating PostgreSQL database: $database_name"
  createdb -h "$host" -p "$port" "$database_name"
  psql -h "$host" -p "$port" -d "$database_name" -X -v ON_ERROR_STOP=1 \
    -c "SELECT 1" >/dev/null
}

ensure_database_connection() {
  local database_url="$1"

  psql "$database_url" -X -v ON_ERROR_STOP=1 -c "SELECT 1" >/dev/null 2>&1 || die \
    "The configured STUDIOSAAS_DATABASE_URL is not reachable."
}

stop_managed_process() {
  local pid_file="$1"
  local expected_text="$2"
  local pid=""

  [ -f "$pid_file" ] || return 0
  pid="$(tr -cd '0-9' <"$pid_file")"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    if ps -p "$pid" -o command= | grep -F "$expected_text" >/dev/null 2>&1; then
      kill "$pid"
      for _attempt in $(seq 1 10); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.2
      done
    else
      die "PID file $pid_file points to an unexpected process. Refusing to stop it."
    fi
  fi
  rm -f "$pid_file"
}

require_free_port() {
  local port="$1"
  local owners
  owners="$(lsof -tiTCP:"$port" -sTCP:LISTEN -nP 2>/dev/null || true)"
  [ -z "$owners" ] || die \
    "Port $port is already in use by PID(s): $(printf '%s' "$owners" | tr '\n' ' '). Stop that process explicitly before starting StudioSaaS."
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempts="${3:-30}"
  local attempt

  for attempt in $(seq 1 "$attempts"); do
    if curl --fail --silent --show-error --max-time 3 "$url" >/dev/null 2>&1; then
      printf "  OK: %s\n" "$label"
      return 0
    fi
    sleep 1
  done
  die "$label did not become healthy: $url"
}
