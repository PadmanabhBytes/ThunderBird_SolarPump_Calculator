#!/usr/bin/env bash
# One-time script: obtains a Let's Encrypt cert and switches nginx to HTTPS.
# Run from the repo root AFTER docker-compose is up.
#
# Usage:
#   bash scripts/init-letsencrypt.sh <domain> <email>
# Example:
#   bash scripts/init-letsencrypt.sh thunderbirdsolar.duckdns.org admin@example.com

set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"

if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
  echo "Usage: $0 <domain> <email>"
  exit 1
fi

CERT_DIR="./data/certbot/conf"
WWW_DIR="./data/certbot/www"

echo ">>> Ensuring certbot directories exist..."
mkdir -p "$CERT_DIR" "$WWW_DIR"

# Download recommended TLS parameters from Let's Encrypt if not already present
if [ ! -f "$CERT_DIR/options-ssl-nginx.conf" ]; then
  echo ">>> Downloading TLS options..."
  curl -fsSL https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
    -o "$CERT_DIR/options-ssl-nginx.conf"
fi
if [ ! -f "$CERT_DIR/ssl-dhparams.pem" ]; then
  echo ">>> Downloading DH params..."
  curl -fsSL https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
    -o "$CERT_DIR/ssl-dhparams.pem"
fi

echo ">>> Obtaining certificate for $DOMAIN..."
docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN"

echo ">>> Writing HTTPS nginx config..."
cat > ./nginx/default.conf << NGINXCONF
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name ${DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # API requests → FastAPI backend
    location /api/ {
        proxy_pass         http://backend:8000;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }

    # React frontend (SPA — all unknown paths serve index.html)
    location / {
        root       /usr/share/nginx/html;
        index      index.html;
        try_files  \$uri \$uri/ /index.html;
    }
}
NGINXCONF

echo ">>> Reloading nginx..."
docker compose exec nginx nginx -s reload

echo ""
echo "✓ Done. Your app is live at: https://${DOMAIN}"
