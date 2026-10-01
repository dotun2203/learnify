
# Create your views here.
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academies.mixins import AcademyScopedViewSetMixin
from apps.accounts.services import get_or_create_learner
from apps.core.exceptions import DomainError
from apps.courses.models import Course, Lesson
from apps.courses.selectors import published_courses
from apps.courses.serializers import LessonSerializer
from apps.delivery import selectors as delivery_selectors
from apps.delivery.models import Notification

from . import selectors, services
from . import serializers as s
from .models import Enrollment
from .permissions import IsEnrolledStudent

# ---------- student: /learn/ ----------

class MyEnrollmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          viewsets.GenericViewSet):
    """The student portal: my courses and my lesson list."""

    permission_classes = [IsAuthenticated, IsEnrolledStudent]
    serializer_class = s.EnrollmentSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Enrollment.objects.none()
        return selectors.enrollments_for_student(self.request.user)

    @extend_schema(tags=["learn"], responses={200: s.EnrollmentDetailSerializer})
    def retrieve(self, request, pk=None):
        enrollment = self.get_object()
        done = {
            lesson_id for lesson_id, progress in selectors.progress_map(enrollment).items()
            if progress.completed_at
        }
        releases = enrollment.releases.select_related("lesson", "lesson__module").all()
        rows = []
        for release in releases:
            available, reason = selectors.lesson_availability(enrollment, release.lesson)
            release.available = available
            release.locked_reason = reason
            release.completed = release.lesson_id in done
            rows.append(release)
        data = s.EnrollmentSerializer(enrollment).data
        data["lessons"] = s.ReleaseSerializer(rows, many=True).data
        return Response(data)


class LessonAccessView(APIView):
    """GET a released lesson's content; POST marks it complete."""

    permission_classes = [IsAuthenticated]

    def _enrollment(self, request, enrollment_id):
        enrollment = selectors.enrollments_for_student(request.user).filter(
            pk=enrollment_id).first()
        if enrollment is None:
            raise DomainError("Enrollment not found.", code="not_found", status_code=404)
        return enrollment

    @extend_schema(tags=["learn"], responses={200: LessonSerializer})
    def get(self, request, enrollment_id, lesson_id):
        enrollment = self._enrollment(request, enrollment_id)
        lesson = Lesson.objects.filter(pk=lesson_id,
                                       module__course=enrollment.course).first()
        if lesson is None:
            raise DomainError("Lesson not found.", code="not_found", status_code=404)
        services.open_lesson(enrollment=enrollment, lesson=lesson)
        return Response(LessonSerializer(lesson).data)

    @extend_schema(tags=["learn"], request=None, responses={200: s.ProgressSerializer})
    def post(self, request, enrollment_id, lesson_id):
        enrollment = self._enrollment(request, enrollment_id)
        lesson = Lesson.objects.filter(pk=lesson_id,
                                       module__course=enrollment.course).first()
        if lesson is None:
            raise DomainError("Lesson not found.", code="not_found", status_code=404)
        progress = services.complete_lesson(enrollment=enrollment, lesson=lesson)
        return Response(s.ProgressSerializer(progress).data)


class MyNotificationsView(ListAPIView):
    """The portal's bell menu — this is the 'web channel' inbox."""

    permission_classes = [IsAuthenticated]
    serializer_class = s.NotificationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        unread = self.request.query_params.get("unread") == "true"
        return delivery_selectors.notifications_for(self.request.user, unread_only=unread)

    @extend_schema(tags=["learn"], request=None, responses={204: None})
    def post(self, request):
        """Mark everything as read."""
        from django.utils import timezone
        delivery_selectors.notifications_for(request.user, unread_only=True).update(
            read_at=timezone.now()
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- creator: /studio/ ----------

class CourseStudentsViewSet(AcademyScopedViewSetMixin, viewsets.GenericViewSet):
    """Roster and manual enrolment, scoped by the X-Academy header."""

    serializer_class = s.RosterEntrySerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Course.objects.none()
        return Course.objects.filter(academy=self.academy)

    @extend_schema(tags=["studio"], responses={200: s.RosterEntrySerializer(many=True)})
    @action(detail=True, methods=["get"])
    def students(self, request, pk=None):
        course = self.get_object()
        page = self.paginate_queryset(selectors.enrollments_for_course(course))
        return self.get_paginated_response(
            s.RosterEntrySerializer(page, many=True).data)

    @extend_schema(tags=["studio"], request=s.ManualEnrollSerializer,
                   responses={201: s.EnrollmentSerializer})
    @action(detail=True, methods=["post"])
    def enroll(self, request, pk=None):
        """Add a student by hand — free seats, imports, and testing before payments."""
        course = self.get_object()
        ser = s.ManualEnrollSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        student, _ = get_or_create_learner(**ser.validated_data)
        enrollment = services.create_enrollment(
            course=course, student=student, source=Enrollment.Source.MANUAL)
        return Response(s.EnrollmentSerializer(enrollment).data,
                        status=status.HTTP_201_CREATED)


# ---------- public: /public/ ----------

class PublicEnrollView(APIView):
    """Free courses only. Paid ones go through checkout once payments ship."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["public"], request=s.PublicEnrollSerializer,
                   responses={201: s.EnrollmentSerializer})
    def post(self, request, academy_slug, course_slug):
        course = published_courses(academy_slug).filter(slug=course_slug).first()
        if course is None:
            raise DomainError("Course not found.", code="not_found", status_code=404)
        if not course.is_free:
            raise DomainError("This course must be purchased.", code="payment_required",
                              status_code=402)
        ser = s.PublicEnrollSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        student, _ = get_or_create_learner(**ser.validated_data)
        enrollment = services.create_enrollment(
            course=course, student=student, source=Enrollment.Source.FREE)
        return Response(s.EnrollmentSerializer(enrollment).data,
                        status=status.HTTP_201_CREATED)