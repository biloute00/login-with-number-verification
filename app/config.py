"""
Single source of truth for the operator / Number Verification API config.

Every value below is a placeholder read from an environment variable. Real
values (client id/secret, the operator's OIDC endpoints, the API root) come
from onboarding with the operator and must never be hardcoded here - set
them as environment variables instead (see .env.example in this folder).
Every other module that needs one of these values imports it from here.
"""
import os


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


# OAuth client registered with the operator for this app
CLIENT_ID = _env("CLIENT_ID", "REPLACE_WITH_CLIENT_ID")
CLIENT_SECRET = _env("CLIENT_SECRET", "")  # leave empty for a public client using PKCE only

# Must match a redirect URI registered with the operator
REDIRECT_URI = _env("REDIRECT_URI", "http://localhost:8000/callback")

# Either set OPENID_CONFIG_URL so the app discovers the two endpoints below...
OPENID_CONFIG_URL = _env("OPENID_CONFIG_URL", "")
# ...or set these directly if discovery isn't available for this operator
AUTHORIZATION_ENDPOINT = _env("AUTHORIZATION_ENDPOINT", "https://example.com/oauth2/authorize")
TOKEN_ENDPOINT = _env("TOKEN_ENDPOINT", "https://example.com/oauth2/token")

# apiRoot from the Number Verification OpenAPI spec, e.g. https://api.orange.com/camara/ofr
API_ROOT = _env("API_ROOT", "https://example.com/camara/placeholder").rstrip("/")

# Scope needed for the /verify call this demo uses
SCOPE = _env("SCOPE", "openid number-verification:verify")
