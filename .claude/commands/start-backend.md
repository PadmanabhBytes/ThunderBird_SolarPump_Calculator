# Start Backend Server

Kill any running uvicorn process and start the FastAPI backend fresh.

```bash
pkill -f "uvicorn app.main" 2>/dev/null; sleep 1; cd /Users/consultadd/Downloads/Thunderbird-SolarPumps/solar_pump_calculator && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run this in the background. After 3 seconds, verify it's up:
```bash
curl -s http://localhost:8000/api/v1/calculations/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/
```

Tell the user the backend is running at http://localhost:8000 and the API docs are at http://localhost:8000/docs
