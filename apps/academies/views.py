from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import selectors, services
from . import serializers as s
from .models import Academy
from .permissions import IsAcademyOwnerObject
from .validators import validate_academy_slug


class AcademyViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Academies the current user belongs to."""

    serializer_class = s.AcademySerializer
    lookup_field = "slug"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation
            return Academy.objects.none()
        return selectors.academies_for_user(self.request.user)

    @extend_schema(tags=["academies"], request=s.AcademyCreateSerializer,
                   responses={201: s.AcademySerializer})
    def create(self, request):
        ser = s.AcademyCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        academy = services.create_academy(owner=request.user, **ser.validated_data)
        return Response(self._out(academy), status=status.HTTP_201_CREATED)

    @extend_schema(tags=["academies"], request=s.AcademyUpdateSerializer,
                   responses={200: s.AcademySerializer})
    def partial_update(self, request, slug=None):
        academy = self.get_object()
        self.check_object_permissions(request, academy)
        ser = s.AcademyUpdateSerializer(academy, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        academy = services.update_academy(academy=academy, **ser.validated_data)
        return Response(self._out(academy))

    @extend_schema(tags=["academies"], request=s.LogoUploadSerializer,
                   responses={200: s.AcademySerializer})
    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser],
            permission_classes=[IsAcademyOwnerObject])
    def logo(self, request, slug=None):
        academy = self.get_object()
        ser = s.LogoUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        academy = services.update_academy(academy=academy, logo=ser.validated_data["logo"])
        return Response(self._out(academy))

    @extend_schema(tags=["academies"], responses={200: s.OnboardingSerializer})
    @action(detail=True, methods=["get"])
    def onboarding(self, request, slug=None):
        return Response(selectors.onboarding_checklist(self.get_object()))

    def _out(self, academy):
        academy = self.get_queryset().get(pk=academy.pk)
        return s.AcademySerializer(academy, context={"request": self.request}).data


class SlugAvailabilityView(APIView):
    """Live check for the 'choose your address' field in the signup wizard."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["academies"], parameters=[OpenApiParameter("slug", str)],
                   responses={200: s.SlugAvailabilitySerializer})
    def get(self, request):
        raw = request.query_params.get("slug", "")
        try:
            slug = validate_academy_slug(raw)
        except DjangoValidationError as exc:
            return Response({"slug": raw, "available": False, "reason": exc.messages[0]})
        return Response({"slug": slug, "available": selectors.slug_is_available(slug)})


class PublicAcademyView(RetrieveAPIView):
    """The academy's public profile, used by its landing page."""

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = s.PublicAcademySerializer
    lookup_field = "slug"
    queryset = Academy.objects.filter(status=Academy.Status.ACTIVE)