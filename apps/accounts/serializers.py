from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import OTPCode
from .selectors import normalize_identifier
from .validators import normalize_phone

User = get_user_model()


# ---------- reusable fields ----------

class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class IdentifierField(serializers.CharField):
    """Accepts an email or a phone number; returns it normalised."""

    def __init__(self, **kwargs):
        kwargs.setdefault("help_text", "Email address or phone number")
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_identifier(value)[1]
        except DjangoValidationError as exc:
            raise serializers.ValidationError("Enter a valid email or phone number.") from exc


class OTPCodeField(serializers.RegexField):
    def __init__(self, **kwargs):
        super().__init__(r"^\d{4,8}$", **kwargs)


# ---------- output ----------

class UserSerializer(serializers.ModelSerializer):
    has_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "phone", "first_name", "last_name",
                  "is_phone_verified", "is_email_verified", "has_password",
                  "preferred_language", "timezone", "date_joined")
        read_only_fields = fields

    def get_has_password(self, obj) -> bool:
        # False for students created at checkout (OTP-only) -> show "Set a password"
        return obj.has_usable_password()


class AcademyAccessSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.SlugField()
    name = serializers.CharField()
    role = serializers.CharField()


class MeSerializer(serializers.Serializer):
    """The user plus the roles the frontend routes on."""

    user = UserSerializer()
    academies = AcademyAccessSerializer(many=True)
    is_student = serializers.BooleanField()
    is_platform_admin = serializers.BooleanField()


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class AuthResponseSerializer(TokenPairSerializer, MeSerializer):
    """Login/register response: tokens + the same payload as GET /me/."""


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()

class RegisterResponseSerializer(DetailSerializer):
    email = serializers.EmailField()
    next = serializers.CharField(help_text="The step the frontend should show next")


# ---------- input ----------

class RegisterSerializer(serializers.Serializer):
    """Public sign-up (the /signup page). Creating an academy afterwards is what
    makes someone a creator; students are created at checkout instead."""

    email = serializers.EmailField()
    phone = PhoneField()
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("An account with this phone already exists.")
        return value

    def validate(self, attrs):
        user = User(email=attrs["email"], first_name=attrs["first_name"],
                    last_name=attrs["last_name"])
        try:
            validate_password(attrs["password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs


class LoginSerializer(serializers.Serializer):
    identifier = IdentifierField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Only harmless fields. Email/phone changes need their own verified flow."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "preferred_language", "timezone")


class IdentifierOnlySerializer(serializers.Serializer):
    identifier = IdentifierField()


class OTPRequestSerializer(serializers.Serializer):
    identifier = IdentifierField()
    purpose = serializers.ChoiceField(choices=OTPCode.Purpose.choices)


class OTPVerifySerializer(serializers.Serializer):
    identifier = IdentifierField()
    purpose = serializers.ChoiceField(choices=[
        OTPCode.Purpose.VERIFY_PHONE, OTPCode.Purpose.VERIFY_EMAIL,
    ])
    code = OTPCodeField()


class OTPLoginSerializer(serializers.Serializer):
    identifier = IdentifierField()
    code = OTPCodeField()


class PasswordChangeSerializer(serializers.Serializer):
    # Optional only for accounts that have no password yet (OTP-only students)
    current_password = serializers.CharField(write_only=True, required=False,
                                             allow_blank=True)
    new_password = serializers.CharField(write_only=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    identifier = IdentifierField()
    code = OTPCodeField()
    new_password = serializers.CharField(write_only=True)