"""
Mobile web demo: log in by typing a phone number, confirmed against the
Number Verification API's /verify operation (the OIDC, no-TS.43-token path).

Run with:  uvicorn app.main:app --reload
Config:    see app/config.py and .env.example for the environment variables
           to set (client id/secret, OIDC endpoints, API root).
"""
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import oidc_client
from .number_verification_client import VerifyError, verify_phone_number

BASE_DIR = Path(__file__).parent
PHONE_PATTERN = re.compile(r"^\+[1-9][0-9]{4,14}$")
PENDING_TTL_SECONDS = 300

app = FastAPI(title="Number Verification login demo")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# One-process, in-memory bridge between the /login redirect and the /callback
# it comes back to. Fine for this demo; a multi-worker deployment would need
# a shared store (e.g. Redis) instead.
_pending_logins: dict[str, dict] = {}


def _cleanup_pending() -> None:
    cutoff = time.time() - PENDING_TTL_SECONDS
    for state in [s for s, v in _pending_logins.items() if v["created_at"] < cutoff]:
        _pending_logins.pop(state, None)


def _result_page(request: Request, *, ok: bool, title: str, detail: str, hint: str = "", status_code: int = 200):
    return templates.TemplateResponse(
        request,
        "result.html",
        {"ok": ok, "title": title, "detail": detail, "hint": hint},
        status_code=status_code,
    )


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"error": None})


@app.post("/login")
def login(request: Request, phone_number: str = Form(...)):
    phone_number = phone_number.strip()
    if not PHONE_PATTERN.match(phone_number):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"error": "Enter the number in international format, e.g. +33612345678."},
            status_code=400,
        )

    _cleanup_pending()
    state = uuid.uuid4().hex
    code_verifier, code_challenge = oidc_client.make_pkce_pair()
    _pending_logins[state] = {
        "phone_number": phone_number,
        "code_verifier": code_verifier,
        "created_at": time.time(),
    }
    auth_url = oidc_client.build_authorization_url(state, code_challenge)
    return RedirectResponse(auth_url, status_code=302)


@app.get("/callback")
def callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    pending = _pending_logins.pop(state, None) if state else None

    if error:
        hint = ""
        if error in ("login_required", "interaction_required", "consent_required"):
            hint = (
                "This usually means the device isn't on the operator's mobile network "
                "- a silent check can't complete over Wi-Fi."
            )
        return _result_page(
            request, ok=False, title="Login failed",
            detail=f"{error}: {error_description or ''}".rstrip(": "), hint=hint, status_code=400,
        )

    if not pending:
        return _result_page(
            request, ok=False, title="Login expired",
            detail="This login attempt is no longer valid - please try again.", status_code=400,
        )

    if not code:
        return _result_page(request, ok=False, title="Login failed", detail="No authorization code was returned.", status_code=400)

    try:
        token_response = oidc_client.exchange_code_for_token(code, pending["code_verifier"])
        access_token = token_response["access_token"]
        verified = verify_phone_number(access_token, pending["phone_number"])
    except VerifyError as exc:
        hint = ""
        if exc.code == "NUMBER_VERIFICATION.USER_NOT_AUTHENTICATED_BY_MOBILE_NETWORK":
            hint = "The login wasn't done via the mobile network, so the API refuses to check the number at all."
        return _result_page(
            request, ok=False, title="Verification failed",
            detail=f"{exc.status_code} {exc.code}: {exc.message}", hint=hint,
        )
    except Exception as exc:  # token exchange or network failure
        return _result_page(request, ok=False, title="Login failed", detail=str(exc), status_code=502)

    if verified:
        return _result_page(
            request, ok=True, title="You're logged in",
            detail=f"{pending['phone_number']} matches this device's SIM.",
        )
    return _result_page(
        request, ok=False, title="Numbers don't match",
        detail=f"{pending['phone_number']} doesn't match this device's SIM.",
    )
