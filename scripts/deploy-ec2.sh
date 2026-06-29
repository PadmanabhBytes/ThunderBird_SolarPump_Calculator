#!/usr/bin/env bash
# Full EC2 setup script — run once on a fresh Ubuntu 22.04 instance.
# Installs Docker, builds the frontend, and starts all services.
#
# Usage (as ubuntu user with sudo):
#   bash scripts/deploy-ec2.sh
#
# After this script completes, run:
#   bash scripts/init-letsencrypt.sh <your-domain> <your-email>

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=== [1/5] Installing system packages ==="
sudo apt-get update -y
sudo apt-get install -y git curl ca-certificates gnupg lsb-release

echo "=== [2/5] Installing Docker ==="
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  echo "Docker installed. You may need to log out and back in for group changes."
else
  echo "Docker already installed: $(docker --version)"
fi

# Ensure Docker Compose V2 is available
if ! docker compose version &>/dev/null; then
  sudo apt-get install -y docker-compose-plugin
fi

echo "=== [3/5] Installing Node 20 ==="
if ! command -v node &>/dev/null || [[ "$(node -v)" != v20* ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
echo "Node: $(node -v) | npm: $(npm -v)"

echo "=== [4/5] Building React frontend ==="
cd "$REPO_DIR/frontend"
npm ci
npm run build
cd "$REPO_DIR"
echo "Frontend built → frontend/dist/"

echo "=== [5/5] Starting services ==="
# Ensure .env exists
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo ""
    echo "  !! .env created from .env.example — EDIT IT NOW and add your NREL_API_KEY !!"
    echo "     nano .env"
    echo ""
    read -rp "Press Enter after you have saved the .env file..."
  else
    echo "ERROR: .env file missing. Create it with NREL_API_KEY=<your-key>"
    exit 1
  fi
fi

# Create certbot dirs if not present (nginx needs them to start)
mkdir -p data/certbot/conf data/certbot/www

docker compose up -d --build

echo ""
echo "=== Services are running ==="
docker compose ps
echo ""
echo "Next step → obtain HTTPS cert:"
echo "  bash scripts/init-letsencrypt.sh <your-duckdns-domain> <your-email>"
echo ""
echo "Example:"
echo "  bash scripts/init-letsencrypt.sh thunderbirdsolar.duckdns.org admin@yourdomain.com"
