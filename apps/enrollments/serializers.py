from rest_framework import serializers

from apps.courses.serializers import LessonSerializer

from .models import Enrollment, LessonProgress, LessonRelease


class StudentSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.EmailField(allow_null=True)


class CourseSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    slug = serializers.SlugField()
    cover = serializers.ImageField(allow_null=True)


class EnrollmentSerializer(serializers.ModelSerializer):
    course = CourseSummarySerializer(read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = ("id", "course", "status", "source", "timezone", "started_at",
                  "completed_at", "progress")
        read_only_fields = fields

    def get_progress(self, obj) -> dict:
        from .selectors import course_progress
        return course_progress(obj)


class RosterEntrySerializer(serializers.ModelSerializer):
    student = StudentSummarySerializer(read_only=True)
    lessons_completed = serializers.IntegerField(read_only=True)

    class Meta:
        model = Enrollment
        fields = ("id", "student", "status", "source", "started_at", "completed_at",
                  "lessons_completed")
        read_only_fields = fields


class ReleaseSerializer(serializers.ModelSerializer):
    """The student's lesson list: titles always, bodies only once unlocked."""

    lesson_id = serializers.UUIDField(source="lesson.id", read_only=True)
    title = serializers.CharField(source="lesson.title", read_only=True)
    module = serializers.CharField(source="lesson.module.title", read_only=True)
    estimated_minutes = serializers.IntegerField(source="lesson.estimated_minutes",
                                                 read_only=True)
    available = serializers.BooleanField(read_only=True)
    locked_reason = serializers.CharField(read_only=True, allow_blank=True)
    completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = LessonRelease
        fields = ("id", "lesson_id", "title", "module", "position", "release_at",
                  "estimated_minutes", "available", "locked_reason", "completed")
        read_only_fields = fields


class EnrollmentDetailSerializer(EnrollmentSerializer):
    lessons = ReleaseSerializer(many=True, read_only=True)

    class Meta(EnrollmentSerializer.Meta):
        fields = (*EnrollmentSerializer.Meta.fields, "lessons")


class LessonContentSerializer(LessonSerializer):
    """A released lesson, body included."""

    class Meta(LessonSerializer.Meta):
        pass


class ProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonProgress
        fields = ("id", "lesson", "opened_at", "completed_at")
        read_only_fields = fields


class ManualEnrollSerializer(serializers.Serializer):
    """The creator adds a student by phone — the same identity rule as checkout."""

    phone = serializers.CharField()
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_null=True, default=None)


class PublicEnrollSerializer(ManualEnrollSerializer):
    pass


class NotificationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    title = serializers.CharField()
    body = serializers.CharField()
    link = serializers.CharField()
    read_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()