# Check Server Status

Check whether the backend (port 8000), frontend (port 5173), and ngrok are running.

Run all three checks:

```bash
echo "=== Backend (port 8000) ===" && curl -s --max-time 2 http://localhost:8000/ > /dev/null && echo "RUNNING" || echo "NOT RUNNING"
```

```bash
echo "=== Frontend (port 5173) ===" && curl -s --max-time 2 http://localhost:5173/ > /dev/null && echo "RUNNING" || echo "NOT RUNNING"
```

```bash
echo "=== ngrok ===" && curl -s --max-time 2 http://localhost:4040/api/tunnels | python3 -c "import sys,json; t=json.load(sys.stdin)['tunnels']; print('RUNNING →', [x['public_url'] for x in t if 'https' in x['public_url']][0])" 2>/dev/null || echo "NOT RUNNING"
```

Report the status of each clearly. If anything is not running, tell the user which command to run to start it.
