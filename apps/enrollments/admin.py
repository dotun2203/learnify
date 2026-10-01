from django.contrib import admin

from .models import Enrollment, LessonProgress, LessonRelease


class ReleaseInline(admin.TabularInline):
    model = LessonRelease
    extra = 0
    fields = ("lesson", "position", "release_at", "status", "sent_at")
    readonly_fields = ("lesson", "position")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "academy", "status", "source", "started_at")
    list_filter = ("status", "source")
    search_fields = ("student__phone", "student__email", "course__title")
    raw_id_fields = ("student", "course", "academy")
    inlines = [ReleaseInline]


@admin.register(LessonRelease)
class LessonReleaseAdmin(admin.ModelAdmin):
    list_display = ("lesson", "enrollment", "position", "release_at", "status", "sent_at")
    list_filter = ("status",)
    raw_id_fields = ("enrollment", "lesson")


admin.site.register(LessonProgress)