# Solar Pump Calculator — Backend API

Production-grade FastAPI backend for engineering-level solar pump system sizing and recommendation.

## Architecture

```
solar_pump_calculator/
├── app/
│   ├── main.py                      # App factory, lifespan, CORS
│   ├── config.py                    # Pydantic-Settings + .env
│   ├── dependencies.py              # FastAPI DI container
│   ├── controllers/
│   │   └── calculation_controller.py
│   ├── services/
│   │   ├── tdh_service.py           # Total Dynamic Head engine
│   │   ├── friction_service.py      # Hazen-Williams formula
│   │   ├── interpolation.py         # Numerical interpolation utilities
│   │   ├── pump_eval_service.py     # Pump eligibility filter
│   │   ├── solar_service.py         # Solar array sizing
│   │   └── ranking_service.py       # Scoring & recommendation
│   ├── repositories/
│   │   ├── friction_repository.py   # CSV → memory (DB-ready interface)
│   │   └── pump_repository.py       # CSV → memory (DB-ready interface)
│   ├── models/
│   │   ├── pump.py
│   │   ├── calculation_request.py
│   │   └── calculation_response.py
│   └── utils/
│       ├── logger.py
│       └── exceptions.py
├── data/
│   ├── friction/hazen_williams.csv  # Pipe material C-values
│   └── pumps/pump_catalog.csv       # 20-pump reference catalog
├── requirements.txt
└── .env
```

## Calculation Pipeline

```
CalculationRequest
       │
       ▼
 TDH Service
  ├─ Static Head = Dynamic WL + Discharge Head
  ├─ Friction Loss (Hazen-Williams)
  ├─ Minor Losses = factor × Friction
  └─ TDH = subtotal × safety_factor
       │
       ▼
 Solar Service
  ├─ Hydraulic Power = ρ·g·Q·H
  ├─ Pump Input Power = Hydraulic / η_pump
  └─ Solar Array = Input / (1 − system_losses)
       │
       ▼
 Pump Eval Service          Pump Repository (CSV)
  └─ Filter: max_head ≥ TDH AND max_flow ≥ required_flow
       │
       ▼
 Ranking Service
  ├─ Efficiency score  (40%)
  ├─ Power match score (35%)
  └─ Head margin score (25%)
       │
       ▼
 CalculationResponse  (ranked recommendations + warnings)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/calculations/recommend` | Full pipeline — TDH → solar → ranked pumps |
| `POST` | `/api/v1/calculations/tdh` | TDH + pipe velocity only |
| `POST` | `/api/v1/calculations/solar` | Solar sizing only |
| `GET`  | `/api/v1/calculations/pumps` | List pump catalog |
| `GET`  | `/api/v1/calculations/pumps/{id}` | Single pump detail |
| `GET`  | `/api/v1/calculations/materials` | Pipe materials + C-values |
| `GET`  | `/health` | Liveness probe |
| `GET`  | `/docs` | Swagger UI |
| `GET`  | `/redoc` | ReDoc UI |

## Quick Start

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the API
uvicorn app.main:app --reload --port 8000
```

Then open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger UI.

## Example Request

```bash
curl -X POST http://localhost:8000/api/v1/calculations/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "static_water_level_m": 18.0,
    "dynamic_water_level_m": 24.0,
    "discharge_head_m": 6.0,
    "required_flow_lpm": 120.0,
    "daily_water_demand_liters": 6000.0,
    "pipe_diameter_mm": 50.0,
    "pipe_length_m": 90.0,
    "pipe_material": "PVC",
    "peak_sun_hours": 5.5,
    "panel_wattage_w": 400.0
  }'
```

## Future: Database Integration

Repositories (`FrictionRepository`, `PumpRepository`) are designed for a clean DB swap:
- Public interface is identical regardless of data source
- Replace the `load()` body with async SQLAlchemy / Supabase queries
- `app.state` singletons map naturally to connection-pool managed sessions
- `DATABASE_URL` and `USE_DATABASE` flags are already wired in `.env`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `DEBUG` | `false` | Enable debug mode |
| `API_PREFIX` | `/api/v1` | URL prefix for all routes |
| `FRICTION_DATA_PATH` | `data/friction/hazen_williams.csv` | Pipe C-value dataset |
| `PUMP_DATA_PATH` | `data/pumps/pump_catalog.csv` | Pump catalog |
| `DEFAULT_PUMP_EFFICIENCY` | `0.45` | Conservative pump efficiency fallback |
| `DEFAULT_SAFETY_FACTOR` | `1.15` | TDH safety multiplier |
| `DATABASE_URL` | *(empty)* | PostgreSQL/Supabase connection string |
