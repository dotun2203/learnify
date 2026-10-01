"""Low-level OTP helpers: generate, hash, compare."""
import hashlib
import hmac
import secrets

from django.conf import settings


def generate_code(length=None):
    length = length or settings.OTP_LENGTH
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_code(code):
    # HMAC with SECRET_KEY: fast to check, useless to an attacker without the key
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


def codes_match(code, code_hash):
    return hmac.compare_digest(hash_code(code), code_hash)