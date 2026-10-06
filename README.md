# login-with-number-verification

A demo of logging in by phone number, confirmed via the CAMARA Number Verification API's `/verify` operation (the OIDC flow, no TS.43 device token).

## Web app (`app/`)

Mobile-first FastAPI app: enter a phone number, get redirected through the operator's silent login, and see whether it matched the device's SIM.

```
pip install -r app/requirements.txt
cp app/.env.example app/.env   # fill in with real operator values, then: set -a && source app/.env && set +a
uvicorn app.main:app --reload
```

All operator-specific config (client id/secret, OIDC endpoints, API root) lives in `app/config.py`, read from environment variables - see `app/.env.example` for the full list. Nothing here will work end-to-end until real values are set (as GitHub-side environment variables in deployment); until then it fails gracefully at the callback step.

The redirect only comes back silently if the browser completing it is actually on the operator's mobile network - Wi-Fi will surface an OIDC error instead of a code.

## Test script (`scripts/`)

A standalone CLI for exercising the same no-TS.43-token flow directly against both API endpoints (`/verify` and `/device-phone-number`). See `scripts/.env.example`.

```
pip install -r scripts/requirements.txt
set -a && source scripts/.env && set +a
python3 scripts/basic_flow_test.py
```
