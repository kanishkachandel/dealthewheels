# DEALTHEWHEELS

**A local demo of fair trip allocation for a multi-vendor dispatch system.**

DEALTHEWHEELS is a small FastAPI application with a browser dashboard. It accepts trip requests, chooses an eligible vendor using configurable target shares, and records the result in a database. The project also includes guided scenarios so you can see how the allocator behaves when vendors have different shares, reject trips, or reach capacity.

> **For local demonstration and development.** The default account and signing key are intentionally easy to use. Do not expose this app to the public internet or use the defaults for a real service.

## What you can do

- Open the dashboard and create or inspect trips.
- Allocate trips among vendors according to their target shares.
- See capacity, vendor eligibility, and allocation outcomes.
- Try guided scenarios for normal and escort trips, rejection and reallocation, capacity limits, reports, and concurrent requests.
- Inspect the API interactively through FastAPI's Swagger page.

## Run it on Windows

The included `demo.sh` is a Bash script. In VS Code, run it from a **Git Bash** terminal, not PowerShell.

1. Open the project folder in VS Code: `D:\kanishkaaaa\kanishkaaaa`.
2. Open **Terminal → New Terminal**.
3. Use the terminal profile dropdown and choose **Git Bash**. If Git Bash is not listed, install Git for Windows, then restart VS Code.
4. In Git Bash, run:

   ```bash
   ./demo.sh
   ```

On first run, the script creates a `.venv`, installs the Python packages, starts the API, waits for its health check, and opens the app in your browser. Keep that terminal open while using the app. Press **Ctrl+C** in it to stop the server.

If your terminal is PowerShell, `./demo.sh` is not the right way to launch a Bash script. Switch the terminal profile to Git Bash first. For a Git Bash terminal that opens in a different folder, move into the project with:

```bash
cd /d/kanishkaaaa/kanishkaaaa
```

The `/d/...` form is Git Bash path syntax; in PowerShell, the equivalent folder is `D:\kanishkaaaa\kanishkaaaa`.

## Run it on macOS or Linux

Open a terminal in the project folder and run:

```bash
chmod +x demo.sh
./demo.sh
```

Python 3.10 or newer is recommended. The launcher creates a virtual environment and installs `requirements.txt` when needed.

## Open the app

When the server is running, use:

| Page | Address | Purpose |
| --- | --- | --- |
| Dashboard | [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/) | Main browser interface |
| API documentation | [http://localhost:8000/docs](http://localhost:8000/docs) | Try API requests with Swagger UI |
| Health check | [http://localhost:8000/actuator/health](http://localhost:8000/actuator/health) | Check whether the API is responding |
| Metrics | [http://localhost:8000/actuator/metrics](http://localhost:8000/actuator/metrics) | Prometheus-format application metrics |

The health and metrics pages return data rather than a designed web page. That is expected: they are service endpoints, not dashboard screens.

## Sign in

For a fresh local database, the app creates this development administrator account:

| Username | Password |
| --- | --- |
| `admin` | `admin123` |

Use it to explore the dashboard's administrator features and demo scenarios. Change or replace the credentials and JWT secret before any non-demo deployment. If you already have a database with an `admin` user, startup does not overwrite that user's password.

## Try the guided demo

Open **Demo** in the dashboard and follow its setup and scenario steps. The scenarios call the application's real API and allocation service; they are not just mock screens. The demo uses its own 900–999 km distance zone and marks its generated trips with an `interview-` idempotency key prefix. Its reset action is intended to clean up those demo trips without deleting unrelated trips.

The allocator tracks each trip type independently. For each incoming trip, it calculates each eligible vendor's shortfall from its target share and selects the vendor with the largest shortfall. A tie is resolved by vendor ID for repeatable results. Vendors must be active, have spare cab capacity, and be outside their cool-off period to be eligible. Repeating a request with the same idempotency key returns the existing assignment instead of creating a duplicate.

When a vendor rejects a trip, the original cab is freed, a cool-off period is applied, and the trip is offered again. Allocation shortfalls carry over between days so the system can correct earlier imbalances over time.

## API overview

The complete request and response schemas are available at `/docs` while the server is running. Most application routes require a bearer token obtained from the login route; health and metrics are public.

| Route | Method | Description |
| --- | --- | --- |
| `/api/auth/login` | `POST` | Sign in and obtain an access token |
| `/api/zones` | `GET` | List trip distance zones (authenticated) |
| `/api/vendors` | `POST` | Create a vendor (administrator) |
| `/api/trips` | `POST` | Submit a trip for allocation (authenticated) |
| `/api/trips/{trip_id}/reject` | `POST` | Reject an assigned trip and reallocate (authenticated) |
| `/api/reports/share` | `GET` | View allocation share by date or month (administrator) |
| `/api/demo/*` | Various | Run or inspect the guided demo (administrator) |
| `/actuator/health` | `GET` | Service health response (public) |
| `/actuator/metrics` | `GET` | Prometheus-format metrics (public) |

Trip requests include a positive `distance_km`, a `trip_type` (`NORMAL` or `ESCORT`), and an `idempotency_key`. Reports accept either a `date` (`YYYY-MM-DD`) or `month` (`YYYY-MM`), with optional zone and trip-type filters.

## How it is put together

- **API:** Python and FastAPI, starting at `app/main.py`.
- **Dashboard:** static HTML, CSS, and JavaScript served by the application from `dashboard/`.
- **Database:** SQLite by default, stored locally as `dealthewheels.db`.
- **Optional cache:** Redis. The database remains the source of truth; the app continues without Redis.
- **Containers:** `Dockerfile` and `docker-compose.yml` provide an alternative setup with PostgreSQL and Redis.

Distance zones are seeded for 0–15 km, 15–25 km, and 25 km or more. The application also seeds the initial configuration on startup when needed.

## Optional Docker setup

If Docker Desktop is installed and running, start the API with PostgreSQL and Redis using:

```bash
docker compose up --build
```

Then open the dashboard at [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/). Stop the services with **Ctrl+C**, then run `docker compose down` to remove the containers. The Docker Compose JWT secret is a placeholder for local use; replace it before any shared or deployed use.

## Configuration

Settings can be supplied in a `.env` file in the project directory. Defaults are suitable only for a local demo.

| Setting | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `DEALTHEWHEELS` | Application title |
| `DATABASE_URL` | `sqlite:///./dealthewheels.db` | SQLAlchemy database connection URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Optional Redis connection URL |
| `JWT_SECRET` | `development-secret-change-me` | Secret used to sign login tokens; replace outside a local demo |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `TOKEN_EXPIRY_MINUTES` | `480` | Login token lifetime |
| `COOLOFF_MINUTES` | `15` | Vendor cool-off after rejecting a trip |

If Redis is not running, the application skips cache operations and continues using the database.

## Project layout

```text
app/              FastAPI routes, models, allocation services, and database setup
dashboard/        Browser dashboard assets
postman/          Postman collection for API exploration
scripts/          Utility scripts, including a load-test client
tests/            Automated test suite
demo.sh           Local one-command launcher
Dockerfile        API container definition
docker-compose.yml  Local API, PostgreSQL, and Redis services
requirements.txt  Python dependencies
```

## Tests

The repository includes pytest tests. With the project environment installed, run:

```bash
python -m pytest
```

## Troubleshooting

**`./demo.sh` returns immediately or does nothing in VS Code**  
Check the selected terminal profile. It must be **Git Bash** for this script. In PowerShell, choose Git Bash from the terminal profile menu and run the command again.

**The browser does not open automatically**  
Wait for the terminal to report that the service is healthy, then open [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/) yourself.

**The health check does not respond**  
Keep the launcher terminal open and look for a Python error during startup. If port 8000 is already in use, stop the other app using it or set a different `PORT` before starting the script.

**Health and metrics show plain text or JSON**  
That is the expected response format for monitoring endpoints. Use `/dashboard/` for the visual interface.

**A demo action says unauthorized**  
Sign in with the local administrator account and retry the action.

## License

No license file is currently included. Contact the repository owner before redistributing or reusing this project.
