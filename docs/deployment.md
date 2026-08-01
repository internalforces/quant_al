# 배포와 환경 변수

## Docker로 실행

프로젝트 루트에서 React 빌드와 FastAPI 런타임을 함께 만듭니다.

```bash
docker build -t mb-quant .
docker run --rm -p 8000:8000 mb-quant
```

`http://localhost:8000/healthz`로 상태를 확인할 수 있습니다.

기존 Caddy 네트워크와 함께 실행하는 구성은 [`deploy/docker-compose.shared-caddy.yml`](../deploy/docker-compose.shared-caddy.yml)을 사용합니다.

```bash
docker compose -f deploy/docker-compose.shared-caddy.yml up -d --build
```

이 구성은 외부 80/443 포트를 직접 점유하지 않습니다. 공개 HTTPS 라우팅은 공유 Caddy에 `deploy/Caddyfile.gilgop.cloud`의 사이트 블록을 추가해 처리합니다.

## Telegram Bot

Bot은 API와 분리된 프로세스입니다. 다음 환경 변수를 설정한 뒤 compose profile 또는 systemd 서비스를 실행합니다.

```env
TELEGRAM_BOT_TOKEN=replace-with-bot-token
MB_QUANT_API_BASE_URL=http://127.0.0.1:8000/api
TELEGRAM_ALIAS_DB_PATH=data/telegram_aliases.sqlite3
# 선택 사항: 허용할 Telegram chat_id를 쉼표로 구분
TELEGRAM_ALLOWED_CHAT_IDS=
```

토큰은 Git에 커밋하지 않습니다. 런타임 SQLite 파일도 `.gitignore`에 포함되어 있습니다.

## 정기 이메일 작업

`.github/workflows/mb.yml`은 평일에 `mb_main.py`를 실행해 설정된 수신자에게 신호 요약을 보냅니다.

필요한 GitHub Secrets:

- `EMAIL_SENDER`
- `EMAIL_RECIPIENTS`
- `SMTP_SERVER`
- `SMTP_USER`
- `SMTP_PASSWORD`

로컬 실행은 다음과 같습니다.

```bash
pip install -r requirements.txt
python mb_main.py
```

## 환경 변수 예시

템플릿은 [`.env.example`](../.env.example)에 있습니다. 실제 `.env`는 개인 비밀값이므로 절대 커밋하지 않습니다.

## 배포 전 확인

```bash
.venv/bin/python -m pytest -q
cd frontend && npm run lint && npm run build
curl --fail http://127.0.0.1:8000/healthz
```

과거 서버별 설치 명령과 systemd/Nginx 예시는 [README-setup.md](../README-setup.md)에 보존되어 있습니다.
