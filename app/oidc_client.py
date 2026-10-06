"""OIDC helper for the no-TS.43-token path: discovery, PKCE, auth URL, token exchange."""
import base64
import hashlib
import secrets
import time
import uuid
from urllib.parse import urlencode

import jwt
import requests

from . import config


def resolve_endpoints() -> tuple[str, str]:
    if config.OPENID_CONFIG_URL:
        resp = requests.get(config.OPENID_CONFIG_URL, timeout=15)
        resp.raise_for_status()
        doc = resp.json()
        return doc["authorization_endpoint"], doc["token_endpoint"]
    return config.AUTHORIZATION_ENDPOINT, config.TOKEN_ENDPOINT


def make_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_authorization_url(state: str, code_challenge: str, redirect_uri: str) -> str:
    auth_endpoint, _ = resolve_endpoints()
    params = {
        "response_type": "code",
        "client_id": config.CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": config.SCOPE,
        "state": state,
        "prompt": "none",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{auth_endpoint}?{urlencode(params)}"


def _build_client_assertion(token_endpoint: str) -> str:
    """A signed JWT used as client authentication instead of a client_secret.

    RFC 7523 private_key_jwt: signed with the private key whose public half
    was registered with the operator as a JWKS.
    """
    now = int(time.time())
    claims = {
        "iss": config.CLIENT_ID,
        "sub": config.CLIENT_ID,
        "aud": token_endpoint,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + 300,
    }
    headers = {"kid": config.CLIENT_ASSERTION_KID} if config.CLIENT_ASSERTION_KID else None
    return jwt.encode(claims, config.CLIENT_ASSERTION_PRIVATE_KEY, algorithm="RS256", headers=headers)


def exchange_code_for_token(code: str, code_verifier: str, redirect_uri: str) -> dict:
    _, token_endpoint = resolve_endpoints()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": config.CLIENT_ID,
        "code_verifier": code_verifier,
    }
    auth = None
    if config.CLIENT_ASSERTION_PRIVATE_KEY:
        data["client_assertion_type"] = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
        data["client_assertion"] = _build_client_assertion(token_endpoint)
    elif config.CLIENT_SECRET:
        auth = (config.CLIENT_ID, config.CLIENT_SECRET)
    resp = requests.post(token_endpoint, data=data, auth=auth, timeout=15)
    resp.raise_for_status()
    return resp.json()
