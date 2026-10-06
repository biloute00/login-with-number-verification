#!/usr/bin/env python3
"""
Test the Number Verification API's "basic" login path: the standard OIDC
Authorization Code flow with prompt=none (no TS.43 temporary token).

This flow only comes back silently (no login screen) if the device running
the browser step is actually attached to the mobile network of the operator
that issued CLIENT_ID. Running it over Wi-Fi will surface an OIDC error such
as login_required or interaction_required instead of a code.

Usage:
    set -a && source .env && set +a   # load config, see .env.example
    python3 scripts/basic_flow_test.py [--phone +34600000000] [--endpoint verify|share|both]

Required configuration (environment variables, see .env.example):
    CLIENT_ID, REDIRECT_URI, API_ROOT
    and either OPENID_CONFIG_URL (for discovery) or both
    AUTHORIZATION_ENDPOINT and TOKEN_ENDPOINT directly.
Optional:
    CLIENT_SECRET, SCOPE, TEST_PHONE_NUMBER
"""
import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import uuid
import webbrowser

import requests

DEFAULT_SCOPE = "openid number-verification:verify number-verification:device-phone-number:read"
CALLBACK_TIMEOUT_SECONDS = 120


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"Missing required environment variable: {name} (see .env.example)")
    return value


def discover_oidc_config(openid_config_url):
    resp = requests.get(openid_config_url, timeout=15)
    resp.raise_for_status()
    config = resp.json()
    return config["authorization_endpoint"], config["token_endpoint"]


def make_pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    result = {}

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        _CallbackHandler.result = dict(urllib.parse.parse_qsl(query))
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<p>Done. You can close this tab and check the terminal.</p>")

    def log_message(self, fmt, *args):
        pass  # keep stdout clean; the script prints its own progress


def wait_for_callback(redirect_uri):
    parsed = urllib.parse.urlparse(redirect_uri)
    host, port = parsed.hostname, parsed.port or 80
    server = http.server.HTTPServer((host, port), _CallbackHandler)
    server.timeout = CALLBACK_TIMEOUT_SECONDS

    result_holder = {}

    def serve_once():
        server.handle_request()
        result_holder["data"] = _CallbackHandler.result

    thread = threading.Thread(target=serve_once)
    thread.start()
    thread.join(timeout=CALLBACK_TIMEOUT_SECONDS)
    server.server_close()

    if "data" not in result_holder:
        sys.exit(
            f"Timed out after {CALLBACK_TIMEOUT_SECONDS}s waiting for the redirect back to "
            f"{redirect_uri}. Did you open the authorization URL in a browser?"
        )
    return result_holder["data"]


def build_authorization_url(auth_endpoint, client_id, redirect_uri, scope, state, code_challenge):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "prompt": "none",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{auth_endpoint}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(token_endpoint, client_id, client_secret, redirect_uri, code, code_verifier):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    auth = (client_id, client_secret) if client_secret else None
    resp = requests.post(token_endpoint, data=data, auth=auth, timeout=15)
    if not resp.ok:
        sys.exit(f"Token exchange failed: {resp.status_code} {resp.text}")
    return resp.json()


def call_api(method, api_root, path, access_token, json_body=None):
    url = f"{api_root}/number-verification/v2{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-correlator": str(uuid.uuid4()),
    }
    resp = requests.request(method, url, headers=headers, json=json_body, timeout=15)
    print(f"\n{method} {path} -> {resp.status_code}")
    print(f"x-correlator: {headers['x-correlator']}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except ValueError:
        print(resp.text)
    if resp.status_code == 403:
        try:
            code = resp.json().get("code", "")
        except ValueError:
            code = ""
        if code == "NUMBER_VERIFICATION.USER_NOT_AUTHENTICATED_BY_MOBILE_NETWORK":
            print(
                "-> The access token wasn't obtained via a mobile-network login. "
                "Re-run the authorization step on a device using mobile data, not Wi-Fi."
            )
    return resp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phone", default=None, help="Phone number for /verify, E.164 format (e.g. +34600000000)")
    parser.add_argument(
        "--endpoint",
        choices=["verify", "share", "both"],
        default="both",
        help="Which endpoint(s) to call after authenticating (default: both)",
    )
    args = parser.parse_args()

    client_id = env("CLIENT_ID", required=True)
    client_secret = env("CLIENT_SECRET")
    redirect_uri = env("REDIRECT_URI", default="http://localhost:8743/callback")
    api_root = env("API_ROOT", required=True).rstrip("/")
    scope = env("SCOPE", default=DEFAULT_SCOPE)
    phone_number = args.phone or env("TEST_PHONE_NUMBER")

    openid_config_url = env("OPENID_CONFIG_URL")
    if openid_config_url:
        auth_endpoint, token_endpoint = discover_oidc_config(openid_config_url)
    else:
        auth_endpoint = env("AUTHORIZATION_ENDPOINT", required=True)
        token_endpoint = env("TOKEN_ENDPOINT", required=True)

    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = make_pkce_pair()

    auth_url = build_authorization_url(auth_endpoint, client_id, redirect_uri, scope, state, code_challenge)
    print("1. Open this URL in a browser on a device connected to the mobile network (not Wi-Fi):\n")
    print(f"   {auth_url}\n")
    webbrowser.open(auth_url)

    print(f"2. Waiting up to {CALLBACK_TIMEOUT_SECONDS}s for the redirect back to {redirect_uri} ...")
    callback_params = wait_for_callback(redirect_uri)

    if "error" in callback_params:
        sys.exit(
            f"Authorization failed: {callback_params.get('error')} "
            f"- {callback_params.get('error_description', '')}\n"
            "If this is login_required or interaction_required, the silent check could not be "
            "satisfied - the device is probably not on the operator's mobile network."
        )
    if callback_params.get("state") != state:
        sys.exit("State mismatch on callback - aborting (possible CSRF or stale redirect).")
    code = callback_params.get("code")
    if not code:
        sys.exit(f"No authorization code in callback: {callback_params}")

    print("3. Got an authorization code, exchanging it for an access token ...")
    token_response = exchange_code_for_token(token_endpoint, client_id, client_secret, redirect_uri, code, code_verifier)
    access_token = token_response.get("access_token")
    if not access_token:
        sys.exit(f"No access_token in token response: {token_response}")
    print(f"   access_token: {access_token[:16]}... (scope: {token_response.get('scope', '?')})")

    if args.endpoint in ("verify", "both"):
        if phone_number:
            call_api("POST", api_root, "/verify", access_token, json_body={"phoneNumber": phone_number})
        else:
            print("\nSkipping /verify: no phone number given (--phone or TEST_PHONE_NUMBER).")

    if args.endpoint in ("share", "both"):
        call_api("GET", api_root, "/device-phone-number", access_token)


if __name__ == "__main__":
    main()
