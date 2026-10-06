# login-with-number-verification

A demo of logging in by phone number, confirmed via the CAMARA Number Verification API's `/verify` operation (the OIDC flow, no TS.43 device token).

## Web app (`app/`)

Mobile-first FastAPI app: enter a phone number, get redirected through the operator's silent login, and see whether it matched the device's SIM.

```
pip install -r app/requirements.txt
cp app/.env.example app/.env   # fill in with real operator values, then: set -a && source app/.env && set +a
uvicorn app.main:app --reload
```

All operator-specific config (client id/secret, OIDC endpoints, API root) lives in `app/config.py`, read from environment variables - see `app/.env.example` for the full list. Nothing here will work end-to-end until real values are set; until then it fails gracefully at the callback step.

The OAuth callback URL (`redirect_uri`) is *not* one of those configured values: `app/main.py` builds it from each request's own host, so it's automatically correct for wherever the app is actually running - locally, or on whatever domain a given Upsun environment ends up with - rather than a value that has to be deployed/kept in sync separately. It still has to be registered with the operator exactly as the app will send it (`https://<your-upsun-domain>/callback`).

The redirect only comes back silently if the browser completing it is actually on the operator's mobile network - Wi-Fi will surface an OIDC error instead of a code.

### Deploying real credentials to Upsun

This app deploys on Upsun (`.upsun/config.yaml`), which builds and deploys straight from this GitHub repo. GitHub Actions secrets are never visible to Upsun on their own, so the real credentials are pushed across explicitly by the `.github/workflows/sync-upsun-variables.yml` workflow.

One-time setup, in this repo's GitHub Settings → Secrets and variables → Actions:

- **Secrets**: `UPSUN_CLI_TOKEN` (an Upsun API token, from the Upsun Console under account settings), plus the real values for `CLIENT_ID`, `CLIENT_SECRET`, `OPENID_CONFIG_URL` (or `AUTHORIZATION_ENDPOINT`/`TOKEN_ENDPOINT`), `API_ROOT`, and `SCOPE` if you need to override the default. (No `REDIRECT_URI` - see above.)
- **Variables**: `UPSUN_PROJECT_ID` (not sensitive - the project ID alone grants no access).

Then run the workflow from the Actions tab (`Run workflow`), optionally overriding which Upsun environment to update (defaults to `main`). It stores each value on Upsun as an `env:`-prefixed variable, which is what exposes it as a plain process environment variable to the running app - re-run it whenever a credential is added or rotated.

## Test script (`scripts/`)

A standalone CLI for exercising the same no-TS.43-token flow directly against both API endpoints (`/verify` and `/device-phone-number`). See `scripts/.env.example`.

```
pip install -r scripts/requirements.txt
set -a && source scripts/.env && set +a
python3 scripts/basic_flow_test.py
```
