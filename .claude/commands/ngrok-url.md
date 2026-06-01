# Get ngrok Public URL

Retrieve the current active ngrok HTTPS tunnel URL for sharing with the client.

```bash
curl -s http://localhost:4040/api/tunnels | python3 -c "import sys,json; t=json.load(sys.stdin)['tunnels']; print([x['public_url'] for x in t if 'https' in x['public_url']][0])"
```

If ngrok is not running, start it with:
```bash
ngrok http 5173
```

When you get the URL, tell the user:
1. The HTTPS link to share with Corey & Cody
2. Remind them that visitors will see an ngrok interstitial page — they need to click "Visit Site" to proceed
3. Both frontend (port 5173) AND backend (port 8000) must be running for the calculator to work
