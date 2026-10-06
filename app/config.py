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

# For operators that require private_key_jwt client authentication (RFC 7523)
# instead of a client_secret - e.g. Orange's "JWT assertion" JWKS requirement.
# PEM-encoded private key whose public half was registered with the operator
# as a JWKS. Takes priority over CLIENT_SECRET when set. "\n" is unescaped
# so the key can be stored as a single-line environment variable.
CLIENT_ASSERTION_PRIVATE_KEY = _env("CLIENT_ASSERTION_PRIVATE_KEY", "").replace("\\n", "\n")
# Must match the "kid" of the corresponding key in that JWKS
CLIENT_ASSERTION_KID = _env("CLIENT_ASSERTION_KID", "")

# The redirect URI isn't configured here - app/main.py builds it from each
# request's own host, so it's always the host the app is actually running
# on (whatever that is on a given Upsun environment) instead of a value
# that has to be kept in sync separately. It still must be registered with
# the operator exactly as the app will send it, e.g. https://<your-upsun-
# domain>/callback.

# Either set OPENID_CONFIG_URL so the app discovers the two endpoints below...
OPENID_CONFIG_URL = _env("OPENID_CONFIG_URL", "")
# ...or set these directly if discovery isn't available for this operator
AUTHORIZATION_ENDPOINT = _env("AUTHORIZATION_ENDPOINT", "https://example.com/oauth2/authorize")
TOKEN_ENDPOINT = _env("TOKEN_ENDPOINT", "https://example.com/oauth2/token")

# apiRoot from the Number Verification OpenAPI spec, e.g. https://api.orange.com/camara/ofr
API_ROOT = _env("API_ROOT", "https://example.com/camara/placeholder").rstrip("/")

# Scope needed for the /verify call this demo uses
SCOPE = _env("SCOPE", "openid number-verification:verify")
