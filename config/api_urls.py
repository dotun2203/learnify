from django.urls import include, path

urlpatterns = [
    path("", include("apps.accounts.urls")),
    # path("academies/", include("apps.academies.urls")),
    # path("studio/courses/", include("apps.courses.urls")),
    # path("webhooks/paystack/", include("apps.payments.webhook_urls")),
]
