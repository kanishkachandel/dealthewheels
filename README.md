# DEALTHEWHEELS

**A fair trip allocation system for coordinating multiple transport vendors.**

DEALTHEWHEELS is a Python web application that receives trip requests and assigns each trip to an eligible vendor. Its central goal is to distribute work in line with agreed vendor shares over time, while respecting operational constraints such as cab capacity, active status, and temporary cool-off periods.

The project combines a FastAPI backend, a browser dashboard, a persistent database, reporting endpoints, and an interactive demo that explains the allocation decisions. It is designed as an educational and development project for exploring allocation logic and API-backed workflows.

## The problem it addresses

When several vendors serve the same area, dispatching every new trip to whichever vendor happens to be first in a list can create an uneven workload. A target-share policy gives each vendor a percentage of the work, but a fair dispatcher must also respond to changing eligibility: a vendor may be full, inactive, or temporarily unavailable after rejecting a trip.

This project demonstrates a deterministic way to balance those concerns. It tries to move the observed assignments toward each vendor's target share, while never assigning a trip to a vendor who is currently ineligible.

## Key concepts

| Concept | Meaning in this project |
| --- | --- |
| **Vendor** | A transport provider that can receive trips and has a cab capacity. |
| **Zone** | A distance band used to match trips with vendor share configuration. Default zones cover 0–15 km, 15–25 km, and 25 km or more. |
| **Target share** | The percentage of trips a vendor should receive for a particular zone and trip type. |
| **Trip type** | `NORMAL` or `ESCORT`. Each type is balanced as its own allocation stream. |
| **Shortfall** | The difference between the trips a vendor would be expected to receive at its target share and the trips it has actually received. |
| **Idempotency key** | A client-provided unique request key that makes retries safe from duplicate trip creation. |
| **Cool-off** | A temporary period during which a vendor that rejected a trip is not eligible for new assignments. |

## How allocation works

For each new trip, the allocator:

1. Finds vendors configured for the trip's distance zone and trip type.
2. Excludes vendors that are inactive, have no spare cab capacity, or are still in cool-off.
3. Calculates each eligible vendor's shortfall using its target percentage, the number of trips already allocated in that stream, and its actual assignments.
4. Assigns the trip to the eligible vendor with the largest shortfall. If shortfalls tie, vendor ID breaks the tie, so the same state produces a predictable decision.
5. Persists the trip and assignment in the database.

Normal and escort trips use separate totals. That means escort assignments do not change the balancing calculation for normal trips. Shortfall residue carries over across days so an imbalance is not forgotten at midnight. Eligibility and capacity take precedence over share targets: if a vendor cannot take the trip, the allocator chooses from the vendors that can.

If a request is repeated with the same idempotency key, the existing trip and assignment are returned. If an assigned vendor rejects a trip, the original cab is released, the vendor enters the configured cool-off period, and the trip is assigned again where possible. The rejection is recorded as a trip event.

## What is included

- **Trip allocation API** for submitting trips and receiving assignments.
- **Vendor and share configuration** to represent capacity and target percentages by zone and trip type.
- **Dashboard** for viewing the project through a browser.
- **Rejection and reallocation flow** with vendor cool-off handling.
- **Share reports** comparing target share, actual share, expected trips, and running shortfall for a date or month.
- **Guided demo scenarios** for allocations, escort streams, capacity limits, rejection, carry-forward, reporting, determinism, concurrency, and convergence.
- **Health and metrics endpoints** for basic service monitoring and Prometheus-format metrics.
- **SQLite local setup** and an optional Docker Compose setup using PostgreSQL and Redis.
- **Automated tests** covering application behavior.

## Guided demo

The dashboard's demo area walks through real API calls and the same allocation service used by trip requests. It can set up three demo vendors with target shares of 50%, 30%, and 20%, then show how decisions change as trips arrive and vendor conditions change.

Demo trips use a dedicated 900–999 km zone and an `interview-` idempotency-key prefix. The demo reset operation targets its own generated data so ordinary trips are not part of the demo cleanup. The scenarios are useful for seeing the policy in action; they do not replace the API's persistence or allocation behavior with mock results.

## Technology and architecture

- **Backend:** Python, FastAPI, Pydantic, and SQLAlchemy.
- **Frontend:** static HTML, CSS, and JavaScript served by the application.
- **Database:** SQLite by default; PostgreSQL can be used through Docker Compose or a configured database URL.
- **Cache:** optional Redis cache for running totals. The database remains authoritative, and the application can run when Redis is unavailable.
- **Authentication:** bearer tokens using JWT; administrator-only operations include vendor management, reports, and demo controls.
- **Observability:** health response at `/actuator/health` and Prometheus metrics at `/actuator/metrics`.

### Request flow

```text
Browser or API client
        │
        ▼
 FastAPI routes ── authentication and input validation
        │
        ├── trip service ── idempotency and zone lookup
        │                    │
        │                    ▼
        │               fair allocator ── eligibility and shortfall ranking
        │                    │
        ▼                    ▼
    reports and demo     SQLAlchemy models
                             │
                             ▼
                    SQLite or PostgreSQL
```

The source is organized by responsibility: `app/api/` defines routes, `app/services/` contains business operations such as allocation and reporting, `app/models/` defines persisted entities, and `app/schemas/` defines request and response shapes. The dashboard lives in `dashboard/`.

## API overview

Interactive request and response documentation is available at `/docs` when the service is running. Most application routes require a bearer token. Health and metrics are public.

| Route | Method | Purpose |
| --- | --- | --- |
| `/api/auth/login` | `POST` | Authenticate and receive an access token |
| `/api/zones` | `GET` | List configured distance zones |
| `/api/vendors` | `POST` | Create a vendor and its target shares (administrator) |
| `/api/trips` | `POST` | Submit a trip for allocation |
| `/api/trips/{trip_id}/reject` | `POST` | Reject and reallocate an assigned trip |
| `/api/reports/share` | `GET` | Compare target and actual allocation shares (administrator) |
| `/api/demo/*` | Various | Set up, run, and inspect guided demo scenarios (administrator) |
| `/actuator/health` | `GET` | Check service health |
| `/actuator/metrics` | `GET` | Read Prometheus-format metrics |

Trip requests specify a positive `distance_km`, a `trip_type` (`NORMAL` or `ESCORT`), and an `idempotency_key`. Share reports accept either a date (`YYYY-MM-DD`) or a month (`YYYY-MM`) and can be filtered by zone and trip type.

## Project structure

```text
app/
  api/             HTTP routes and authentication dependencies
  core/            Application settings, security, and shared exceptions
  db/              Database setup and schema upgrades
  models/          SQLAlchemy data models
  schemas/         Validated API request and response models
  services/        Allocation, trips, reports, caching, and demo scenarios
dashboard/         Browser dashboard assets
postman/           Postman collection for exploring the API
scripts/           Utility scripts, including a load-test client
tests/             Automated test suite
demo.sh            Local demo launcher
Dockerfile         API container definition
docker-compose.yml API, PostgreSQL, and Redis services
requirements.txt   Python dependencies
```

## Quick start

The simplest local setup uses SQLite and does not require Docker or Redis. The launcher creates a Python virtual environment, installs the dependencies, starts the API, and opens the browser.

On Windows, use **Git Bash** in the VS Code terminal:

```bash
./demo.sh
```

On macOS or Linux:

```bash
chmod +x demo.sh
./demo.sh
```

Open the dashboard at [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/), or explore the API at [http://localhost:8000/docs](http://localhost:8000/docs). Stop the server with **Ctrl+C** in the terminal running the launcher.

For a container-based setup with PostgreSQL and Redis, use `docker compose up --build`.

## Local demo account and configuration

On a fresh local database, the application creates this development administrator:

| Username | Password |
| --- | --- |
| `admin` | `admin123` |

Settings may be supplied in a `.env` file. The standard local defaults are:

| Setting | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `DEALTHEWHEELS` | Application title |
| `DATABASE_URL` | `sqlite:///./dealthewheels.db` | Database connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Optional cache connection |
| `JWT_SECRET` | `development-secret-change-me` | Token signing key |
| `JWT_ALGORITHM` | `HS256` | Token signing algorithm |
| `TOKEN_EXPIRY_MINUTES` | `480` | Access-token lifetime |
| `COOLOFF_MINUTES` | `15` | Vendor cool-off after rejection |

The default credentials and JWT key are for local development only. Replace them before any shared or public deployment; this repository does not claim production readiness.

## Tests

Run the automated test suite from the project environment with:

```bash
python -m pytest
```

## Current scope and limitations

- This is a demonstration and development application, not a hosted dispatch service.
- Its built-in administrator credentials and JWT key are development defaults.
- SQLite is convenient for local use; production concurrency, migrations, secrets, and operational requirements need deployment-specific configuration and review.
- Redis is optional and is not required for the core trip allocation flow.
- No license file is currently included. Contact the repository owner before redistributing or reusing the project.
