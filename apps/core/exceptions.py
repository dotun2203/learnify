from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.views import exception_handler


class DomainError(APIException):
    """Raise from services for predictable business-rule failures."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "domain_error"
    default_detail = "The request could not be completed."

    def __init__(self, detail=None, code=None, status_code=None):
        if status_code:
            self.status_code = status_code
        # Keep the code on the instance: when `detail` is a dict, DRF attaches
        # codes to each item and get_codes() no longer returns a plain string.
        self.code = code or self.default_code
        super().__init__(detail, code)


class PlanLimitReached(DomainError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_code = "plan_limit_reached"
    default_detail = "Your current plan limit has been reached."


class KycRequired(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "kyc_required"
    default_detail = "Identity verification is required for this action."


def custom_exception_handler(exc, context):
    """Every error returns {"error": {"code", "message", "details"}}."""
    response = exception_handler(exc, context)
    if response is None:
        return None

    code = getattr(exc, "code", None) or getattr(exc, "default_code", "error")
    if not isinstance(exc, DomainError) and hasattr(exc, "get_codes"):
        codes = exc.get_codes()
        if isinstance(codes, str):
            code = codes

    data = response.data
    if isinstance(data, dict) and set(data.keys()) == {"detail"}:
        message, details = str(data["detail"]), {}
    elif isinstance(exc, DomainError):
        # A service raised this with structured details (e.g. publish blockers).
        # Keep its own code so the frontend can react to it.
        message, details = exc.default_detail, data
    else:
        message, details = "Validation failed.", data
        code = "validation_error" if isinstance(exc, DRFValidationError) else code

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response

class InvalidCredentials(DomainError):
    """Explicit 401. (DRF's AuthenticationFailed becomes 403 on views that have
    authentication_classes = [], because there's no WWW-Authenticate header to send.)"""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "invalid_credentials"
    default_detail = "Invalid credentials."


class EmailNotVerified(DomainError):
    """Password login is blocked until the email address is confirmed."""

    status_code = status.HTTP_403_FORBIDDEN
    default_code = "email_not_verified"
    default_detail = "Confirm your email address to finish signing in."
