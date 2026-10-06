"""Thin client for the Number Verification API's POST /verify operation."""
import uuid

import requests

from . import config


class VerifyError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def verify_phone_number(access_token: str, phone_number: str) -> bool:
    url = f"{config.API_ROOT}/number-verification/v2/verify"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-correlator": str(uuid.uuid4()),
    }
    resp = requests.post(url, headers=headers, json={"phoneNumber": phone_number}, timeout=15)
    if resp.ok:
        return bool(resp.json().get("devicePhoneNumberVerified", False))

    try:
        body = resp.json()
    except ValueError:
        body = {}
    raise VerifyError(resp.status_code, body.get("code", ""), body.get("message") or resp.text)
