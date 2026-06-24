# MB Quant Deployment

## Deployment split

- GitHub Actions mail job stays as-is: `.github/workflows/mb.yml` runs `mb_main.py` with the root `requirements.txt`
- Web server deployment is separate: install only `backend/requirements.txt`, build the frontend, and run the FastAPI service
- Domain for the web server is `gilgop.cloud`

## 1. Shared Caddy on existing 80/443

Use this when another stack already owns public `80/443` on the same server and you want `gilgop.cloud` routed through that existing Caddy instance.

This repository now includes:

- `Dockerfile`: builds the React frontend and serves it from FastAPI
- `deploy/docker-compose.shared-caddy.yml`: runs the app on internal port `8000` only
- `deploy/Caddyfile.gilgop.cloud`: site block to add to the existing Caddy gateway

### MB Quant container

```bash
cd /var/www/mb-quant
docker compose -f deploy/docker-compose.shared-caddy.yml up -d --build
```

Notes:

- No host `80/443` ports are published from this compose file
- The service joins the external Docker network `starterkit-prod_internal` by default
- If your shared Caddy network name is different, set `CADDY_SHARED_NETWORK=<network-name>`

### Existing Caddy gateway

Add the contents of `deploy/Caddyfile.gilgop.cloud` to the already running Caddy instance that owns public `80/443`.

```caddy
www.gilgop.cloud {
    redir https://gilgop.cloud{uri} permanent
}

gilgop.cloud {
    encode zstd gzip
    reverse_proxy mb-quant-web:8000
}
```

Then reload the existing Caddy stack. Example, if the gateway is the Starter Kit project:

```bash
cd "/Users/sonmyeong-gwan/Desktop/One Dollar Project Starter Kit "
docker compose --env-file infra/compose/env.production -f infra/compose/docker-compose.prod.yml exec caddy caddy reload --config /etc/caddy/Caddyfile
```

Quick checks:

```bash
docker compose -f deploy/docker-compose.shared-caddy.yml ps
docker network inspect starterkit-prod_internal
curl -I https://gilgop.cloud/healthz
```

### Telegram bot with shared Caddy deployment

The Telegram bot is a separate process that calls the MB Quant API. Create a new bot
with BotFather, then run the compose profile:

```bash
cd /var/www/mb-quant
export TELEGRAM_BOT_TOKEN="123456:replace-with-new-bot-token"
docker compose -f deploy/docker-compose.shared-caddy.yml --profile bot up -d --build
```

Optional access control:

```bash
export TELEGRAM_ALLOWED_CHAT_IDS="123456789,-1001234567890"
```

Bot commands:

```text
/price 삼성전자
/price AAPL
/signal 삼성전자
/signal 엔비디아
/add 국장 005930.KS 삼전
/add 미장 NVDA 엔비
/list 국장
/list 미장
/price 삼전
/signal 엔비
/remove 삼전
/help
```

Aliases are shared per Telegram chat. People in the same group chat use the same
alias list, while aliases in another group or private chat stay separate. In the
Docker deployment the alias SQLite database is stored in the
`mb_quant_bot_data` volume.

Do not run two polling processes with the same Telegram bot token. If another
project already uses that token, either add these commands to that running bot or
use a new BotFather token.

## 2. Reverse proxy without 443

This project does not require port 443 to run.

- FastAPI runs on `127.0.0.1:8000`
- Nginx serves the React build and proxies `/api` to FastAPI
- The sample config in `deploy/nginx.conf` listens on port `80`

### Server setup

```bash
cd /var/www/mb-quant
python3 -m venv .venv-web
. .venv-web/bin/activate
pip install -r backend/requirements.txt
cd frontend
npm ci
npm run build
```

### FastAPI service

```bash
sudo cp deploy/mb-quant-api.service /etc/systemd/system/mb-quant-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now mb-quant-api
```

### Telegram bot service

Set the new bot token in `/var/www/mb-quant/.env`:

```env
TELEGRAM_BOT_TOKEN=123456:replace-with-new-bot-token
MB_QUANT_API_BASE_URL=http://127.0.0.1:8000/api
TELEGRAM_ALIAS_DB_PATH=/var/www/mb-quant/data/telegram_aliases.sqlite3
# Optional: comma-separated Telegram chat IDs
TELEGRAM_ALLOWED_CHAT_IDS=
```

Then install the service:

```bash
sudo cp deploy/mb-quant-telegram-bot.service /etc/systemd/system/mb-quant-telegram-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now mb-quant-telegram-bot
```

### Nginx on port 80

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/mb-quant
sudo ln -sf /etc/nginx/sites-available/mb-quant /etc/nginx/sites-enabled/mb-quant
sudo nginx -t
sudo systemctl reload nginx
```

If `80` is also unavailable, change `listen 80;` to another public port such as `8080` or `8443`, then open that port in the firewall.

## 3. Standalone mode without nginx

FastAPI can also serve the built frontend directly, so you can run everything on a single port such as `8000`.

```bash
cd /var/www/mb-quant
python3 -m venv .venv-web
. .venv-web/bin/activate
pip install -r backend/requirements.txt

cd /var/www/mb-quant/frontend
npm ci
npm run build

cd /var/www/mb-quant
sudo cp deploy/mb-quant-standalone.service /etc/systemd/system/mb-quant-standalone.service
sudo systemctl daemon-reload
sudo systemctl enable --now mb-quant-standalone
```

Then access the app at:

- `http://SERVER_IP:8000`
- `http://DOMAIN:8000`

To use another port, edit `deploy/mb-quant-standalone.service` and change `--port 8000`.

## 4. Frontend and backend on separate ports

If you want the frontend on one port and the API on another, set a public API URL before building the frontend.

```bash
cd /var/www/mb-quant/frontend
cp .env.example .env
```

Example:

```env
VITE_API_BASE_URL=http://SERVER_IP:8000/api
```

Then build and run the frontend:

```bash
npm ci
npm run build
npm run preview:host
```

Example result:

- frontend: `http://SERVER_IP:4173`
- backend: `http://SERVER_IP:8000`

## Notes

- Do not use the root `requirements.txt` for the web server. That file is for the GitHub Actions mail job.
- The shared-Caddy Docker path is the recommended deployment when another stack already owns `80/443`.
- If you expose FastAPI directly without nginx, make sure the server firewall allows the selected port.
- If you use `8443` instead of `443`, users must include the port in the URL.
- The existing nginx deployment keeps working exactly as before; 443 is not required by this repository.

## API examples

Name-based stock price and MB signal endpoints resolve Korean/English company
names and tickers before fetching data:

```bash
curl "http://127.0.0.1:8000/api/resolve?q=삼성전자"
curl "http://127.0.0.1:8000/api/price?q=삼성전자"
curl "http://127.0.0.1:8000/api/signal?q=엔비디아"
```

## Telegram command reference

```text
/add 국장 [국장 티커] [별명]
/add 미장 [미장 티커] [별명]
/list 국장
/list 미장
/price [회사명|티커|별명]
/signal [회사명|티커|별명]
/remove [별명]
/whoami
/help
```

Examples:

```text
/add 국장 005930.KS 삼전
/add 국장 028300.KQ HLB
/add 미장 NVDA 엔비
/price 삼전
/signal 엔비
```
