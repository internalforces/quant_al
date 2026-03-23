# MB Quant Deployment

## Deployment split

- GitHub Actions mail job stays as-is: `.github/workflows/mb.yml` runs `mb_main.py` with the root `requirements.txt`
- Web server deployment is separate: install only `backend/requirements.txt`, build the frontend, and run the FastAPI service
- Domain for the web server is `gilgop.cloud`

## 1. Reverse proxy without 443

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

### Nginx on port 80

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/mb-quant
sudo ln -sf /etc/nginx/sites-available/mb-quant /etc/nginx/sites-enabled/mb-quant
sudo nginx -t
sudo systemctl reload nginx
```

If `80` is also unavailable, change `listen 80;` to another public port such as `8080` or `8443`, then open that port in the firewall.

## 2. Standalone mode without nginx

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

## 3. Frontend and backend on separate ports

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
- If you expose FastAPI directly without nginx, make sure the server firewall allows the selected port.
- If you use `8443` instead of `443`, users must include the port in the URL.
- The existing nginx deployment keeps working exactly as before; 443 is not required by this repository.
