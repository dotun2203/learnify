from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.core.exceptions import EmailNotVerified, InvalidCredentials

from . import selectors, services
from . import serializers as s
from .models import OTPCode


class PublicAPIView(APIView):
    """Base for endpoints anyone can call (no token needed)."""

    permission_classes = [AllowAny]
    authentication_classes = []


def me_payload(user):
    return s.MeSerializer(selectors.get_user_context(user)).data


def auth_response(user, http_status=status.HTTP_200_OK):
    data = {**services.issue_tokens(user), **me_payload(user)}
    return Response(data, status=http_status)


OK = {"detail": "If the account exists, a code has been sent."}


# 1. Register
class RegisterView(PublicAPIView):
    throttle_scope = "login"

    @extend_schema(tags=["auth"], request=s.RegisterSerializer,
                   responses={201: s.AuthResponseSerializer})
    def post(self, request):
        ser = s.RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = services.register_user(**ser.validated_data)
        return Response(
            {"detail": "Check your email for a verification code.",
             "email": user.email, "next": "verify_email"},
            status=status.HTTP_201_CREATED,
        )


# 2. Login (password)
class LoginView(PublicAPIView):
    throttle_scope = "login"

    @extend_schema(tags=["auth"], request=s.LoginSerializer,
                   responses={200: s.AuthResponseSerializer})
    def post(self, request):
        ser = s.LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = authenticate(request, username=ser.validated_data["identifier"],
                            password=ser.validated_data["password"])
        if user is None:
            raise InvalidCredentials()
        if user.email and not user.is_email_verified:
            # The frontend should send them to the verify screen and
            # call /auth/otp/request/ with purpose=verify_email.
            raise EmailNotVerified()
        return auth_response(user)


# 3. Refresh
@extend_schema(tags=["auth"])
class RefreshView(TokenRefreshView):
    pass


# 4. Logout
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], request=s.RefreshSerializer, responses={204: None})
    def post(self, request):
        ser = s.RefreshSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.logout(ser.validated_data["refresh"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# 5. Me
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], responses={200: s.MeSerializer})
    def get(self, request):
        return Response(me_payload(request.user))

    @extend_schema(tags=["auth"], request=s.ProfileUpdateSerializer,
                   responses={200: s.MeSerializer})
    def patch(self, request):
        ser = s.ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(me_payload(request.user))


# 6. Request OTP
class OTPRequestView(PublicAPIView):
    throttle_scope = "otp"

    @extend_schema(tags=["auth"], request=s.OTPRequestSerializer,
                   responses={202: s.DetailSerializer})
    def post(self, request):
        ser = s.OTPRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.request_otp_for_identifier(**ser.validated_data)
        return Response(OK, status=status.HTTP_202_ACCEPTED)


# 7. Verify phone/email
class OTPVerifyView(PublicAPIView):
    throttle_scope = "otp"

    @extend_schema(tags=["auth"], request=s.OTPVerifySerializer,
                   responses={200: s.UserSerializer})
    def post(self, request):
        ser = s.OTPVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = services.verify_contact(**ser.validated_data)
        return auth_response(user)


# 8. Login with OTP (students)
class OTPLoginView(PublicAPIView):
    throttle_scope = "otp"

    @extend_schema(tags=["auth"], request=s.OTPLoginSerializer,
                   responses={200: s.AuthResponseSerializer})
    def post(self, request):
        ser = s.OTPLoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = services.login_with_otp(**ser.validated_data)
        return auth_response(user)


# 9. Change password
class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], request=s.PasswordChangeSerializer, responses={204: None})
    def post(self, request):
        ser = s.PasswordChangeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.change_password(user=request.user, **ser.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)


# 10. Forgot password
class PasswordResetRequestView(PublicAPIView):
    throttle_scope = "otp"

    @extend_schema(tags=["auth"], request=s.IdentifierOnlySerializer,
                   responses={202: s.DetailSerializer})
    def post(self, request):
        ser = s.IdentifierOnlySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.request_otp_for_identifier(
            identifier=ser.validated_data["identifier"],
            purpose=OTPCode.Purpose.RESET_PASSWORD,
        )
        return Response(OK, status=status.HTTP_202_ACCEPTED)


# 11. Reset password
class PasswordResetConfirmView(PublicAPIView):
    throttle_scope = "otp"

    @extend_schema(tags=["auth"], request=s.PasswordResetConfirmSerializer,
                   responses={204: None})
    def post(self, request):
        ser = s.PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.reset_password(**ser.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)