from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import UserChangeAdminForm, UserCreationAdminForm
from .models import OTPCode, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeAdminForm
    add_form = UserCreationAdminForm
    ordering = ("-date_joined",)
    list_display = ("email", "phone", "first_name", "last_name", "is_phone_verified", "is_staff")
    search_fields = ("email", "phone", "first_name", "last_name")
    list_filter = ("is_staff", "is_active", "is_phone_verified")
    fieldsets = (
        (None, {"fields": ("email", "phone", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "preferred_language", "timezone")}),
        ("Verification", {
            "fields": ("is_phone_verified", "is_email_verified", "whatsapp_opt_in"),
        }),
        ("Permissions", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "phone", "is_staff", "usable_password", "password1", "password2"),
        }),
    )


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "channel", "target", "attempts", "expires_at",
                    "consumed_at", "created_at")
    list_filter = ("purpose", "channel")
    search_fields = ("target", "user__email", "user__phone")
    readonly_fields = [f.name for f in OTPCode._meta.fields]
    raw_id_fields = ("user",)
