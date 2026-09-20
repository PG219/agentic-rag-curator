# Airflow 3.0 Setup Notes — agentic-rag-curator

This document records the real issues hit while wiring Apache Airflow 3.0 into this
project's ingestion pipeline (Stage 1e), why they happened, and how they were fixed.
Airflow 3.0 changed several architectural pieces from 2.x, and most of the official
docs/tutorials online still assume 2.x behavior — so this is kept as a reference for
future-me and as a debugging story for interviews.

## Architecture decision: Airflow calls the app over HTTP, not via direct import

**Original plan:** the DAG would import `IngestionService` from `src/` directly and
run it as a Python task.

**What broke it:** installing the project's `pyproject.toml` dependencies into
Airflow's own container image (so it could import `src/`) silently upgraded
SQLAlchemy to 2.0.x. Airflow 3.0's own internals (`apache-airflow-core`) require
`sqlalchemy<2.0`. This corrupted Airflow's own runtime and broke `airflow db migrate`.

**Fix — architectural, not a version pin:** decoupled Airflow from the app entirely.
The FastAPI app now runs as its own containerized service (`app` in `compose.yml`),
exposing `POST /api/v1/ingest`. The Airflow DAG's only job is to call that endpoint
over the Docker network (`http://app:8000/api/v1/ingest`) using plain `requests`.

**Why this is the right call, not just a workaround:** Airflow's job is orchestration
(when things run, retries, scheduling), not owning application logic or its dependency
tree. This is the standard production pattern — an orchestrator with a bloated,
conflicting dependency graph is fragile. It also means the app's dependencies can
evolve freely without ever touching Airflow's container.

## Airflow 3.0 architectural changes that caused confusion

1. **DAG parsing moved out of the scheduler.** In 2.x, the scheduler both parsed and
   scheduled DAGs. In 3.0, DAG parsing is a separate `dag-processor` component.
   Without it running as its own service, DAGs never appear in the UI — even though
   the scheduler logs look completely healthy and show no errors.

2. **Task execution goes through a dedicated Execution API**, not direct DB access.
   Task subprocesses authenticate to this API using a signed JWT. Each Airflow
   component auto-generates its **own random signing secret** by default. If the
   scheduler and webserver are separate containers (as in any multi-container setup),
   tokens signed by one can never be verified by the other.

3. **`airflow users create` was removed** from the CLI entirely. The default "simple
   auth manager" instead auto-generates an admin user + password on first boot,
   written to a file inside the container:
   `/opt/airflow/simple_auth_manager_passwords.json.generated`

## Issues hit, in the order we hit them

### 1. `ModuleNotFoundError: No module named 'pydantic_settings'`
Airflow's base image has none of the app's dependencies. Expected, once the
architecture above was chosen — no longer relevant after decoupling via HTTP.

### 2. SQLAlchemy version conflict when installing app deps into Airflow's image
```
apache-airflow-core 3.0.0 requires sqlalchemy<2.0,>=1.4.49, but you have sqlalchemy 2.0.54
```
Root cause of the architecture decision above. Do not install the app's full
dependency tree into Airflow's container.

### 3. `airflow users create` — invalid choice
Airflow 3.0 removed this command. Simplified `airflow-init`'s command to just
`airflow db migrate`. Credentials are auto-generated on first webserver boot instead
(see file path above).

### 4. DAG never appears in the UI ("0 Dags", "No Dags found")
Scheduler logs showed no errors, just repeating `"DAG bundles loaded: dags-folder"`
with no parsing activity. Root cause: no `dag-processor` service was running.
**Fix:** added a dedicated `airflow-dag-processor` service in `compose.yml` with
`command: dag-processor`, mounting the same `./airflow/dags` volume.

### 5. `httpcore.ConnectError: Connection refused` inside the task subprocess
Not a networking issue with the app — the task subprocess was trying to call
Airflow's own internal Execution API and couldn't reach it, because
`AIRFLOW__CORE__EXECUTION_API_SERVER_URL` was never set. **Fix:** set it explicitly
on both `airflow-webserver` and `airflow-scheduler`:
```yaml
AIRFLOW__CORE__EXECUTION_API_SERVER_URL: http://airflow-webserver:8080/execution/
```

### 6. `Could not read served logs: ... No host supplied`
Cosmetic log-viewer issue in the UI, unrelated to task success/failure. Fixed by
setting `AIRFLOW__CORE__HOSTNAME` explicitly on both webserver and scheduler to
their own container names, so the log-serving URL is built correctly.

### 7. `Invalid auth token: Signature verification failed` (HTTP 403 on task start)
The real blocker. Scheduler and webserver each auto-generated their own random JWT
signing secret, so tokens issued by one were rejected by the other.
**Fix:** set the same fixed secret on every Airflow component:
```yaml
AIRFLOW__API_AUTH__JWT_SECRET: "a-fixed-shared-secret-for-local-dev-only-change-me"
```
**Lesson:** in any distributed system where multiple processes must verify each
other's signed tokens, use one shared, explicitly-set secret — never let each
instance generate its own.

### 8. arXiv API returned `406 Not Acceptable`
Happened only from within the containerized app, not from direct browser/PowerShell
testing. `httpx`'s default headers weren't being accepted by arXiv's edge servers.
**Fix:** added an explicit `Accept: application/atom+xml` header alongside the
existing `User-Agent` header in `ArxivClient`.

## Debugging approach that worked repeatedly

When something failed inside Airflow, the fastest path to the real cause was almost
always to **bypass Airflow and test the failing call directly**:
```powershell
docker exec airflow-scheduler curl -v http://app:8000/api/v1/ingest -X POST
```
This isolated whether the problem was Airflow's own plumbing (auth, networking,
config) or the application logic itself — and avoided wasting time debugging the
wrong layer.

## Final working Airflow block (reference)

```yaml
  airflow-postgres:
    image: postgres:16-alpine
    container_name: airflow-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - airflow_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U airflow"]
      interval: 10s
      timeout: 5s
      retries: 5

  airflow-init:
    image: apache/airflow:3.0.0
    container_name: airflow-init
    depends_on:
      airflow-postgres:
        condition: service_healthy
    environment:
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-postgres:5432/airflow
    entrypoint: /bin/bash
    command: -c "airflow db migrate"

  airflow-webserver:
    image: apache/airflow:3.0.0
    container_name: airflow-webserver
    restart: unless-stopped
    depends_on:
      airflow-init:
        condition: service_completed_successfully
    environment:
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-postgres:5432/airflow
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"
      AIRFLOW__CORE__EXECUTION_API_SERVER_URL: http://airflow-webserver:8080/execution/
      AIRFLOW__CORE__HOSTNAME: airflow-webserver
      AIRFLOW__API_AUTH__JWT_SECRET: "a-fixed-shared-secret-for-local-dev-only-change-me"
    ports:
      - "8080:8080"
    volumes:
      - ./airflow/dags:/opt/airflow/dags
    command: api-server

  airflow-scheduler:
    image: apache/airflow:3.0.0
    container_name: airflow-scheduler
    restart: unless-stopped
    depends_on:
      airflow-init:
        condition: service_completed_successfully
    environment:
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-postgres:5432/airflow
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"
      AIRFLOW__CORE__EXECUTION_API_SERVER_URL: http://airflow-webserver:8080/execution/
      AIRFLOW__CORE__HOSTNAME: airflow-scheduler
      AIRFLOW__API_AUTH__JWT_SECRET: "a-fixed-shared-secret-for-local-dev-only-change-me"
    volumes:
      - ./airflow/dags:/opt/airflow/dags
    command: scheduler

  airflow-dag-processor:
    image: apache/airflow:3.0.0
    container_name: airflow-dag-processor
    restart: unless-stopped
    depends_on:
      airflow-init:
        condition: service_completed_successfully
    environment:
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-postgres:5432/airflow
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"
      AIRFLOW__CORE__EXECUTION_API_SERVER_URL: http://airflow-webserver:8080/execution/
      AIRFLOW__API_AUTH__JWT_SECRET: "a-fixed-shared-secret-for-local-dev-only-change-me"
    volumes:
      - ./airflow/dags:/opt/airflow/dags
    command: dag-processor
```

> **Note:** `AIRFLOW__API_AUTH__JWT_SECRET` is a fixed local-dev value here for
> simplicity. In any real deployment this should come from a proper secret and never
> be committed in plaintext.
