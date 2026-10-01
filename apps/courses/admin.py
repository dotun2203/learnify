
# Register your models here.
from django.contrib import admin

from .models import Asset, Course, Lesson, Module


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("title", "position", "estimated_minutes", "is_preview")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "academy", "status", "price_kobo", "published_at")
    list_filter = ("status", "schedule_type")
    search_fields = ("title", "academy__name")
    raw_id_fields = ("academy", "created_by")


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "position")
    raw_id_fields = ("course",)
    inlines = [LessonInline]


admin.site.register([Lesson, Asset])