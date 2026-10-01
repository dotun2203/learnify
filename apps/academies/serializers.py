from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Academy, AcademyMembership
from .validators import validate_academy_slug


class SlugField(serializers.SlugField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return validate_academy_slug(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class AcademySerializer(serializers.ModelSerializer):
    """Studio view: what a member sees."""

    role = serializers.SerializerMethodField()

    class Meta:
        model = Academy
        fields = ("id", "name", "slug", "tagline", "description", "logo", "brand_color",
                  "website", "support_email", "whatsapp_number", "status", "role",
                  "activated_at", "created_at")
        read_only_fields = ("id", "slug", "status", "role", "activated_at", "created_at")

    def get_role(self, obj) -> str | None:
        user = self.context["request"].user
        membership = next((m for m in obj.memberships.all() if m.user_id == user.id), None)
        return membership.role if membership else None


class AcademyCreateSerializer(serializers.ModelSerializer):
    slug = SlugField(help_text="Your academy address, e.g. grace-bible-school")

    class Meta:
        model = Academy
        fields = ("name", "slug", "tagline", "description", "brand_color")


class AcademyUpdateSerializer(serializers.ModelSerializer):
    """The slug is deliberately absent: public links depend on it."""

    class Meta:
        model = Academy
        fields = ("name", "tagline", "description", "brand_color", "website",
                  "support_email", "whatsapp_number")


class LogoUploadSerializer(serializers.Serializer):
    logo = serializers.ImageField()


class PublicAcademySerializer(serializers.ModelSerializer):
    class Meta:
        model = Academy
        fields = ("name", "slug", "tagline", "description", "logo", "brand_color",
                  "website", "support_email", "whatsapp_number")
        read_only_fields = fields


class OnboardingStepSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    done = serializers.BooleanField()
    blocking = serializers.BooleanField()


class OnboardingSerializer(serializers.Serializer):
    status = serializers.CharField()
    complete = serializers.BooleanField()
    can_activate = serializers.BooleanField()
    steps = OnboardingStepSerializer(many=True)


class SlugAvailabilitySerializer(serializers.Serializer):
    slug = serializers.CharField()
    available = serializers.BooleanField()


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademyMembership
        fields = ("id", "user", "role", "created_at")