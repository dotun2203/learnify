
# Create your views here.
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.academies.mixins import AcademyScopedViewSetMixin

from . import selectors, services
from . import serializers as s
from .models import Course


class CourseViewSet(AcademyScopedViewSetMixin, viewsets.ModelViewSet):
    """Studio: /studio/courses/ — always scoped to the X-Academy header."""

    parser_classes = [JSONParser, MultiPartParser, FormParser]
    serializer_class = s.CourseSerializer
    filterset_fields = ["status"]
    search_fields = ["title", "subtitle"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Course.objects.none()
        return selectors.course_detail_qs(self.academy)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return s.CourseWriteSerializer
        if self.action == "retrieve":
            return s.CourseDetailSerializer
        return s.CourseSerializer

    @extend_schema(tags=["studio"], responses={201: s.CourseSerializer})
    def create(self, request, *args, **kwargs):
        ser = s.CourseWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        course = services.create_course(
            academy=self.academy, created_by=request.user, **ser.validated_data)
        return Response(s.CourseSerializer(course).data, status=status.HTTP_201_CREATED)

    @extend_schema(tags=["studio"], responses={200: s.CourseSerializer})
    def partial_update(self, request, *args, **kwargs):
        course = self.get_object()
        ser = s.CourseWriteSerializer(course, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        course = services.update_course(course=course, **ser.validated_data)
        return Response(s.CourseSerializer(course).data)

    @extend_schema(tags=["studio"], request=None, responses={200: s.CourseSerializer})
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        course = services.publish_course(course=self.get_object())
        return Response(s.CourseSerializer(course).data)

    @extend_schema(tags=["studio"], request=None, responses={200: s.CourseSerializer})
    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        course = services.unpublish_course(course=self.get_object())
        return Response(s.CourseSerializer(course).data)

    @extend_schema(tags=["studio"], responses={200: s.PublishBlockersSerializer})
    @action(detail=True, methods=["get"], url_path="publish-check")
    def publish_check(self, request, pk=None):
        """What the Studio shows next to a greyed-out Publish button."""
        return Response({"blockers": selectors.publish_blockers(self.get_object())})

    @extend_schema(tags=["studio"], request=s.ReorderSerializer,
                   responses={200: s.CourseDetailSerializer})
    @action(detail=True, methods=["post"])
    def reorder(self, request, pk=None):
        ser = s.ReorderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        course = services.reorder_course(course=self.get_object(),
                                         modules=ser.validated_data["modules"])
        course = self.get_queryset().get(pk=course.pk)
        return Response(s.CourseDetailSerializer(course).data)

    @extend_schema(tags=["studio"], request=s.ModuleCreateSerializer,
                   responses={201: s.ModuleSerializer})
    @action(detail=True, methods=["get", "post"])
    def modules(self, request, pk=None):
        course = self.get_object()
        if request.method == "GET":
            return Response(s.ModuleSerializer(course.modules.all(), many=True).data)
        ser = s.ModuleCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        module = services.add_module(course=course, **ser.validated_data)
        return Response(s.ModuleSerializer(module).data, status=status.HTTP_201_CREATED)


class ModuleViewSet(AcademyScopedViewSetMixin,
                    mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                    mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = s.ModuleSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return selectors.Module.objects.none()
        return selectors.modules_for_academy(self.academy).prefetch_related("lessons")

    @extend_schema(tags=["studio"], request=s.LessonCreateSerializer,
                   responses={201: s.LessonSerializer})
    @action(detail=True, methods=["get", "post"])
    def lessons(self, request, pk=None):
        module = self.get_object()
        if request.method == "GET":
            return Response(s.LessonSerializer(module.lessons.all(), many=True).data)
        ser = s.LessonCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        lesson = services.add_lesson(module=module, **ser.validated_data)
        return Response(s.LessonSerializer(lesson).data, status=status.HTTP_201_CREATED)


class LessonViewSet(AcademyScopedViewSetMixin,
                    mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                    mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = s.LessonSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return selectors.Lesson.objects.none()
        return selectors.lessons_for_academy(self.academy).prefetch_related("assets")

    @extend_schema(tags=["studio"], request=s.AssetSerializer,
                   responses={201: s.AssetSerializer})
    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def assets(self, request, pk=None):
        lesson = self.get_object()
        ser = s.AssetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        asset = services.add_asset(lesson=lesson, **ser.validated_data)
        return Response(s.AssetSerializer(asset).data, status=status.HTTP_201_CREATED)


# ---------- public ----------

class PublicCourseListView(ListAPIView):
    """Catalogue for an academy's landing page."""

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = s.PublicCourseSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Course.objects.none()
        return selectors.published_courses(self.kwargs["academy_slug"])


class PublicCourseDetailView(RetrieveAPIView):
    """The sales page: outline visible, lesson bodies hidden."""

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = s.PublicCourseDetailSerializer
    lookup_field = "slug"
    lookup_url_kwarg = "course_slug"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Course.objects.none()
        return selectors.published_courses(self.kwargs["academy_slug"]).prefetch_related(
            "modules__lessons"
        )