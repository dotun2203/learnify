from django.contrib import admin

from .models import Academy, AcademyMembership


class MembershipInline(admin.TabularInline):
    model = AcademyMembership
    extra = 0
    raw_id_fields = ("user",)


@admin.register(Academy)
class AcademyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "is_active", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "slug", "owner__phone", "owner__email")
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ("owner",)
    inlines = [MembershipInline]
