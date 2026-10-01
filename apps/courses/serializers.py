from rest_framework import serializers

from .models import Asset, Course, Lesson, Module


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ("id", "file", "kind", "original_name", "size_bytes", "position")
        read_only_fields = ("id", "original_name", "size_bytes", "position")


class LessonSerializer(serializers.ModelSerializer):
    assets = AssetSerializer(many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = ("id", "module", "title", "body", "position", "estimated_minutes",
                  "is_preview", "assets")
        read_only_fields = ("id", "module", "position", "assets")


class LessonCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ("title", "body", "estimated_minutes", "is_preview")


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ("id", "course", "title", "summary", "position", "lessons")
        read_only_fields = ("id", "course", "position", "lessons")


class ModuleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ("title", "summary")


class CourseSerializer(serializers.ModelSerializer):
    price_naira = serializers.SerializerMethodField()
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ("id", "title", "slug", "subtitle", "description", "cover",
                  "price_kobo", "price_naira", "currency", "status", "published_at",
                  "schedule_type", "drip_interval_days", "delivery_time", "timezone", "require_sequential",
                  "lesson_count", "created_at", "updated_at")
        read_only_fields = ("id", "slug", "status", "published_at", "currency",
                            "price_naira", "lesson_count", "created_at", "updated_at")

    def get_price_naira(self, obj) -> float:
        return obj.price_naira

    def get_lesson_count(self, obj) -> int:
        return Lesson.objects.filter(module__course=obj).count()


class CourseDetailSerializer(CourseSerializer):
    modules = ModuleSerializer(many=True, read_only=True)

    class Meta(CourseSerializer.Meta):
        fields = (*CourseSerializer.Meta.fields, "modules")


class CourseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ("title", "subtitle", "description", "cover", "price_kobo",
                  "schedule_type", "drip_interval_days", "delivery_time", "timezone", "require_sequential")

    def validate_price_kobo(self, value):
        if value and value < 10000:  # NGN 100
            raise serializers.ValidationError("Paid courses must cost at least NGN 100.")
        return value

    def validate(self, attrs):
        schedule = attrs.get("schedule_type", getattr(self.instance, "schedule_type", None))
        interval = attrs.get("drip_interval_days",
                             getattr(self.instance, "drip_interval_days", 1))
        if schedule == Course.ScheduleType.CUSTOM and interval < 1:
            raise serializers.ValidationError(
                {"drip_interval_days": "Set how many days between lessons."})
        return attrs


class ReorderModuleSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    lessons = serializers.ListField(child=serializers.UUIDField(), required=False,
                                    default=list)


class ReorderSerializer(serializers.Serializer):
    modules = ReorderModuleSerializer(many=True)


class PublishBlockersSerializer(serializers.Serializer):
    blockers = serializers.ListField(child=serializers.CharField())


# ---------- public ----------

class PublicLessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        # No body unless the creator marked the lesson as a free preview
        fields = ("id", "title", "estimated_minutes", "is_preview")
        read_only_fields = fields


class PublicModuleSerializer(serializers.ModelSerializer):
    lessons = PublicLessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ("id", "title", "summary", "lessons")
        read_only_fields = fields


class PublicCourseSerializer(serializers.ModelSerializer):
    academy = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    price_naira = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ("id", "academy", "title", "slug", "subtitle", "description", "cover",
                  "price_kobo", "price_naira", "currency", "schedule_type",
                  "drip_interval_days", "published_at")
        read_only_fields = fields

    def get_price_naira(self, obj) -> float:
        return obj.price_naira


class PublicCourseDetailSerializer(PublicCourseSerializer):
    modules = PublicModuleSerializer(many=True, read_only=True)

    class Meta(PublicCourseSerializer.Meta):
        fields = (*PublicCourseSerializer.Meta.fields, "modules")