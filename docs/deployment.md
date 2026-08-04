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
export CADDY_SHARED_NETWORK=<existing-caddy-network-name>
docker compose -f deploy/docker-compose.shared-caddy.yml up -d --build
```

이 구성은 외부 80/443 포트를 직접 점유하지 않습니다. 공개 HTTPS 라우팅은 공유 Caddy에 `deploy/Caddyfile.gilgop.cloud`의 사이트 블록을 추가해 처리합니다.
`CADDY_SHARED_NETWORK`에는 기존 Caddy 게이트웨이가 사용하는 외부 Docker 네트워크 이름을 지정합니다.

## Telegram Bot

Bot은 API와 분리된 프로세스입니다. 다음 환경 변수를 설정한 뒤 compose profile 또는 systemd 서비스를 실행합니다.

```env
TELEGRAM_BOT_TOKEN=replace-with-bot-token
MB_QUANT_API_BASE_URL=http://127.0.0.1:8000/api
TELEGRAM_ALIAS_DB_PATH=data/telegram_aliases.sqlite3
# Generate with: openssl rand -hex 32
# The API and bot must use the same value.
MB_QUANT_BOT_API_TOKEN=replace-with-a-distinct-random-secret
# 선택 사항: 허용할 Telegram chat_id를 쉼표로 구분
TELEGRAM_ALLOWED_CHAT_IDS=
```

`MB_QUANT_BOT_API_TOKEN`은 봇 요청을 인증하고 채팅별 요청 제한을 적용하는 공유 비밀입니다.
systemd에서는 봇이 `.env`를, 공개 API가 `.env.api`를 읽습니다. `.env.api`는
`deploy/mb-quant-api.env.example`에서 만들고, 두 파일의 `MB_QUANT_BOT_API_TOKEN`을
같은 값으로 설정합니다. Compose 구성은 두 컨테이너에 이 값을 전달합니다.
토큰은 Git에 커밋하지 않습니다. 런타임 SQLite 파일도 `.gitignore`에 포함되어 있습니다.

## 정기 이메일 작업

`.github/workflows/mb.yml`은 매주 월요일부터 금요일, 23:00 KST(UTC 14:00)에 `mb_main.py`를 실행합니다. 수동 실행(`workflow_dispatch`)도 지원합니다.

리포트에는 지정한 최대 10개 종목의 최신 신호와 포지션, 전략·시장 누적 성과, 월·연 수익률, 샤프 비율을 종목별로 정리해 포함합니다. `EMAIL_RECIPIENTS`에 쉼표로 구분한 모든 수신자에게 각각 발송합니다.

필요한 GitHub Secrets:

- `EMAIL_SENDER`
- `EMAIL_RECIPIENTS`
- `SMTP_SERVER`
- `SMTP_PORT` (`587`은 STARTTLS, `465`는 SSL)
- `SMTP_USER`
- `SMTP_PASSWORD`

GitHub 저장소에서 **Settings → Secrets and variables → Actions → New repository secret**으로 위 값을 등록합니다. `SMTP_PORT`는 숫자만 입력하며, 값을 생략하면 기본값 `587`을 사용합니다. 필수 설정이 누락되었거나 모든 수신자 전송이 실패하면 워크플로는 실패로 끝나므로, Actions 실행 결과가 설정 및 SMTP 서버 전달 실패를 놓치지 않도록 합니다. 수신자 주소는 로그에 남기지 않고 성공·실패 건수만 기록합니다. SMTP 서버의 수락은 최종 수신함 도달을 보장하지 않으므로, 수신 여부를 장기적으로 확인하려면 발송 이력이나 외부 모니터링이 필요합니다.

로컬 실행은 다음과 같습니다.

```bash
pip install -r requirements.txt
python mb_main.py
```

로컬 실행에서도 `.env`에 같은 변수를 설정합니다. 포트 `587`은 STARTTLS, `465`는 SSL 연결을 사용합니다.

## 환경 변수 예시

템플릿은 [`.env.example`](../.env.example)와
[`deploy/mb-quant-api.env.example`](../deploy/mb-quant-api.env.example)에 있습니다.
실제 `.env`와 `.env.api`는 개인 비밀값이므로 절대 커밋하지 않습니다.

## 배포 전 확인

```bash
.venv/bin/python -m pytest -q
cd frontend && npm run lint && npm run build
curl --fail http://127.0.0.1:8000/healthz
```

과거 서버별 설치 명령과 systemd/Nginx 예시는 [README-setup.md](../README-setup.md)에 보존되어 있습니다.
