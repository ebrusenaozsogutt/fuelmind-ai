# FuelMind AI

FuelMind AI is an industrial decision-support prototype for monitoring fuel-station operations. It combines a stateful, physically related data simulation with real-time monitoring, anomaly scenarios, data-quality evaluation, and rule-based alarms.

The current implementation covers the operational foundation through Stage 7. Machine-learning anomaly detection, demand forecasting, and order planning are explicitly planned work, not current product capabilities.

## Overview

FuelMind AI models the station domain across tanks, pumps, sales, deliveries, and sensor readings. When field telemetry is not available, its simulation engine produces reproducible operational data whose values remain related to tank state, sales activity, and pump behaviour rather than being independent random samples.

The system exposes management and simulation workflows through a FastAPI REST API, streams live events over WebSocket, persists operational history in PostgreSQL, and provides a .NET 8 WPF client for login, monitoring, simulation control, charts, and alarm handling.

## Current Project Status

- [x] **Stage 1 — System design:** client-server architecture, REST/WebSocket design, and data-source abstraction.
- [x] **Stage 2 — Backend foundation:** PostgreSQL, SQLAlchemy, Alembic, authentication, authorization, CRUD, and domain validation.
- [x] **Stage 3 — Simulation core:** deterministic, stateful, tick-based station simulation.
- [x] **Stage 4 — Runner and persistence:** simulation lifecycle, durable ticks, batch processing, recovery, and dataset generation.
- [x] **Stage 5 — Live data:** station WebSocket channels, sequencing, heartbeat, reconnect support, and history backfill.
- [x] **Stage 6 — Desktop client:** .NET 8 WPF/MVVM monitoring and simulation-control client.
- [x] **Stage 7 — Scenarios and alarms:** scenario scheduling, data-quality scoring, rule-based alarms, and desktop alarm centre.
- [ ] **Stage 8 — Planned:** Isolation Forest, feature engineering, hybrid rule + AI detection, explainability, and model registry workflows.
- [ ] **Stage 9 — Planned:** seven-day demand forecasting, XGBoost regression, accuracy metrics, safety stock, and order recommendations.
- [ ] **Stage 10 — Planned:** daily summaries, PDF/CSV reporting, packaging, final integration, and release validation.

## Key Features

- Stateful, seed-based simulation with realtime, accelerated, and dataset modes.
- REST API for authentication, master data, simulation lifecycle, live history, and alarms.
- Station-scoped WebSocket streaming for simulation ticks and live events.
- PostgreSQL persistence with Alembic migrations and transactional tick persistence.
- .NET 8 WPF desktop client using MVVM, LiveCharts2, HTTP, and `ClientWebSocket`.
- Live tank and pump monitoring, including levels, flow, pressure, motor current, and temperature.
- Scenario CRUD and scheduling for seven controlled abnormal-behaviour scenarios.
- Rule-based alarm detection, lifecycle management, de-duplication, and data-quality scoring.
- Historical dataset generation for 30-, 60-, and 90-day simulation windows.

## System Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         C# WPF Desktop Client                        │
│ Login · MVVM · LiveCharts2 · LiveDataStore · Alarm Center            │
└───────────────────────┬───────────────────────────┬──────────────────┘
                        │ REST/HTTPS                 │ WebSocket
                        ▼                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                            FastAPI Backend                            │
│ Auth & CRUD · Simulation API · Live History · Alarm Lifecycle         │
├─────────────────┬──────────────────┬────────────────┬────────────────┤
│ Simulation      │ Scenario Engine  │ Alarm & Quality │ Live Layer     │
│ Runner/Tick     │ Scheduled faults │ Rule evaluation │ Broker/WS      │
└─────────────────┴──────────────────┴────────────────┴────────────────┘
                                    │
                                    ▼
                         PostgreSQL + Alembic
```

```text
SimulationRunner → TickEngine → tank / pump / sales data
                 → transactional PostgreSQL persistence → WebSocket → WPF → LiveCharts2

ScenarioEngine → altered sensor or equipment behaviour → rule engine → alarm → WPF Alarm Center
```

## Technology Stack

| Layer | Technologies |
| --- | --- |
| Desktop | C#, .NET 8, WPF, XAML, MVVM, CommunityToolkit.Mvvm, LiveCharts2 |
| Backend | Python, FastAPI, Uvicorn, Pydantic, asyncio |
| Data | PostgreSQL, SQLAlchemy, Alembic, psycopg |
| Realtime | WebSocket, `ClientWebSocket`, HTTP client |
| Quality | pytest, pytest-asyncio, HTTPX, Ruff, .NET build/tests |
| Version control | Git, GitHub |

## Simulation Engine

The simulation is not a script that emits unrelated random values. It is stateful and tick-based: one `SimulationClock` advances a `StationSimulationState` containing tank, pump, and active-sale state. A seeded `RandomSource` makes a run reproducible.

Pump state, sales, tank quantities, and sensor readings are generated as related operating signals. In particular, the model retains both `true_level_liters` and `measured_level_liters`, enabling realistic sensor and leak scenarios. Simulation runs support `REALTIME`, `ACCELERATED`, and `DATASET` modes.

## Real-Time Data Flow

REST and WebSocket are deliberately separate:

- **REST** handles CRUD, authenticated commands, simulation lifecycle, and historical data.
- **WebSocket** delivers station-scoped live ticks, connection events, and heartbeat traffic.

The `SimulationRunner` is independent of connected clients: a WebSocket disconnect does not stop a run or persistence. The client reconnects automatically; persisted sensor history can backfill missed data, while sequence tracking and ping/pong heartbeat help identify connection gaps and stale sockets.

## Anomaly Scenario Engine

Scenarios are persisted per simulation run, target a station, tank, or pump where applicable, and are applied by the `ScenarioEngine`.

| Scenario | Effect |
| --- | --- |
| Pump flow drop | Reduces flow and pressure; motor current increases. |
| Motor current increase | Raises motor current and temperature; can increment pump errors. |
| Tank leak / sales-level mismatch | Withdraws physical tank volume, creating an operational mismatch. |
| Sensor stuck | Holds the measured tank level while the true level can change. |
| Sensor spike | Produces an elevated measured tank-level reading. |
| Water-level increase | Gradually raises the tank water-level signal. |
| Demand surge | Applies a higher demand multiplier to the station. |

## Alarm and Data Quality

The current alarm layer is rule-based. It evaluates monitoring rules against persisted readings, including `data_quality_score` and quality flags. Alarm creation is de-duplicated to reduce alarm floods and supports this lifecycle:

`NEW` → `ACKNOWLEDGED` → `INVESTIGATING` → `RESOLVED` (or `FALSE_POSITIVE`)

Live alarms are available to the desktop alarm centre. AI-based Isolation Forest detection is not implemented yet; see the roadmap.

## Database

The PostgreSQL schema is organised around these domain areas:

| Area | Tables |
| --- | --- |
| Core | `users`, `stations`, `fuel_types`, `tanks`, `pumps` |
| Operational | `sales`, `sensor_readings`, `deliveries` |
| Alarm / future AI schema | `alarms`, `forecasts`, `order_recommendations`, `model_versions` |
| Simulation | `simulation_runs`, `simulation_scenarios`, `simulation_events` |

The forecasting and model-version tables exist in the schema, but the Stage 8–9 AI and forecasting workflows are planned rather than implemented.

## API

Swagger UI in local development: <http://127.0.0.1:8000/docs>

Representative endpoints:

| Area | Endpoints |
| --- | --- |
| Auth | `POST /api/auth/login`, `GET /api/auth/me` |
| Simulations | `POST /api/simulations`, `POST /api/simulations/{run_id}/start`, `POST /api/simulations/{run_id}/pause`, `POST /api/simulations/{run_id}/resume`, `POST /api/simulations/{run_id}/stop` |
| Live | `GET /api/stations/{station_id}/live-status`, `GET /api/stations/{station_id}/sensor-history`, `WS /api/ws/stations/{station_id}/live` |
| Alarms | `GET /api/alarms`, `PATCH /api/alarms/{id}/acknowledge`, `PATCH /api/alarms/{id}/investigate`, `PATCH /api/alarms/{id}/resolve` |

## Project Structure

```text
fuelmind-ai/
├── backend/
│   ├── app/                 # API, models, services, simulation, live layer
│   ├── migrations/          # Alembic migrations
│   ├── scripts/             # Demo and dataset helper scripts
│   ├── tests/               # Backend unit and integration tests
│   ├── .env.example
│   ├── alembic.ini
│   └── requirements.txt
├── desktop/
│   ├── FuelMind.Desktop/    # .NET 8 WPF client
│   ├── FuelMind.Desktop.Tests/
│   └── FuelMind.sln
├── docs/
├── data/
├── reports/
├── tests/
└── trained_models/
```

## Installation

### Prerequisites

- Python 3
- PostgreSQL
- .NET 8 SDK
- Git

### Backend (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure the local `.env` from the provided template with your own PostgreSQL connection and development secrets. Do not commit it.

Create the database named `fuelmind_db` and then apply migrations:

```powershell
alembic upgrade head
```

Start the API:

```powershell
uvicorn app.main:app --reload --workers 1
```

`--workers 1` is required for the current development architecture because active simulation state is held in process memory.

### Desktop client

```powershell
cd desktop\FuelMind.Desktop
dotnet restore
dotnet build
dotnet run
```

## Running the Demo

1. Start PostgreSQL and create/configure your local `fuelmind_db` connection in `backend/.env`.
2. Activate the backend virtual environment.
3. Run `alembic upgrade head` from `backend`.
4. Optionally configure development-only demo users in `.env`, then run `python -m app.seed`.
5. Start the backend with Uvicorn.
6. Start the WPF client and sign in.
7. Create and start a simulation from the client.
8. Open live monitoring to observe tank and pump metrics.
9. Create a scenario for the run and observe the live graph and alarm centre.

## Testing

From `backend` with the virtual environment active:

```powershell
pytest
ruff check .
```

Build the desktop solution:

```powershell
cd desktop
dotnet build FuelMind.sln
dotnet test .\FuelMind.Desktop.Tests\FuelMind.Desktop.Tests.csproj
```

The repository includes backend unit/integration tests and a WPF `RingBuffer` test project. No fixed test count is stated here because it should be taken from the current test run.

## Reliability Design

- A client disconnect does not stop the simulation runner.
- The WPF client uses automatic reconnect and a bounded `RingBuffer` for chart memory.
- REST history supports backfill after a live connection gap.
- Live messages use sequence tracking and ping/pong heartbeat handling.
- Tick persistence is transactional and validates sequence ordering.
- Startup recovery handles interrupted simulation runs.

## Roadmap

**Stage 8 — Anomaly intelligence:** Isolation Forest, feature engineering, risk scoring, hybrid rule + AI detection, explainability, and model registry capabilities.

**Stage 9 — Forecasting and planning:** seven-day fuel-demand forecasting, baseline and XGBoost models, MAE/RMSE/MAPE evaluation, critical-stock dates, safety stock, and recommended order quantity/date.

**Stage 10 — Delivery:** daily AI summaries, PDF/CSV reports, end-to-end integration, packaging, `dotnet publish`, and final test/release work.

## Future Real Device Integration

FuelMind AI is designed around a data-source abstraction rather than a single telemetry origin: `SIMULATION`, `CSV_IMPORT`, `REAL_DEVICE`, and `MANUAL`.

A future Mepsan device or sensor integration can be introduced through a data-adapter/ingestion layer. The established PostgreSQL, alarm, future AI, REST, WebSocket, and WPF layers can remain in place while the source adapter changes.

## Security

- JWT authentication with `ADMIN` and `OPERATOR` roles.
- Backend-side authorization checks for protected operations.
- Local secrets are configured through `.env`; environment files are not committed.

## Academic Context

FuelMind AI is an industrial decision-support and learning prototype. It is not represented as a production deployment or an official commercial system. No license is currently declared in this repository.
